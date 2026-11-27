# Blind test, batch 1 (3 SDSs), 27 Nov 2026

Engine as merged in main (21be6b7), no rule changes. Live lookups.
Verdicts are the reviewer's (Claude's) judgement against the SDS text; the fails are pending the user's review.
The fourth uploaded file was a CSV export of the Sheet's Resources tab, not an SDS, and was not run.

| SDS | Run as | S10 | S4 | S5 | S6 | S7 | Total F/W |
|---|---|---|---|---|---|---|---|
| Vickers Laboratories, Colour Standard Reagent 200 Hazen (1.6% HCl, not classified), rev 23 Feb 2021 | GB, mixture (detected GB) | 2F 4W | 3W 1I | 1W | 1W | 3W | 2F 12W |
| Nautra Media, Flat dot Matte inkjet film (Korean supplier), prepared 12 Jun 2017 | US, mixture (detected US; not written for EU/GB/US) | 3F 2W 1I | 1I | 1F 1W | 1W | — | 4F 4W |
| Domino UK, IE-UV90BK UV printing ink (Repr. 1B, Skin Sens. 1), rev 28 Oct 2021 | GB, mixture (detected GB) | 1F 3W | 1F 4W | — | 1W | 2W 1I | 2F 10W |

34 fails + warnings: 16 correct, 10 clearly wrong, 4 debatable, 3 right verdict for partly wrong reasons, 1 correct but low value.
Fails (8): 2 correct, 4 wrong, 2 partly right.

## Clearly wrong (10)

| SDS | Check | Why |
|---|---|---|
| Vickers | 10-D1 **F** | CAS 7647-01-0 was looked up as hydrogen chloride gas (ICSC 0163) and refrigerated liquid HCl (CAMEO); the product is 1.6% in water. Acids/ammonia not meaningful; metals plausible at most as a warning |
| Vickers | 4-D1 W | Same gas card; also 4.1 eyes already says "OBTAIN MEDICAL ATTENTION" (wording mismatch with "refer for medical attention") |
| Vickers | 4-D3 W | Delayed lung oedema from the gas card |
| Vickers | 7-D1 W | "Fireproof" storage from the gas card |
| Nautra | 10-A9 **F** | Stability is stated ("Stable under ordinary conditions") under non-standard numbering (10.1 Stability, 10.2 Conditions to avoid, ...) |
| Nautra | 5-A3 **F** | 5.3 "Fire fighting Instructions: wear protective suit and self-contained breathing apparatus"; pattern needs "firefighter"/"protective equipment" |
| Nautra | 5-A6 W | Same text; heading and content share a line and the heading line is dropped |
| Domino | 10-C4 W | Bug: elements taken only from formulas printed in the SDS and element words in names; PubChem formulas ignored |
| Domino | 4-B7 **F** | P321 is assigned via Skin Irrit. 2 / Skin Sens. 1, where the CLP Annex IV condition is a cleansing agent, not an antidote |
| Domino | 7-A5 W | Annex II 7.1.2 "such as" examples treated as mandatory; hygiene advice present (and "wash hands" in 8.2) |

## Debatable (4)

| SDS | Check | Why |
|---|---|---|
| Vickers | 10-C2 W | "Cool" storage read as "heat" being a condition to avoid (non-flammable aqueous solution) |
| Nautra | 6-A6 W | Solid film; "no special procedures" arguably covers clean-up |
| Domino | 4-A9 W | Oxygen already limited to "properly trained personnel" |
| Domino | 7-C3 W | 7.1 silent on ventilation; silence is not a contradiction with 8.2 |

## Right verdict, partly wrong reasons (3)

| SDS | Check | Why |
|---|---|---|
| Nautra | 10-A3 **F** | Reactivity and hazardous reactions really are missing; but it named "incompatible" and "decomposition" (present as "Materials to avoid", "Hazardous decomposition product") |
| Domino | 10-D1 **F** | Oxidisers / polymerisation are a real gap for an acrylate ink; "air" and "combustibles" come from the carbon black dust card (dispersed pigment) |
| Domino | 4-C1 W | P362 really missing; P352 "wash" vs "rinse with plenty of water" is too literal |

## Correct but low value (1)

Nautra 10-D1 W: "name fluorine explicitly" (follows the agreed rule; noise for an inkjet film).

## Correct (16)

Vickers: 10-A5 F, 10-A7, 10-A8, 7-C1, 4-A10, 5-A6, 6-A5, 7-A4, 7-A5.
Nautra: 5-C2 F and 10-C5 (40-45% PVC: hydrogen chloride missing from combustion/decomposition products).
Domino: 10-C2 (7.2 "protect from sunlight" vs 10.4 "no conditions"), 10-D6, 4-B3 (contact lenses, P305+P351+P338), 4-C4, 6-A5.

## Possible misses

- Domino Section 10: acrylate monomers (CAMEO: very exothermic addition polymerisation) but 10.3 "No potentially hazardous reactions known"; 10-A11 fires only when the SDS itself mentions polymerisation.
- Nautra: 5.2 "Not applicable" vs CO/CO2 in its 10.4; 5-C1 did not fire (numbering).

## Tool issues

- Product name not found on 2 of 3 reports; Nautra has a preparation date but no revision date.
- PubChem "No CID found" (polymers, UVCBs) labelled "unreachable".
