# SOP-K101: Standard Operating Procedure for Centrifugal Gas Compressor K-101

**Document ID:** SOP-K101  
**Revision:** 3.8  
**Effective Date:** 2026-02-01  
**Asset Tag:** K-101  
**Plant Area:** 20 - Gas Compression & Treating  

---

## [SOP-K101:SEC-01] Section 1. Anti-Surge Control & Surge Prevention (ASV-101)

### 1.1 Aerodynamic Surge Definition and Thresholds
- **Surge Margin:** Minimum allowable distance from active operating point to surge limit line is 10%.
- **Anti-Surge Valve (ASV-101):** Quick-acting fail-open pneumatic recycle valve connecting compressor discharge back to suction scrubber V-102.
- **Surge Detection:** Modulated flow oscillations accompanied by rapid pressure differential fluctuations and acoustic roaring.

### 1.2 Anti-Surge Emergency Response
1. If compressor operating point crosses the Surge Control Line (SCL) or ASV-101 controller fails to open in automatic mode, switch ASV-101 immediately to **MANUAL** and step open to **100% full recycle**.
2. Opening ASV-101 recycles gas from discharge back to suction, instantly boosting suction flow above the surge threshold.
3. Check compressor driver speed (ST-101) and maintain minimum governing speed.
4. Notify control room lead to throttle upstream gas generation or divert feed if prolonged 100% recycle causes discharge gas temperature to rise above 115 °C.

---

## [SOP-K101:SEC-02] Section 2. High Vibration & Mechanical Bearing Protection

### 2.1 Vibration Severity Standards (ISO 10816-3)
- **Normal Baseline Vibration (VT-101):** 1.0 - 2.5 mm/s RMS
- **Vibration Alert Warning (VAH-101):** 3.8 mm/s RMS
- **Vibration Danger Trip (VAHH-101):** 4.5 mm/s RMS (initiates automatic shutdown of driver turbine/motor)

### 2.2 Response to Elevated Vibration
1. Correlate vibration spike with process telemetry:
   - If vibration occurs alongside rapid flow/pressure fluctuations, the cause is **Aerodynamic Surge**. Open ASV-101 immediately.
   - If vibration occurs following high level in upstream scrubber V-102 (LT-103 > 70%), the cause is **Liquid Ingestion / Droplet Impingement** on impeller blades.
2. If liquid ingestion is suspected:
   - Check scrubber drain valve LCV-103 position and ensure manual bypass is open.
   - Immediately reduce compressor speed to idle or trip unit if liquid level in V-102 exceeds LAHH-103 (85%).
3. Dispatch maintenance technician to verify local accelerometer probes and bearing lube oil pressure (PT-201 > 2.2 barg).

---

## [SOP-K101:SEC-03] Section 3. Compressor Interstage Cooling & Suction Scrubber V-102

### 3.1 Suction Scrubber Protection
- Centrifugal compressors cannot compress liquids without catastrophic impeller and seal destruction.
- **Scrubber High Level Alarm (LAH-103):** 60%
- **Compressor Trip High-High Level (LAHH-103):** 80%

### 3.2 Operating Guidelines
1. In the event of carryover from V-101, ensure automated drain valve LCV-103 is operating smoothly.
2. If LCV-103 fails closed, open manual drain valve HV-103B directly to closed drain drum.
3. Verify interstage gas cooler E-101 cooling water flow to keep suction temperature below 45 °C.
