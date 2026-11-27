# Blind test, batch 2 (5 EU/Ireland SDSs, all mixtures), 27 Nov 2026

Engine as merged in main (21be6b7) plus the Section 8 draft commit (no rule changes). Live lookups.
Verdicts are the reviewer's judgement against the SDS text; a competent person should confirm.

| SDS | Classification | S10 | S4 | S5 | S6 | S7 | Total F/W |
|---|---|---|---|---|---|---|---|
| Cleanfast HR 511 Glass & Stainless Steel Cleaner, rev 25 May 2025 | not classified (<5% propan-2-ol) | 1F 4W | 1W | — | 4W | 3W 1I | 1F 12W |
| Watco Epoxyline Resin, rev 03/05/2023 | not classified | 1F 2W 1I | 1W | 1W | — | 1W | 1F 5W |
| Rust-Oleum Paint & Varnish Remover, rev 28/04/2021 | Flam. Liq. 2, Eye Dam. 1, Aq. Chr. 3 | 1F 3W 1I | 4W | 1W | — | 2W | 1F 10W |
| MPM Contact Spray Aerosol A300, rev 19/02/2026 | Aerosol 1 | 1F 3W 1I | 3W | 1F 1W | — | 5W | 2F 12W |
| 77 Lubricants ATF ULV Red, rev 16/07/2026 | Asp. Tox. 1 | 3W 1I | 1F 3W | — | 1W | 4W 1I | 1F 11W |

56 fails + warnings: 24 correct, 22 clearly wrong, 7 debatable, 3 right verdict for partly wrong reasons.
Fails (6): 2 correct, 2 wrong, 1 partly right, 1 debatable.

## Clearly wrong (22)

| SDS | Check | Why |
|---|---|---|
| Cleaner | 10-D1 W | Propan-2-ol data (chlorine, air, aldehydes) applied to a <5% aqueous cleaner (concentration) |
| Cleaner | 6-C2 W | 6.1 says "Follow the instructions in Sections 7 and 8"; the cross-reference covers 8.2's respirator advice |
| Cleaner | 6-D1 W | ICSC "remove ignition sources" for <5% propan-2-ol in water, flash point 63 °C (concentration) |
| Cleaner | 7-D1 W | ICSC "fireproof" storage for the same (concentration) |
| Epoxyline | 5-C6 W | Bug: Section 14 regex read "hazard class(es) 14.4" as class 1 (product is not regulated) |
| Epoxyline | 4-C4 W | Fired on "Potential delayed effects: Not available"; Section 11 records no delayed effects |
| Epoxyline | 7-D1 W | ICSC "fireproof" for ≤10% 1-methoxy-2-propanol in an unclassified resin (concentration) |
| Remover | 10-A16 W | Nanoform rule fired on "This product does not contains nanomaterials" (negation ignored) |
| Remover | 4-C1 W | P353 "Rinse skin with water" vs 4.1 "Flush contaminated skin with plenty of water" (synonym) |
| Remover | 4-C2 W | "Symptoms missing for H318", but 4.2 lists pain, watering, redness for eyes |
| Remover | 4-C4 W | Same "Potential delayed effects: Not available" trigger |
| Remover | 5-C6 W | Same Section 14 bug (product is class 3) |
| Aerosol | 5-D1 **F** | CAMEO's ERG excerpt "DO NOT USE water" is the LNG pool-fire caveat, not butane; foam is fine |
| Aerosol | 7-A5 W | Hygiene advice present (no eating/drinking/smoking, wash hands); rule demands every Annex II example |
| ATF | 10-C2 W | 10.4 says "None under recommended storage and handling conditions (see section 7)"; cross-reference ignored |
| ATF | 10-D1 W | Acids, bases, halogenated compounds, water: from naphthalene (<0.1%) and minor oils (concentration) |
| ATF | 4-A6 **F** | "Routes given: none", but 4.1 has "First-aid measures after inhalation / skin / eye / ingestion"; labels not parsed |
| ATF | 4-B1 W | "Do NOT induce vomiting" missing, but 4.1 ingestion says "Do not induce vomiting" (same parsing failure) |
| ATF | 4-D3 W | Lung oedema from ICSC 1431 (a 0.3-1% oil) (concentration) |
| ATF | 6-A4 W | Large/small spill rule triggered by a phantom H300 (see bugs) |
| ATF | 7-A5 W | Same "every example" problem |
| ATF | 7-D1 W | ICSC 0667 naphthalene (<0.1%) "area without drain access" (concentration) |

