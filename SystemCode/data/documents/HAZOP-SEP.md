# HAZOP-SEP: Hazard and Operability Study — High Pressure Separation & Gas Compression

**Study Reference:** HAZOP-2025-SEP-04  
**Date of Study:** 2025-11-20  
**Facility:** Offshore / Onshore Central Processing Facility (CPF)  
**Nodes Reviewed:** Node 1 (Separator V-101 Vapor Line), Node 2 (Separator Liquid Outlets), Node 3 (Compressor K-101 Train)  

---

## [HAZOP-SEP:NODE-01] Node 1. High Pressure in Separator V-101 (Parameter: Pressure / High)

- **Deviation:** MORE Pressure (Vessel overpressure > 34.0 barg)
- **Direct Causes:**
  1. Pressure control valve PCV-101 fails closed due to mechanical stem stiction or loss of instrument air.
  2. Gas export pipeline blockage or downstream compressor trip.
  3. Upstream wellhead pressure surge during slug arrival.
- **Consequences:**
  - Vessel design pressure exceeded (42.0 barg).
  - Potential mechanical deformation or rupture if safety relief fails.
  - Spurious lifting of spring-loaded PSV-101 causing major flaring and environmental reportable emission.
- **Existing Safeguards:**
  - Independent pressure transmitter PT-101 with PAH-101 alarm at 34.0 barg.
  - Safety instrumented system trip PAHH-101 at 36.5 barg closing inlet SDV-101.
  - Dual relief valves PSV-101A/B sized for 100% blocked vapor flow set at 38.0 barg.
  - Manual bypass valve HV-101B and emergency blowdown valve BDV-101.
- **Recommended Action:**
  - Put PCV-101 into Manual mode and crack open bypass HV-101B.
  - If PT-101 > 35.5 barg, pinch upstream production well chokes by 15% immediately.

---

## [HAZOP-SEP:NODE-02] Node 2. Liquid Carryover from V-101 to Compressor (Parameter: Phase Distribution / Liquid in Gas)

- **Deviation:** MORE Liquid in Vapor Outlet (Carryover)
- **Direct Causes:**
  1. Demister mesh pad fouling with wax/asphaltenes causing high gas velocity channeling.
  2. Severe crude foaming due to sudden depressurization or surfactant contamination.
  3. Liquid level in V-101 exceeding 80% (flooding separation space).
- **Consequences:**
  - Massive liquid droplet carryover into gas line to suction scrubber V-102.
  - Liquid ingestion into centrifugal compressor K-101 leading to impeller blade fracture, catastrophic thrust bearing failure, and gas leak.
- **Existing Safeguards:**
  - Demister differential pressure transmitter DPIT-101 with alarm DPAH-101 at 0.080 bar.
  - Suction scrubber V-102 with high level alarm LAH-103 and compressor shutdown trip LAHH-103.
  - Continuous anti-foam chemical injection skid.
- **Recommended Action:**
  - Ramp anti-foam dosing from 5 ppm to 25 ppm.
  - Verify scrubber V-102 drain valve LCV-103 is discharging; open bypass drain if needed.
  - Reduce gas throughput by pinching upstream wellhead chokes.

---

## [HAZOP-SEP:NODE-03] Node 3. Aerodynamic Surge in Compressor K-101 (Parameter: Flow / Low & Pressure / Differential)

- **Deviation:** LESS Flow / MORE Vibration (Surge condition)
- **Direct Causes:**
  1. Anti-surge valve ASV-101 fails to open upon sudden drop in suction gas volume.
  2. Sudden rise in discharge line pressure due to downstream pipeline restriction.
  3. Excessive suction strainer / scrubber fouling.
- **Consequences:**
  - Flow reversal and violent aerodynamic surge cycling at 2-5 Hz.
  - High vibration (VT-101 > 4.5 mm/s RMS) damaging dry gas seals and tilting pad radial bearings.
  - Potential gas release to atmosphere via damaged compressor casing seals.
- **Existing Safeguards:**
  - Automated fast-acting anti-surge controller with dedicated margin algorithm.
  - Vibration monitoring transmitters VT-101 with trip VAHH-101 at 4.5 mm/s RMS.
  - Manual emergency override for ASV-101.
- **Recommended Action:**
  - Switch ASV-101 to Manual mode and force open to 100% full recycle immediately.
  - Inspect suction scrubber DP and verify inlet pressure PT-102 is adequate.

---

## [HAZOP-SEP:NODE-04] Node 4. Oil-Water Interface Drift & Emulsion (Parameter: Interface / High or Low)

- **Deviation:** OTHER Interface Behavior (Emulsion pad / transmitter drift)
- **Direct Causes:**
  1. Dense emulsion / rag layer blinding capacitive interface sensor LT-102.
  2. Oil-water interface control valve LCV-102 mechanical failure.
- **Consequences:**
  - Unseparated water carryover into export crude oil pipeline (> 0.5% specification penalty).
  - Oil carryunder into water treatment system causing environmental discharge limit exceedance (> 15 ppm oil in water).
- **Existing Safeguards:**
  - Local reflex gauge glass LG-102 with manual draw-off sample cocks.
  - Online BS&W water-cut analyzer AT-101 on crude outlet.
  - High interface alarm IAH-102.
- **Recommended Action:**
  - Dispatch operator to sample from local gauge glass ports to confirm true interface level.
  - Increase demulsifier chemical dosing rate by 20%.
