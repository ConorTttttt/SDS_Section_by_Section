# P-statement calculator verification (ConorTttttt/Classification), 28 Nov 2026

Read-only review of `verification/engine.js` on `main` (be42ceb), with the open PR #6 branch
(`feature/complete-annex-iv-p-statements`, e5f63cc) checked the same way. The proposed fixes are a separate pull request
(`claude/annex-iv-p-statement-table`); nothing is merged.

## How expectations were derived

- **Source:** the consolidated CLP text (CELEX 02008R1272-20270101; Annex IV Part 1 identical in 02008R1272-20260701),
  extracted by `tools/legal_tables.py` into `data/legal/`. Reuse under the Commission's EUR-Lex policy: the tables are
  extracted and restructured; the wording is unchanged.
- **Expected statements** per hazard class and category come from Annex IV Part 1 rows. They are graded by the
  "conditions for use" column:
  - **required:** no condition, or wording-only instructions such as "Manufacturer/supplier to specify";
  - **conditional:** "— if …", "— for …", "— except …";
  - **optional:** consumer-only rows for non-consumer supply, and "omit where … is used".
- **ED, PBT/vPvB and PMT/vPvM** have no Annex IV Part 1 rows; their statements come from the Annex I label tables.
- **Comparison is by component.** For example, P301+P310 counts as P301 and P310, because Annex IV lists both the
  combinations and their parts. Opening clauses ("IF SWALLOWED:") count only inside a combination.
- **Self-check of the extraction:** the Annex IV extraction was compared with the separately parsed Annex I label tables
  (95 columns). They agree except for six differences in the legal text itself:

  | Hazard class | Annex I label table | Annex IV Part 1 |
  |---|---|---|
  | Explosives | P501 | P503 |
  | Self-heating | (no P410) | P410 |
  | Effects on or via lactation | (no P202) | P202 |
  | CMR | P201, no condition | P201 for consumer products only, omitted where P202 is used |
  | Skin corrosion | Category 1 shares the 1A/1B/1C column | some rows list Category 1, others do not |
  | Skin irritation | — | the P313 row lists Category 3, which EU CLP does not have |

  Where Annex I and Annex IV differ, the tests accept either reading.
- **Harness:** `tools/verify_p_calculator.py` with `tools/pcalc_harness.js`. It runs the engine's `selectArticle28`
  once per class/category (114 rows) and once per case (27: 4 supplier, 15 synthetic, 8 blind). The case rows use the
  case's Section 2 H-codes.
- **Not checked against:** ECHA's *Guidance on labelling and packaging*. echa.europa.eu answers automated requests with
  a bot challenge, so the Article 28 points below are judged against Articles 22 and 28 and Annex IV only. Upload the
  guidance PDF if you want that comparison.

## Results

| | main | PR #6 | fix PR |
|---|---|---|---|
| Existing Node suites | 21/21 pass (Art. 28: 50, Art. 26: 49, engine: 223) | own suites pass (Art. 28: 103, Art. 26: 49, engine: 221) | 22/22 pass (Art. 28: 51, Annex I cross-check: 105) |
| Class/category rows passing (all 114) | 5 | 68 | 114 |
| Calculated classes passing (62 rows) | 5 | 49 | 62 |
| Rows with an ineligible statement | 0 | 15 | 0 |
| Rows missing a required statement | 109 | 43 | 0 |
| Cases passing (27; 4 have no H-codes) | 8 | 21 | 27 |