## Debatable (7)

| SDS | Check | Why |
|---|---|---|
| Cleaner | 4-A7 W | 4.1 opens "Take care of your own safety"; arguably covers first-aider protection |
| Epoxyline | 10-C2 W | "Protected from direct sunlight", "cool" in 7.2 is generic; 10.4 "No specific data" |
| Epoxyline | 10-D1 **F** | 10.5 "No specific data" with benzyl alcohol ≤5% and PGME ≤10%: oxidisers is a fair point, fail is strong at these concentrations |
| Epoxyline | 10-D6 W | Peroxide formation from PGME at ≤10% in a resin |
| Remover | 10-C2 W | Sunlight, same boilerplate pattern |
| Remover | 4-A9 W | Oxygen "by trained personnel" in 4.1 |
| Aerosol | 5-C6 W | Leaking-gas-fire advice for an aerosol dispenser (UN 1950, label 2.1); P377 is not assigned to aerosols |

## Right verdict, partly wrong reasons (3)

| SDS | Check | Why |
|---|---|---|
| Remover | 10-D1 **F** | Bases and peroxide formation (methylal 10-25%) are real gaps; acids/acid chlorides come from 2-dimethylaminoethanol at ≤0.3% |
| Aerosol | 4-D1 W | Eye rinsing really is missing (4.1 eyes: "If eye irritation persists: Get medical advice"); "remove contaminated clothes" is already there |
| Aerosol | 7-B11 W | Fired on an H412 inferred from Section 12 prose ("Harmful to aquatic life...") although the SDS says not classified. The 7.1.1 gap (no release-to-environment advice) is real, but that is 7-A4. The Section 2/12 contradiction is a real SDS defect for those sections |

## Correct (24)

Cleaner: 10-A5 F, 10-A7, 10-A8, 7-C1, 6-A5, 6-A6, 7-A4, 7-A5 (hygiene advice is only in 8.2).
Remover: 10-B2 (static discharge missing from 10.4), 7-D1 ×2 (fireproof; no drain access: fit a Flam. Liq. 2 product).
Aerosol: 10-A7, 10-A13, 10-B3 (container may burst if heated), 10-D1 F (no incompatibles for a flammable-propellant aerosol), 4-A7, 4-C4, 7-B7 (50 °C limit from P410+P412 missing), 7-D1 ×2.
ATF: 7-C1, 4-A7, 7-A4, 7-D1 (separate from oxidisers).

## Engine bugs found in batch 2

1. 5-C6: `hazard class(es)\s*(\d)` captures the next subheading ("14.4") as the class.
2. H304 wording "May be fatal if swallowed and enters airways" matches the H300 text pattern, adding a phantom H300 (drives 6-A4, 7-C4 info).
3. 4-C4 treats the heading "Potential delayed effects" as delayed effects even when the value is "Not available".
4. 5-D1 reads ERG excerpt caveats for other materials as applying to this substance.
5. Section 12 prose adds hazard codes (H412) even when Section 12 also says "Not classified".
6. Hazard-code extraction picks "H039" out of a UFI (3VD1-H039-E00E-U8SQ); no rule consumed it this time.

## Possible misses

- Aerosol: 10.1 and 10.5 say "No additional information available" with no reason; 10-A5 (agreed fail) did not fire.
- Remover: 1,3-dioxolane (50-75%) has no ICSC/CAMEO/NIOSH record by CAS, so no reference data at all for the main ingredient; reported only as "not found".

## Tool issues

- Product name "not found" on all five reports (header regex).
- Page footers ("Date of issue/Date of revision ... Version", "16/07/2026 (Revision date) IE - en 3/18") inside section text and finding excerpts.
- PubChem "No CID found" (UVCB substances) still labelled "unreachable".
