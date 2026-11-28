# Section 8 checklist: approved draft (not yet in the Checklist tab, not yet coded)

Status: decisions and edits approved on 27 Nov 2026. The rows go into the Checklist tab and get coded
**after the blind test on real SDSs has been reviewed**, so the blind test measures the engine as it is now.

Rules for every limit value: it comes from a lookup snapshot, never from memory. Each finding names the
list, its edition and the date checked. Where no lookup exists, the result is "needs verification".

## Sources (fetched and read 27 Nov 2026)

| Source | Edition / version | Used for |
|---|---|---|
| EU REACH Annex II as amended by Reg. 2020/878, Section 8 | as published | EU structure and content (8.1.1.1 to 8.2.3) |
| GB REACH Annex II, Section 8 (legislation.gov.uk) | as it applies in GB | GB structure; 8.1.1 = COSHH 2002 WELs and Control of Lead at Work 2002 OELs; no biological limit item |
| 29 CFR 1910.1200 App D, Table D.1, Section 8 (osha.gov HTML) | source note "77 FR 17884; 89 FR 44459; 91 FR 594-598" | US elements (a) PEL, ACGIH TLV and other limits for all Section 3 ingredients "where available"; (b) engineering controls; (c) individual protection |
| 29 CFR 1910.1200 App C (osha.gov HTML) | source note ends "91 FR 574-594, Jan. 8, 2026" | US PPE statements by class (see 8-B1 to 8-B4) |
| HSE EH40/2005 Workplace exposure limits | Fourth edition 2020 (PDF modified 17 Jan 2020); HSE limits page (updated 24 Feb 2026) says it "contains all updated limits" | GB WELs (8-D1); conversion basis and rounding (paras 68-69) |
| Directive 2004/37/EC, Annex III and IIIa | consolidated 02004L0037-20240408 | EU binding limits and biological limits (8-D2, 8-D4) |
| Directive (EU) 2026/2450 | OJ L 30.10.2026; transposition by 20 Nov 2028 | upcoming limits: PAH mixtures, cobalt, isoprene, 1,4-dioxane; welding fumes; 1,4-dioxane biological limit |
| Directive 98/24/EC | consolidated 01998L0024-20240408 | Art. 3(3): national value "taking into account" the IOELV |
| IOELV Directives 2000/39 (consolidated 02000L0039-20210520), 2006/15, 2009/161, 2017/164, 2019/1831 | no later IOELV directive in Cellar on 27 Nov 2026; remaining 91/322 entries to check when coding | EU indicative limits (8-D3) |
| 29 CFR 1910.1000 Tables Z-1, Z-2, Z-3 (eCFR) | text date recorded per lookup | US PELs (8-D5) |
| NIOSH Pocket Guide | page "last reviewed" date recorded | RELs, sampling methods, respirator recommendations (8-D6, 8-D8, 8-D10) |
| CLP Annex IV, P280 / P282 / P283 / P284 conditions | EU consolidated 1 Jan 2027 = GB (compared) | 8-B1 to 8-B4 |
| HSE HSG53, Table 7 Filter types | Fourth edition 2013 | 8-B6 filter type per contaminant (EN 14387 / EN 143 types) |
| ICSC cards, PREVENTION column | card date recorded | 8-D9 |

### Conversion basis (8-D1, 8-D2, 8-D5)

- EU and GB: mg/m³ at 20 °C and 101.3 kPa (2000/39 and 2004/37 footnotes). EH40 para 68: mg/m³ = ppm × MW / 24.05526.
- US Z-1: ppm "at 25 °C and 760 torr"; a mg/m³ value listed with a ppm value is "approximate", and a mg/m³-only value is exact.
- Where the list gives both ppm and mg/m³, the checker converts with the list's own ratio, so no molecular weight is needed. Otherwise it uses the list's stated basis and the PubChem molecular weight, and names both in the finding.
- Tolerance: a quoted value matches when it equals the list value after rounding to the number of significant figures the SDS quotes, or when it is within half a unit of the list value's last significant figure (EH40 para 69 rounding). A difference explained by converting at the other standard temperature (20 °C vs 25 °C, about 1.6 %) is reported as info. Only a difference clearly beyond these is a fail.

## Rows

Severity per jurisdiction where it differs. "Plan" = status to enter in the Checklist tab.

