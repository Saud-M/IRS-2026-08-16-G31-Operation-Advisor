

## SECTION 1 : PROJECT TITLE
## Operation Advisor


---

## SECTION 2 : EXECUTIVE SUMMARY / PAPER ABSTRACT

Control room operators in upstream and midstream oil and gas facilities rarely deal with isolated single-sensor anomalies. When a disturbance hits a primary production train, thermodynamic and fluid coupling propagates that upset across multiple vessels within seconds. A sticking pressure control valve on a high-pressure separator raises vessel back-pressure, which alters gas velocity through the overhead wire-mesh demister pad, starves the downstream centrifugal compressor of suction flow, and pushes the compressor toward aerodynamic surge.
During these transients, panel operators face two simultaneous problems. First, the Distributed Control System (DCS) generates a cascade of secondary threshold alarms that obscure the initiating mechanical or process root cause. Second, standard operating procedures (SOPs) and Hazard and Operability (HAZOP) dossiers are stored as static multi-page manuals. Looking up the exact clause for a specific valve bypass or chemical dosing rate while watching vessel pressure climb toward an Emergency Shutdown (ESD) trip threshold creates severe cognitive strain.
At the same time, petroleum production facilities operate under strict functional safety standards—specifically IEC 61511 and OSHA Process Safety Management (PSM) 29 CFR 1910.119. Because unverified software actions can cause catastrophic vessel overpressure, rotating equipment destruction, or hydrocarbon release, an AI system cannot be wired directly to open or close field valves. Nor can operators rely on an ungrounded conversational language model that might invent non-existent valve tags or suggest venting gas to flare when safe mechanical alternatives exist.
To address this gap, Group 31 developed the Operation Advisor for Oil & Gas Operations. Rather than acting as an autonomous controller, the platform functions strictly as a read-only Human-in-the-Loop (HITL) supervisory decision-support system for Central Processing Facility (CPF) Train 1. It combines deterministic symbolic reasoning, probabilistic machine learning, state-space planning, evolutionary optimization, multimodal operator input processing, and citation-verified Retrieval-Augmented Generation (RAG) running on an air-gapped local Ollama (`llama3.2`) language model.
 

---

## SECTION 3 : CREDITS / PROJECT CONTRIBUTION

| Official Full Name  | Student ID (MTech Applicable)  | Work Items (Who Did What) |
| :------------ |:---------------:| :-----|
| Ayman Alshammari | A0353094A | Symbolic Reasoning, Ontology & Governance|
| Saud Almbdal | A0351051W | Process Physics, Supervised ML, Bayesian Inference & Safety Gate|
| Mohammed Aldawsari | A0354107L | | A1234567C@outlook.com |
| Muhannad Al Masad | A0353434H | Multimodal Cognitive Pipeline, Grounded RAG, Local Ollama LLM & Web Cockpit|


---

## SECTION 4 : VIDEO OF SYSTEM MODELLING & USE CASE DEMO

[Technical Presentation](https://www.youtube.com/watch?v=HJAkGgq074g)

[Business Presentation & Video Demo](https://www.youtube.com/watch?v=N82LX3bYCdo)


---

## SECTION 5 : USER GUIDE

`Refer to appendix <Installation & User Guide> in project report at Github Folder: ProjectReport`


---
## SECTION 6 : PROJECT REPORT / PAPER

`Refer to project report at Github Folder: ProjectReport`


---


