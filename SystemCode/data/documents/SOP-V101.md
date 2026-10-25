# SOP-V101: Standard Operating Procedure for 3-Phase High Pressure Separator V-101

**Document ID:** SOP-V101  
**Revision:** 4.2  
**Effective Date:** 2026-01-15  
**Asset Tag:** V-101  
**Plant Area:** 10 - Primary Separation & Stabilization  

---

## [SOP-V101:SEC-01] Section 1. High Pressure Abatement & PCV-101 Malfunction Response

### 1.1 Operating Limits
- **Normal Operating Pressure:** 30.0 barg to 33.0 barg
- **High Pressure Alarm (PAH-101):** 34.0 barg
- **High-High Pressure Alarm & ESD-1 Trip (PAHH-101):** 36.5 barg
- **Pressure Safety Valve (PSV-101A/B) Setpoint:** 38.0 barg

### 1.2 Immediate Action for PCV-101 Stiction or Actuator Failure
1. If PT-101 exceeds 34.0 barg and gas outlet valve PCV-101 fails to open or responds sluggishly, immediately verify control loop status in DCS.
2. Put PCV-101 into **MANUAL** mode and attempt stepping the output to 75% or 100%.
3. If the valve stem does not move (confirmed mechanically or via flow FT-101), dispatch field operator to inspect local instrument air supply (regulator set to 4.5 barg) and physical positioner linkage.
4. Unlock and crack open manual bypass valve **HV-101B** around PCV-101 to relieve vessel pressure, modulating opening to stabilize vessel pressure between 31.0 and 32.5 barg.
5. If vessel pressure approaches 36.0 barg and bypass throttling is insufficient, crack open manual flare depressurization valve **BDV-101** to prevent mechanical lifting of thermal relief valve PSV-101.

---

## [SOP-V101:SEC-02] Section 2. Demister Fouling, Carryover & Foaming Mitigation

### 2.1 Demister Pad Differential Pressure Limits
- **Normal Clean Demister DP (DPIT-101):** 0.015 - 0.035 bar
- **Fouling Warning Threshold:** > 0.050 bar
- **High DP Alarm (DPAH-101):** 0.080 bar
- **Carryover Risk Limit:** > 0.120 bar (indicates severe liquid entrainment toward compressor suction drum V-102)

### 2.2 Anti-Foam Chemical Dosing & Liquid Carryover Response
1. When DPIT-101 rises above 0.060 bar accompanied by level rise in suction scrubber V-102 (LT-103), initiate anti-foam chemical injection via metering pump **P-105**.
2. Ramp silicone-based anti-foam dosing rate from baseline 5 ppm to 25 ppm in 5-minute increments.
3. Reduce gas throughput through V-101 by pinching upstream manifold choke valves by 10-15% to lower gas superficial velocity across the mesh demister pad.
4. Check scrubber V-102 liquid drain valve LCV-103 to ensure condensate is continuously evacuated to prevent liquid ingress into compressor K-101.

---

## [SOP-V101:SEC-03] Section 3. Emulsion Layer & Oil-Water Interface Control

### 3.1 Interface Level Control & Transmitter Drift
- **Target Interface Level (LT-102):** 50%
- **Interface Range (Clean separation):** 40% - 60%
- **Emulsion Pad / Rag Layer Formation:** Indicated by sluggish interface response or mismatch between nuclear interface profiler and capacitive differential probe LT-102.

### 3.2 Corrective Protocol for Emulsion Pad
1. Sample oil-water interface from local gauge glass draw-off ports (LG-102).
2. If heavy rag layer emulsion exceeds 150 mm thickness, increase demulsifier injection rate at upstream manifold by 20%.
3. Increase separator operating temperature by 3-5 °C if heat tracing or pre-heater is online to accelerate oil-water coalescence.
4. If water carryunder into crude oil line is detected at BS&W analyzer AT-101 (> 0.5% water cut), partially open manual low-point drain bypass to lower interface to 35%.

---

## [SOP-V101:SEC-04] Section 4. Severe Production Slug Handling

### 4.1 Liquid Surge Dynamics
- A sudden liquid slug arriving from multiphase flowline can rapidly increase liquid level LT-101 at rates exceeding 3% per second.

### 4.2 Slug Response Checklist
1. Dispatch notification to field gathering operator to pinch wellhead choke valves on active subsea/slugging wells by 20%.
2. Fully open oil outlet valve LCV-101 and water outlet valve LCV-102 in DCS manual station to maximize liquid evacuation into downstream surge vessels.
3. Monitor V-101 vessel pressure closely, as liquid slug reduces available vapor volume and may trigger secondary pressure spike.