| ID | Check | Rule or source | Severity | Applies to | Plan |
|---|---|---|---|---|---|
| 8-A1 | Section 8 heading, as the 8th section | Annex II Part B; 1910.1200(g)(2)(viii) | fail | EU, GB, US | coded |
| 8-A2 | Subheadings 8.1 Control parameters and 8.2 Exposure controls | Annex II Part B | fail | EU, GB | coded |
| 8-A3 | US elements (a), (b), (c) all present; "no applicable information" stated where none | App D Table D.1 | fail | US | coded |
| 8-A4 | Empty or "no data" with no reason: one combined finding per section | agreed rule | fail | EU, GB, US | coded |
| 8-A5 | Every limit gives its legal basis (EU: the member state's law; GB: EH40/COSHH 2002 WEL, or Control of Lead at Work 2002) | Annex II 8.1.1 | fail | EU, GB | coded |
| 8-A6 | Limits use the chemical identity from Section 3 (name/CAS) | Annex II 8.1.1 | warning | EU, GB | coded |
| 8-A7 | Each limit has value, unit and reference period; notations kept | 8.1.1.1/8.1.1.2 (Decision 2014/113 Art. 2(3)); EH40 Sk/Sen/Carc | warning | EU, GB, US | coded |
| 8-A8 | Biological limit values given where they exist | 8.1.1.4-8.1.1.5 (EU only) | warning | EU | coded |
| 8-A9 | Monitoring procedures given when a limit is listed | 8.1.2 | warning | EU, GB | coded |
| 8-A10 | DNELs/PNECs given when a REACH registration number or exposure scenario is present | 8.1.4 | warning | EU, GB | coded |
| 8-A11 | Control banding: context and limitations stated | 8.1.5 | warning | EU, GB | coded |
| 8-A12 | Engineering controls specific (LEV, enclosure, closed system). Absent = fail; only generic "adequate ventilation" = warning | 8.2.1; App D (b) | fail / warning | EU, GB, US | coded |
| 8-A13 | Eye protection type named (safety glasses, goggles or face shield) | 8.2.2.2 | fail EU/GB, warning US | EU, GB, US | coded |
| 8-A14 | Gloves: material, thickness and breakthrough time | 8.2.2.2 | fail EU/GB, warning US | EU, GB, US | coded |
| 8-A15 | Body protection type when skin contact is possible | 8.2.2.2 "Other" | warning | EU, GB, US | coded |
| 8-A16 | Respiratory protection names device and filter (type and class) or SCBA | 8.2.2.2 | fail EU/GB, warning US | EU, GB, US | coded |
| 8-A17 | CEN standard cited for each PPE item (EN 166, EN ISO 374-1, EN 14387/143/149, EN 14605/13034) | 8.2.2.2 | warning EU/GB, info US (1910.133/.134/.138) | EU, GB, US | coded |
| 8-A18 | Thermal hazard: PPE construction addressed | 8.2.2.2 Thermal hazards | warning | EU, GB, US | coded |
| 8-A19 | Environmental exposure controls present | 8.2.3 | warning | EU, GB | coded |
| 8-A20 | Refers to Section 5 for firefighting PPE where relevant | 8.2.2.1 | info | EU, GB | coded |
| 8-B1 | PPE items the classification calls for are specified. EU/GB (CLP Annex IV P280): Acute Tox. dermal 1-4 gloves/clothing; Skin Corr. 1 gloves/clothing + eye/face; Skin Irrit. 2 and Skin Sens. 1 gloves; Eye Dam. 1 and Eye Irrit. 2 eye/face; CMR and physical classes: PPE specified. US (App C, verified 27 Nov 2026): same, except Eye Irrit. 2B has no eye-protection statement, and Flam. Liq. 4 (combustible liquid) also carries the PPE statement | P280 conditions; App C C.4.2-C.4.10, C.4.14-C.4.30 | fail | EU, GB, US | coded |
| 8-B2 | Acute Tox. inhalation 1-2 or Resp. Sens. 1: respiratory protection and its equipment specified | P284 conditions; App C C.4.3, C.4.6 (verified, same classes) | fail | EU, GB, US | coded |
| 8-B3 | Ox. Liq. 1 / Ox. Sol. 1: fire-resistant or flame-retardant clothing | P283 conditions; App C C.4.26, C.4.27 Cat 1 (verified) | warning | EU, GB, US | coded |
| 8-B4 | Refrigerated liquefied gas: cold-insulating gloves and face shield or eye protection (links to 7-B14) | P282 conditions; App C C.4.18 (verified) | fail | EU, GB, US | coded |
| 8-B5 | Corrosive (H314/H318) but only "safety glasses" | 8.2.2.2 "based on the hazard"; no binding mapping, needs a person's judgement | warning | EU, GB, US | coded |
| 8-B6 | Filter type covers the contaminant (organic vapour, boiling point above 65 °C: A; at or below 65 °C: AX; inorganic gases: B, not for CO; SO2 and acid gases: E; ammonia and organic derivatives: K; mercury: Hg-P3; nitrogen oxides: NO-P3; particles: P). Combination filters that include the required type (ABEK1, A2P3 etc.) pass; fail only when the required type is absent, or a particle-only filter is given for a vapour. Mixtures: the lowest-boiling organic component listed in Section 3 decides A vs AX. Boiling point from Section 9 or ICSC, named in the finding | HSE HSG53 Table 7 (EN 14387) | fail | EU, GB | coded |
| 8-B7 | CMR 1A/1B: engineering controls specific enough to support the employer's assessment | 8.2.1 (2004/37 Art. 3-5, EU); COSHH ALARP for carcinogens, mutagens, asthmagens (GB, HSE) | warning | EU, GB | coded |
| 8-B8 | Skin notation (EH40 Sk, EU "Skin"): dermal uptake addressed | EH40; 2004/37 Annex III | warning | EU, GB | coded |
| 8-C1 | Section 7.1 and 8.2.1 don't contradict on ventilation or enclosure | Annex II 8.2.1 | warning | EU, GB, US | coded |
| 8-C2 | Section 4.1 first-aider PPE ("see Section 8") covered in Section 8 | consistency | warning | EU, GB, US | coded |
| 8-C3 | Section 6.1 PPE ("see Section 8") covered in Section 8 | consistency | warning | EU, GB, US | coded |
| 8-C4 | Contaminants released in normal use (Sections 7, 10) have their limits in 8.1.3 | 8.1.3 | warning | EU, GB | coded |
| 8-C5 | "Not hazardous / no PPE required" contradicts the Section 2 classification | Annex II 0.2.4; (g)(5) | fail | EU, GB, US | coded |
| 8-C6 | 8.2.1 relates to the uses identified in 1.2 | 8.2.1 | info | EU, GB | coded |
| 8-D1 | Each Section 3 CAS with an EH40 WEL is listed; values and notation match (conversion and tolerance as above) | EH40/2005 4th ed. 2020 | fail (missing, or clearly beyond rounding); info (within the conversion-basis difference) | GB | coded |
| 8-D2 | Each Section 3 CAS with an EU binding limit is listed, stated value not above it; transitional values by date; 2026/2450 values reported as upcoming until 20 Nov 2028 | 2004/37 Annex III; Art. 1(1) minimum requirements | fail; info for upcoming and within-tolerance differences | EU | coded |
| 8-D3 | Each Section 3 CAS with an EU indicative limit has a national value listed. Missing = fail; a different value = info (member states only "take into account" the EU value, and the national list is manual, 8-D13) | 98/24 Art. 3(3); IOELV directives | fail / info | EU | coded |
| 8-D4 | EU biological limits (lead; 1,4-dioxane once 2026/2450 applies) | 2004/37 Annex IIIa | warning | EU | coded |
| 8-D5 | A PEL given for every Section 3 ingredient that has one, value matches (conversion and tolerance as above); substance-specific standards (1910.1001-1052) take precedence | 1910.1000 Z-1 to Z-3 | fail (missing, or clearly beyond rounding); info otherwise | US | coded |
| 8-D6 | NIOSH REL: warning if quoted but different; info if absent | NIOSH Pocket Guide | warning / info | US | coded |
| 8-D7 | ACGIH TLV present and correct (App D (a) requires it where available). ICSC's copies of TLVs are not used | licensed list | (manual) | US | manual: ACGIH TLVs are licensed |
| 8-D8 | Suggest NIOSH/OSHA method numbers when 8.1.2 is empty | NIOSH Pocket Guide | info | EU, GB, US | coded |
| 8-D9 | PPE consistent with the ICSC card's prevention advice (inhalation, skin, eyes) | ICSC | warning | EU, GB, US | coded |
| 8-D10 | US cartridge type consistent with the NIOSH respirator recommendation | NIOSH Pocket Guide | warning | US | coded |
| 8-D11 | Glove material suits the substance; breakthrough time right | manufacturer data; EN ISO 374 is paid | (manual) | EU, GB, US | manual: needs glove manufacturer data |
| 8-D12 | DNEL/PNEC values match the registration dossier | ECHA CHEM | (manual) | EU | manual: ECHA CHEM refuses automated access |
| 8-D13 | Other national limits (8.1.1.3: TRGS 900, INRS etc.); GESTIS International Limit Values | member state's list | (manual) | EU | manual: needs the member state's national list |
| 8-D14 | Lead limit under Control of Lead at Work 2002 | legislation.gov.uk | fail | GB | not yet coded |
| 8-J1 | Legal basis fits the jurisdiction (GB SDS citing IOELVs or TRGS; EU SDS citing EH40) | Annex II 8.1.1 EU vs GB | warning | EU, GB | coded |

### Coverage statement on every Section 8 limit finding (8-D1 to 8-D6)

For a mixture, Section 3 may legitimately omit ingredients (Annex II 3.2 thresholds; US trade-secret and
concentration rules). The limit checks can only cover the ingredients listed, so each finding and the
Section 8 summary say: "Limit coverage checked for the N ingredients listed in Section 3 only; ingredients
not disclosed in Section 3 were not checked."

## Decisions recorded (27 Nov 2026)

1. 8-D3: a national value different from the EU indicative limit is info.
2. ICSC's copies of ACGIH TLVs are not used.
3. 8-B5 stays a warning.
4. 8-B1/8-B2 US: verified against App C on osha.gov (see 8-B1 for the two US differences).
