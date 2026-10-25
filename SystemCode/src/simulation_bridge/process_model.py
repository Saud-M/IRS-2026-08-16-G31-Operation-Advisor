"""Dynamic Process Model for Three-Phase Separator (V-101) and Two-Stage Centrifugal Compression Train.

Formulates physical differential equations:
1. Gas inventory and pressure dynamics: dP/dt = (R * T / V_gas) * (Q_gas_in - Q_gas_out)
2. Oil volume accumulation: dV_oil/dt = Q_oil_in - Q_oil_out
3. Water volume accumulation: dV_water/dt = Q_water_in - Q_water_out
4. Demister differential pressure: DP = f(gas_velocity, entrainment, fouling)
5. Scrubber liquid accumulation from carryover
6. Centrifugal compressor power, discharge temperature, surge proximity, and shaft vibration
7. Closed-loop PI controllers for pressure (PIC-101), oil level (LIC-101), and interface level (LIC-102)
"""

from dataclasses import dataclass, field
import math
from typing import Dict, Any, Optional


@dataclass
class ProcessParameters:
    """Design parameters and physical constants of the production train."""
    # Vessel Geometry (V-101 Separator)
    vessel_volume_total: float = 25.0  # m^3
    vessel_diameter: float = 2.2       # m
    vessel_length: float = 6.6         # m
    nominal_liquid_fraction: float = 0.50 # 50% liquid, 50% gas volume

    # Thermodynamic Properties (Natural Gas / Light Crude / Produced Water)
    gas_constant_R: float = 8.314      # J / (mol * K)
    gas_molar_mass: float = 0.0185     # kg / mol (rich methane-ethane mix)
    gas_specific_heat_ratio: float = 1.28 # gamma (Cp / Cv)
    gas_heat_capacity_cp: float = 2200.0 # J / (kg * K)
    oil_density: float = 820.0         # kg / m^3
    water_density: float = 1030.0      # kg / m^3
    atmospheric_pressure_bar: float = 1.01325

    # Nominal Inflow Rates (at standard conditions)
    nominal_gas_inflow_sm3h: float = 90000.0  # Sm^3/h
    nominal_oil_inflow_m3h: float = 40.0      # m^3/h
    nominal_water_inflow_m3h: float = 18.0    # m^3/h
    nominal_inlet_temp_c: float = 45.0        # °C

    # Compressor Train (K-101 / K-102)
    stage1_compression_ratio: float = 2.4
    stage2_compression_ratio: float = 2.2
    compressor_polytropic_eff: float = 0.82
    surge_flow_threshold_sm3h: float = 62000.0 # Sm^3/h limit for stage 1 surge line
    demister_nominal_clean_dp_bar: float = 0.10

    # Controller Tunings (Proportional Gain Kp, Integral Time Ti in seconds)
    pic101_setpoint_barg: float = 30.0
    pic101_kp: float = 2.5
    pic101_ti_sec: float = 35.0

    lic101_setpoint_pct: float = 50.0
    lic101_kp: float = 1.8
    lic101_ti_sec: float = 60.0

    lic102_setpoint_pct: float = 25.0
    lic102_kp: float = 2.0
    lic102_ti_sec: float = 50.0