Per-row tables: [main](calculator_verification/test_table_main.md), [PR #6](calculator_verification/test_table_pr6.md),
[fix](calculator_verification/test_table_fix.md).

The fix PR's 114/114 is measured against the same Annex IV data that the fix embeds, so it shows the wiring is right
rather than giving an independent check. The independent check is the fix PR's
`verification/test_annex_iv_table.js`, which compares the engine's candidates with the Annex I label tables.

With H-codes only and no class label, 105 of 114 rows pass. The other 9 involve H-codes shared by several classes:

| H-code | Classes that share it | Statement that depends on the class |
|---|---|---|
| H240, H241, H242 | organic peroxide, self-reactive | P410 (organic peroxides only) |
| H250 | pyrophoric liquid, pyrophoric solid | P335 (solids only) |
| H261 | water-reactive Category 2, Category 3 | P223, P302+P335+P334 (Category 2 only) |

For these the fix holds the class-specific statements as "class to confirm".

## Coverage (main)

- **Classes the calculator computes:** flammable liquids 1–3; acute toxicity oral, dermal and inhalation 1–4; skin
  corrosion 1/1A/1B/1C; skin irritation 2; eye damage 1; eye irritation 2; respiratory and skin sensitisation 1/1A/1B;
  Muta., Carc. and Repr. 1A/1B/2; lactation; STOT SE 1/2/3; STOT RE 1/2; aspiration 1; aquatic acute 1 and chronic 1–4;
  ozone 1; ED HH and ED ENV 1/2; PBT, vPvB, PMT, vPvM.
- **Other physical classes** reach Article 28 only as manual H-code entries.
- **P-statements it can output:** 21 of the 129 in Annex IV Part 1:
  - general: P101, P102, P103;
  - prevention: P202, P210, P260, P261, P273, P280;
  - response: P301+P310, P301+P312, P301+P330+P331, P302+P352, P303+P361+P353, P304+P340, P305+P351+P338, P308+P313,
    P331, P333+P313, P337+P313;
  - disposal: P501.
- **Missing statements that matter for SDS Sections 4–7 and 10:**

| SDS section | Missing statements (main) |
|---|---|
| 4 First aid | P310, P311, P312, P314, P315, P320, P321, P330, P332+P313, P342+P311, P308+P311, P361+P364, P362+P364, P363, P302+P334, P302+P335+P334, P306+P360, P336+P315 |
| 5 Firefighting | P370+P378, P370+P372+P380+P373, P370+P380+P375(+[P378]), P371+P380+P375, P370+P376, P377, P381 |
| 6 Accidental release | P390, P391 |
| 7 Handling and storage | P201, P233, P240–P243, P262, P263, P264, P270, P271, P272, P401, P402+P404, P403, P403+P233, P403+P235, P405, P406, P407, P410+P412, P411, P413, P420 (and P284, P282, P283 for Section 8) |
| 10 Stability and reactivity | P210 for every class except flammable liquids; P211, P212, P220, P222, P223, P230, P231+P232, P234, P235, P250, P251, P410, P411, P412, P420 |
| 13 Disposal | P502 (ozone), P503 (explosives) |

## Findings

Severity: **error** = wrong output; **omission** = an eligible statement is not produced; **judgement call** = a choice
the law leaves open. Line numbers are `verification/engine.js` on main unless marked PR #6.

| # | Severity | Where | What | Legal basis | Expected behaviour |
|---|---|---|---|---|---|
| 1 | omission | `P28_RULES` 1050–1072 | Catalogue holds 21 of 129 statements. Every calculated class except aquatic chronic 3/4 misses at least one statement it requires. | Art. 22(2), Annex IV Part 1 | Generate candidates from the full Annex IV table (fix PR) |
| 2 | omission | 1056 (P280) | P280 not triggered by acute toxicity dermal 1–4 (H310/H311/H312). Not triggered by physical classes either (manual entries). | Annex IV 6.2, P280 rows for "Acute toxicity — dermal 1, 2, 3, 4" ("Specify protective gloves/clothing") | P280 for H310–H312 |
| 3 | omission | 1063 (P302+P352) | Not triggered by acute dermal 1–4 (H310–H312) | Annex IV 6.3, P302+P352 rows for acute dermal 1–4 | P302+P352 for H310–H312 |
| 4 | omission | 1058 (P261) | Not triggered by acute inhalation 3 (H331) | Annex IV 6.2, P261 rows for acute inhalation 3, 4 | P261 for H331 (omittable where P260 is given) |
| 5 | omission | 1069 (P304+P340) | Not triggered by skin corrosion (H314) | Annex IV 6.3, P304+P340 rows for skin corrosion 1A, 1B, 1C | P304+P340 for H314 |
| 6 | omission (conditional) | 1059 (P260) | Not offered for H314 | Annex IV 6.2, P260 rows for skin corrosion: "if inhalable particles of dusts or mists may occur during use" | Offer P260 for H314, held until the condition is confirmed |
| 7 | omission | 1054 (P210) | P210 only for flammable liquids | Annex IV 6.2, P210 rows for explosives, flammable gases, aerosols, flammable solids, self-reactive, pyrophoric, oxidising liquids/solids, organic peroxides, desensitised explosives | P210 for those classes (manual entries) |
| 8 | omission | 1071 (P501) | No disposal statement for self-reactive, water-reactive, oxidisers, organic peroxides, desensitised explosives. No P502 for ozone; no P503 for explosives. | Annex IV 6.5; Annex I Table 5.2 (ozone: P502) | P501/P502/P503 per Table 6.5 |
| 9 | omission | 1079 (`/^H\d{3}/` filter) | ED, PBT/vPvB, PMT/vPvM (EUH380–EUH451) get no P-statements | Annex I Tables 3.11.3, 4.2.3, 4.3.1, 4.4.1 (e.g. ED HH 1: P201, P202, P263, P280, P308+P313, P405, P501) | Statements from those tables (fix PR) |
| 10 | error (minor) | 1056 (P280 text) | Wording lacks "hearing protection/". Displayed only when no PPE is entered. | Annex IV Part 1 P280: "Wear protective gloves/protective clothing/eye protection/face protection/hearing protection/…" | Annex IV wording |
| 11 | omission | consumer disposal, 1130–1146 | Consumer ozone product (H420): no disposal statement, so a blocker is raised | Art. 28(2); Annex I Table 5.2 lists P502 | Accept P502 as the disposal statement |
| 12 | judgement call | 1186–1190 (only two redundancy pairs) | H314 + H304 proposes P331 beside P301+P330+P331, so "Do NOT induce vomiting." appears twice | Art. 28(1): clearly redundant statements are omitted | Flag for review (fix PR adds a review item) |
| 13 | judgement call | `priority` values, sort at 1204–1206 | Six-statement draft ordered by fixed numbers; P102 (80) ranks above most response statements | Art. 28(3) sets the limit, not an order; Annex IV gives no order | Keep, and keep the six-statement blocker. The fix keeps your numbers and adds defaults per table. |
| 14 | judgement call | 1206 | A combination counts as one statement towards six | Not settled by Art. 28 or Annex IV; ECHA guidance not checked (bot challenge) | Your call; confirm against the guidance |
| 15 | judgement call | 1204–1206 | Outside consumer supply P501 can drop out of the six without asking whether disposal presents a hazard | Art. 28(2) second paragraph: disposal statement not required where it is clear disposal presents no hazard | The fix adds an info review item |
| 16 | correct | 1186–1190 | P103/P202 and P261/P260 omissions | Annex IV: P103 "omit where P202 is used"; P261 "may be omitted if P260 is given" | — |
| 17 | correct | 1130–1146, 1194–1200 | Consumer P501 protected from exclusion; destination required; Art. 22 caveat | Art. 28(2) | — |

**PR #6 (for the branch decision).** It has 129 codes but still keys triggers on H-codes. Errors found:

| PR #6 location | Error |
|---|---|
| lines 939, 940, 947 | P264, P270 and P310 triggered by H311 (Annex IV lists acute dermal 1, 2 only) |
| line 949 | P312 lacks H311 |
| line 985 | P410 triggered by H240–H242 for self-reactive substances (organic peroxides only) |
| P280 rule | triggered by H220/H221 (pyrophoric gas only) |
| P335 rule | triggered by H250 for pyrophoric liquids (solids only) |
| P223 rule | triggered by H261 for water-reactive Category 3 |
| P370+P380+P375 rule | triggered by H208 (desensitised explosives Category 4 take P371+P380+P375) |

Omissions in PR #6:
- P501 for physical classes;
- P233, P280 and P501 for desensitised explosives;
- P210 for Aerosol 3;
- P363 for skin corrosion;
- all statements for the EUH-coded classes.

It also still raises the consumer disposal blocker beside P502, still proposes P331 beside P301+P330+P331, and writes
"P370+P380+P375+P378" where Annex IV has "P370 + P380 + P375 + [P378]".

**Signal word and pictograms: no findings.**

| Check | Result |
|---|---|
| Art. 20(3), Danger over Warning | correct (`hasDanger ? 'Danger' : …`, line 1391/1410) |
| Signal word per category | matches the Annex I label tables for all 26 calculated classes, e.g. lactation none, aquatic chronic 2–4 none, ED/PBT/PMT as in Tables 3.11.3–4.4.1 |
| Pictograms per category | match Annex V |
| Art. 26(1)(a)–(e) | implemented as written |
| GHS05 vs GHS07 | GHS07 is dropped only for the skin/eye irritation contribution (H315/H319); it stays for other GHS07 hazards such as H302, H317, H335. This is Art. 26(1)(c). |
| Art. 26(2) | applied by the classification, which assigns one category per class; manual entries are flagged for review |

## What the fix PR changes (ConorTttttt/Classification, branch `claude/annex-iv-p-statement-table`)

- Candidates are selected from the full Annex IV Part 1 table, keyed by hazard class and category. The class comes from
  the Annex VI code in the outcome label; H-codes are the fallback.
- Annex IV conditions for use are carried with each statement.
- ED, PBT/vPvB and PMT/vPvM take their statements from the Annex I tables.
- P502 and P503 are accepted as the disposal statement.
- An Article 28(1) review item is raised when a single statement repeats words already in a selected combination.
- `verification/test_annex_iv_table.js` compares the candidates with the Annex I tables.
- It replaces PR #6's hand-written index rather than building on it, so the two conflict: merge one of them.

**Effect on stage 1:** the calculator's candidates become complete and carry `decision` ("proposed", "condition
pending", "class to confirm", "redundant", "not selected") and `conditionKind`. The recommender's adapter should read
those fields rather than treat every candidate as eligible.
