# Fix round 1 (27 Nov 2026): results on the 8 tuning SDSs

These 8 SDSs (blind batches 1 and 2) were used to design the fixes, so the numbers below show that the fixes do
what they were meant to. They are not a fair accuracy measure: that is the job of the fresh holdout batch.
Verdicts are Claude's; the user reviews the fails below before any blind-test expectations are frozen.

## What changed

1. Concentration and physical-form gating of reference data (`tools/refgate.py`, `config/reference_gating.json`).
2. One text-interpretation module used by every rule (`tools/textinterp.py`): negation, "no data" phrases,
   cross-references, synonyms, "such as" lists. Unit tests in `tests/`.
3. The six bugs (Section 14 class, H304 read as H300, "delayed effects: Not available", ERG caveats, Section 12
   prose as classification, 10-C4 without PubChem formulas) and layout parsing (page furniture, UFI fragments,
   label-style first-aid routes, heading and text on one line, sub-subsections, non-standard Section 10 numbering).
4. Report: product name, revision/issue/preparation date, reference-data coverage warnings, list of gated data.

## Before and after (fails + warnings)

| | Before | After |
|---|---|---|
| Findings (fail + warning) | 90 | 56 |
| Clearly wrong (Claude's verdict) | 32 (36 %) | 0 |
| Debatable | 11 | 5 (Nautra 6-A6; cleaner 10-D1; Epoxyline 10-D1, 10-D6, 7-D1) |
| Correct but low value | 1 | 1 (Nautra 10-D1, "name fluorine") |
| Fails | 14 (6 wrong) | 10 (0 wrong, 1 debatable) |

No finding judged correct before the fixes was lost, except two low-value ICSC storage items from ingredients
below 1 % (ATF ICSC 1431; remover ICSC 0654).

Real gaps found only after the fixes: 10-A5 on the aerosol ("No additional information available") and on
Epoxyline ("No specific data" in 10.4/10.5); 7-C1 on the Nautra film (no segregation in 7.2 from the oxidisers in
its "Materials to avoid"); 5-C2 and 4-A10 on the aerosol.

## Fails for the user's review (14 from the blind test, plus 2 new)

| # | SDS | Check | What the engine said (blind test) | Claude's verdict | After the fixes |
|---|---|---|---|---|---|
| 1 | Vickers (1.6 % HCl) | 10-A5 | 10.1 and 10.3 "No data available" with no reason | correct | fail (unchanged) |
| 2 | Vickers | 10-D1 | 10.5 lists only alkalis; violent reactions recorded with acids, ammonia, metals | wrong (gas card; 1.6 %) | info |
| 3 | Nautra film | 10-A3 | US elements missing: "incompatible, decomposition" | right verdict, wrong elements | fail: "reactivity, reactions" |
| 4 | Nautra film | 10-A9 | stability not stated | wrong (stated under 10.1) | removed |
| 5 | Nautra film | 5-C2 | 40-45 % PVC, but no hydrogen chloride among combustion products | correct | fail (unchanged) |
| 6 | Nautra film | 5-A3 | US firefighter element missing | wrong (protective suit + SCBA given) | removed |
| 7 | Domino ink | 10-D1 | 10.5 names nothing; acids, air, oxidisers, combustibles recorded | right verdict; air/combustibles from carbon black | fail, families from the main acrylates only |
| 8 | Domino ink | 4-B7 | 4.3 lacks the specific treatment P321 refers to | wrong (P321 via skin classes) | removed |
| 9 | Cleaner | 10-A5 | 10.1 "not available" (10.3 "Unknown") with no reason | correct | fail (unchanged) |
| 10 | Epoxyline | 10-D1 | 10.5 "No specific data"; air, acids, oxidisers recorded | debatable (1-methoxy-2-propanol ≤10 % counts as ≥10 %) | fail |
| 11 | Remover | 10-D1 | 10.5 oxidisers only; air, bases recorded | right verdict; acids from ≤0.3 % ingredient | fail, from dioxolane and methylal only |
| 12 | Aerosol | 10-D1 | 10.5 "No additional information available"; butane etc. react with oxidisers | correct | fail (unchanged) |
| 13 | Aerosol | 5-D1 | ERG "DO NOT USE water" vs foam | wrong (LNG caveat) | removed |
| 14 | ATF | 4-A6 | ingestion route missing | wrong (label not parsed) | removed |
| 15 | Aerosol | 10-A5 | 10.1 and 10.5 "No additional information available", no reason | correct (missed before) | new fail |
| 16 | Epoxyline | 10-A5 | 10.4 and 10.5 "No specific data", no reason | correct (missed before) | new fail |

## Still open

- Domino ink: CAMEO records exothermic addition polymerisation for the main acrylate, and 10.3 says "No potentially
  hazardous reactions known"; 10-D6 reports only peroxide formation because it keeps one reference statement per
  record. Not changed in this round.
- Threshold edge: "≤ 10 %" counts as 10 % and so as a main ingredient (config/reference_gating.json).

## User review of the 16 fails (27 Nov 2026) and resulting changes

- Agreed: rows 1, 3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 16.
- Row 2: info agreed; the metals item becomes a warning when the product is classified corrosive to metals (H290).
- Row 10: disagreed. Threshold changed to "> 10 %" (so "≤ 10 %" is a 1-10 % ingredient), and a new rule: for a mixture
  with no hazard classification, findings based only on reference data are capped at warning. Row 10 is now a warning.
- Rows 3, 7, 11, 12 checked against the SDS text by Claude, as asked:
  - 3 (Nautra 10-A3): confirmed; Section 10 has only Stability, Conditions to avoid, Materials to avoid, Decomposition.
  - 7 (Domino 10-D1): confirmed; HDDA (50-60 %) autoxidises in air to explosive peroxides (CAMEO 20479), isodecyl acrylate
    (10-20 %) reacts vigorously with strong oxidising acids (CAMEO 8752); 10.5 names nothing.
  - 11 (remover 10-D1): confirmed; methylal (10-25 %) "reacts vigorously with strong oxidants and strong bases. This generates
    fire and explosion hazard" (ICSC 1152); 10.5 lists only oxidising materials.
  - 12 (aerosol 10-D1): **edited**. The only fail item ("air") came from "BUTANE can explode ... when mixed with
    (nickel carbonyl + oxygen)" (CAMEO 5668), a specific reagent combination. Parenthetical combinations are no longer read as
    families; the finding is now a warning (oxidisers and other incompatibles not listed in 10.5).
- 10-D6 keeps every statement in a record (peroxide formation and polymerisation). The Domino ink's acrylate polymerisation is
  now flagged. Polymerisation counts only when the substance itself polymerises ("may initiate the polymerization of
  isocyanates" does not count).

Side effects to note: with peroxide formation kept for 1-10 % ingredients (as agreed for high-hazard data), 10-D6 now also
fires for propan-2-ol (≤ 5 %) in the cleaner and 2-butoxyethanol (≤ 2.5 %) in the aerosol. Claude counts both as debatable.

Expectations for these 8 SDSs are frozen in local/blind_test/ (git-ignored): `python3 -I tools/run_regression.py --cases local/blind_test/cases.json`.

## Follow-up decision (27 Nov 2026)

10-D6 for 1-10 % ingredients: peroxide-formation data count as a warning only if the mixture carries EUH019 or the ingredient
is a known strong peroxide former (`config/reference_gating.json` → `strong_peroxide_formers`); otherwise info. The list is
empty until a cited source is added (Prudent Practices could not be fetched from this environment). Effect: 10-D6 is info on
the cleaner (propan-2-ol), Epoxyline (1-methoxy-2-propanol) and the aerosol (2-butoxyethanol). Local expectations updated.