@dataclass
class ProcessState:
    """Current dynamic state variables of the process train."""
    time_sec: float = 0.0

    # Separator V-101 States
    pressure_barg: float = 30.0
    temperature_c: float = 45.0
    oil_volume_m3: float = 3.125       # 25% oil (3.125 m^3) + 25% water (3.125 m^3) = 50% total
    water_volume_m3: float = 3.125     # 25% of 12.5 m^3 liquid capacity
    liquid_level_pct: float = 50.0    # Total liquid volume / vessel liquid capacity
    interface_level_pct: float = 25.0 # Water volume / vessel liquid capacity

    # Inflow and Outflow Rates
    gas_inflow_sm3h: float = 90000.0
    oil_inflow_m3h: float = 40.0
    water_inflow_m3h: float = 18.0

    gas_outflow_sm3h: float = 90000.0
    oil_outflow_m3h: float = 40.0
    water_outflow_m3h: float = 18.0

    # Demister & Scrubber (V-102)
    demister_dp_bar: float = 0.10
    scrubber_liquid_level_pct: float = 5.0
    liquid_carryover_rate_m3h: float = 0.0

    # Valve Positions [0.0 = fully closed, 1.0 = fully open]
    pcv101_position: float = 0.50
    lcv101_position: float = 0.50
    lcv102_position: float = 0.50

    # Controller Integrator Accumulators
    pic101_integral: float = 0.50
    lic101_integral: float = 0.50
    lic102_integral: float = 0.50

    # Compressor Stage 1 (K-101) & Stage 2 (K-102)
    stage1_suction_p_barg: float = 29.9
    stage1_discharge_p_barg: float = 71.5
    stage1_discharge_temp_c: float = 118.0
    stage2_discharge_p_barg: float = 156.0
    compressor_power_kw: float = 3250.0
    surge_margin_pct: float = 31.0
    shaft_vibration_mms: float = 2.0
    in_surge: bool = False

    # Fault and Degradation Modifiers
    pcv_stiction_active: bool = False
    pcv_stuck_target: Optional[float] = None
    demister_fouling_factor: float = 1.0
    foam_carryover_factor: float = 0.0
    interface_transmitter_bias_pct: float = 0.0
    inlet_slug_factor: float = 1.0


class SeparatorCompressorTrain:
    """Integrates dynamic equations of state across the separator and compressor train."""

    def __init__(self, params: Optional[ProcessParameters] = None, initial_state: Optional[ProcessState] = None):
        self.params = params or ProcessParameters()
        self.state = initial_state or ProcessState()
        self.dt = 1.0  # Default simulation step size in seconds

    def step(self, dt: float = 1.0) -> ProcessState:
        """Advance the physics simulation by dt seconds."""
        self.dt = dt
        s = self.state
        p = self.params

        s.time_sec += dt

        # 1. Update Inflow with potential slug factor
        current_gas_in = p.nominal_gas_inflow_sm3h * s.inlet_slug_factor
        current_oil_in = p.nominal_oil_inflow_m3h * s.inlet_slug_factor
        current_water_in = p.nominal_water_inflow_m3h * s.inlet_slug_factor

        s.gas_inflow_sm3h = current_gas_in
        s.oil_inflow_m3h = current_oil_in
        s.water_inflow_m3h = current_water_in

        # 2. Control Loops Execution
        # Pressure Control (PIC-101 -> PCV-101)
        pressure_error = s.pressure_barg - p.pic101_setpoint_barg
        s.pic101_integral += (pressure_error / p.pic101_ti_sec) * dt
        s.pic101_integral = max(0.0, min(1.0, s.pic101_integral))  # Anti-windup
        pcv_desired = 0.50 + p.pic101_kp * (pressure_error / 5.0) + s.pic101_integral - 0.50
        pcv_desired = max(0.02, min(1.0, pcv_desired))

        if s.pcv_stiction_active and s.pcv_stuck_target is not None:
            # Valve is stuck at fault target
            s.pcv101_position = s.pcv_stuck_target
        else:
            # Realistic valve actuator rate limiting (max 5% stroke per sec)
            dp_stroke = max(-0.05 * dt, min(0.05 * dt, pcv_desired - s.pcv101_position))
            s.pcv101_position += dp_stroke

        # Hydrocarbon Liquid Level Control (LIC-101 -> LCV-101)
        level_error = s.liquid_level_pct - p.lic101_setpoint_pct
        s.lic101_integral += (level_error / p.lic101_ti_sec) * dt
        s.lic101_integral = max(0.0, min(1.0, s.lic101_integral))
        lcv101_desired = 0.50 + p.lic101_kp * (level_error / 50.0) + s.lic101_integral - 0.50
        s.lcv101_position = max(0.0, min(1.0, lcv101_desired))

        # Water Interface Level Control (LIC-102 -> LCV-102)
        # Measured level includes potential transmitter sensor bias
        measured_interface_pct = s.interface_level_pct + s.interface_transmitter_bias_pct
        interface_error = measured_interface_pct - p.lic102_setpoint_pct
        s.lic102_integral += (interface_error / p.lic102_ti_sec) * dt
        s.lic102_integral = max(0.0, min(1.0, s.lic102_integral))
        lcv102_desired = 0.50 + p.lic102_kp * (interface_error / 25.0) + s.lic102_integral - 0.50
        s.lcv102_position = max(0.0, min(1.0, lcv102_desired))

        # 3. Mass & Volume Balances
        # Total vessel volume = 25 m^3. Maximum liquid hold-up = 12.5 m^3
        v_liq_max = p.vessel_volume_total * p.nominal_liquid_fraction
        v_gas = max(1.0, p.vessel_volume_total - (s.oil_volume_m3 + s.water_volume_m3))

        # Liquid outflows governed by valve position and differential pressure to downstream
        cv_oil = (p.nominal_oil_inflow_m3h / 0.50) / 3600.0  # m^3/s at 50% open
        cv_water = (p.nominal_water_inflow_m3h / 0.50) / 3600.0

        delta_p_liq = max(0.5, s.pressure_barg - 10.0) # downstream 10 barg
        oil_out_rate_m3s = s.lcv101_position * cv_oil * math.sqrt(delta_p_liq / 20.0)
        water_out_rate_m3s = s.lcv102_position * cv_water * math.sqrt(delta_p_liq / 20.0)

        s.oil_outflow_m3h = oil_out_rate_m3s * 3600.0
        s.water_outflow_m3h = water_out_rate_m3s * 3600.0

        # Accumulation
        d_v_oil = (current_oil_in / 3600.0 - oil_out_rate_m3s) * dt
        d_v_water = (current_water_in / 3600.0 - water_out_rate_m3s) * dt

        s.oil_volume_m3 = max(0.1, s.oil_volume_m3 + d_v_oil)
        s.water_volume_m3 = max(0.1, s.water_volume_m3 + d_v_water)

        total_liquid_m3 = s.oil_volume_m3 + s.water_volume_m3
        s.liquid_level_pct = min(100.0, (total_liquid_m3 / v_liq_max) * 100.0)
        s.interface_level_pct = min(100.0, (s.water_volume_m3 / v_liq_max) * 100.0)

        # 4. Gas Balance & Separator Pressure Dynamics
        # Gas export valve flow (Sm^3/h)
        cv_gas = (p.nominal_gas_inflow_sm3h / 0.50)
        gas_out_rate_sm3h = s.pcv101_position * cv_gas * math.sqrt(max(0.1, s.pressure_barg / 30.0))
        s.gas_outflow_sm3h = gas_out_rate_sm3h

        # Ideal Gas Law derivative: dP/dt = (P_abs / V_gas) * (dV_gas/dt_net)
        # Using molar volumetric flow at standard conditions (1 Sm^3 = 41.57 mol)
        mol_per_sm3 = 101325.0 / (8.314 * 288.15) # ~42.29 mol/Sm^3
        molar_flow_net = (current_gas_in - gas_out_rate_sm3h) * (mol_per_sm3 / 3600.0)

        temp_k = s.temperature_c + 273.15
        dp_dt_pascal = (molar_flow_net * p.gas_constant_R * temp_k) / v_gas
        dp_dt_bar = dp_dt_pascal / 1e5

        s.pressure_barg = max(0.5, s.pressure_barg + dp_dt_bar * dt)

        # 5. Demister DP & Liquid Carryover to Suction Scrubber V-102
        # Carryover surges when liquid level exceeds 70% or foaming is active
        high_level_carryover = max(0.0, (s.liquid_level_pct - 68.0) * 0.15)
        s.liquid_carryover_rate_m3h = high_level_carryover + s.foam_carryover_factor * 8.0

        gas_velocity_ratio = max(0.1, s.gas_outflow_sm3h / p.nominal_gas_inflow_sm3h)
        demister_clean_dp = p.demister_nominal_clean_dp_bar * (gas_velocity_ratio ** 1.8)
        fouling_dp = s.demister_fouling_factor * (1.0 + s.liquid_carryover_rate_m3h * 0.08)
        s.demister_dp_bar = demister_clean_dp * fouling_dp

        # Scrubber liquid accumulation
        scrubber_inflow = s.liquid_carryover_rate_m3h / 3600.0
        s.scrubber_liquid_level_pct = min(100.0, s.scrubber_liquid_level_pct + (scrubber_inflow * 100.0 / 1.5) * dt)

        # 6. Compressor Train Dynamics (Stage 1 K-101 and Stage 2 K-102)
        s.stage1_suction_p_barg = max(0.2, s.pressure_barg - s.demister_dp_bar)
        p_suc_abs = s.stage1_suction_p_barg + p.atmospheric_pressure_bar

        # Compression ratio
        p_dis_abs = p_suc_abs * p.stage1_compression_ratio
        s.stage1_discharge_p_barg = p_dis_abs - p.atmospheric_pressure_bar

        gamma = p.gas_specific_heat_ratio
        exp_temp = (gamma - 1.0) / (gamma * p.compressor_polytropic_eff)
        t_dis_k = temp_k * (p.stage1_compression_ratio ** exp_temp)
        s.stage1_discharge_temp_c = t_dis_k - 273.15

        # Compressor power consumption (kW)
        mass_flow_kgs = (s.gas_outflow_sm3h * p.gas_molar_mass * mol_per_sm3) / 3600.0
        work_j_kg = (gamma / (gamma - 1.0)) * (p.gas_constant_R / p.gas_molar_mass) * temp_k * (
            (p.stage1_compression_ratio ** exp_temp) - 1.0
        )
        s.compressor_power_kw = (mass_flow_kgs * work_j_kg / 1000.0) / p.compressor_polytropic_eff

        # Surge Margin & Vibration
        # Surge occurs when flow drops below threshold for current pressure ratio
        surge_limit_flow = p.surge_flow_threshold_sm3h * math.sqrt(max(0.5, p.stage1_compression_ratio / 2.4))
        surge_distance_sm3h = s.gas_outflow_sm3h - surge_limit_flow
        s.surge_margin_pct = (surge_distance_sm3h / surge_limit_flow) * 100.0

        if s.surge_margin_pct < 0.0 or s.liquid_carryover_rate_m3h > 3.0:
            s.in_surge = True
            # Violent oscillations in vibration
            vibe_surge = 5.5 + 2.0 * math.sin(s.time_sec * 3.14)
            s.shaft_vibration_mms = max(4.8, vibe_surge)
        else:
            s.in_surge = False
            # Nominal base vibration with slight flow dependence
            s.shaft_vibration_mms = 1.8 + 0.5 * (s.gas_outflow_sm3h / p.nominal_gas_inflow_sm3h)

        return s

    def snapshot(self) -> Dict[str, Any]:
        """Return scalar snapshot of all current process values."""
        s = self.state
        return {
            "time_sec": round(s.time_sec, 2),
            "PT-101": round(s.pressure_barg, 3),
            "LT-101": round(s.liquid_level_pct, 2),
            "LT-102": round(s.interface_level_pct + s.interface_transmitter_bias_pct, 2),
            "TT-101": round(s.temperature_c, 2),
            "FT-101": round(s.gas_outflow_sm3h, 1),
            "DP-101": round(s.demister_dp_bar, 4),
            "ST-101": round(s.shaft_vibration_mms, 2),
            "PCV-101_pos": round(s.pcv101_position, 3),
            "LCV-101_pos": round(s.lcv101_position, 3),
            "LCV-102_pos": round(s.lcv102_position, 3),
            "V102_scrubber_level": round(s.scrubber_liquid_level_pct, 2),
            "compressor_power_kw": round(s.compressor_power_kw, 1),
            "surge_margin_pct": round(s.surge_margin_pct, 2),
            "in_surge": s.in_surge,
        }
