# Backlog

These are findings and open items that fall outside the sections built so far. Each one names the checklist it belongs to.

## Out-of-scope findings from the test SDSs

| SDS | Section | Finding | Belongs to |
|---|---|---|---|
| Acetone (Fisher, rev 14, 19-Oct-2023; GB) | 2.2 | Classified Eye Irrit. 2 (H319), but the label omits P305+P351+P338. CLP Annex IV assigns that combination to Eye Irrit. 2 (EU and GB text, verified). | Section 2 checklist |
| Sodium hypochlorite (Fisher/Acros, rev 11, 19-Dec-2025; US) | 11 | Section 11 says "Inhalation: Not an expected route of exposure", but the product is classified STOT SE 3 (respiratory irritation, H335) and Section 4 gives inhalation first aid. | Section 11 checklist |
| Calcium carbide (SLS CHE1468, rev 1.1; GB) | 2.2 | P223 is printed as "Keep away from any possible contact with water, because of violent reaction and possible flash fire." The official CLP text is "Do not allow contact with water." | Section 2 checklist |
| Calcium carbide (SLS CHE1468) | 1 / 16 | Cites Reg. (EU) 2015/830 together with GB CLP. For EU use, that format has been superseded since 1 Jan 2023. | Section 1/16 checklist |

## Verification still open

- **GHS Rev.10 codes P316–P319.** The equivalence to P310–P315 is unverified. It will be checked against GHS Rev.11 Annex 3, which the user will upload. Until then, findings say "UNVERIFIED".
- **OSHA Appendix C (US P-statement wording).** eCFR and federalregister.gov publish it only as images. US text is matched against the CLP wording for now.
- **EUH211/EUH212.** These are deleted in the EU text consolidated to 1 Jan 2027, following titanium dioxide notice C/2025/6670. They were never in GB CLP. This matters for the Section 2 and Section 8 checklists.
- **Sources that refuse automated access:** ECHA CHEM / C&L Inventory (Azure gateway), ERG/PHMSA (Akamai) and UNECE (Cloudflare). The checks that rely on them report "not checked".
- **PubChem** intermittently refuses requests with "server busy", so elemental-composition checks fall back to the formulas given in the SDS.
- **GESTIS** article text needs an API key we don't hold, so it stays a manual link.

## Engine coverage: Checklist rows that have no code yet

The regression set tests only the rows that are coded, so rows with no code don't show up as failures. They're listed here.

| Section | Coded | Not coded yet | Manual by design (source paid, desktop-only, or refuses automated access) |
|---|---|---|---|
| 10 | 26 / 56 | A6, A8, A10, A11, A13–A16; B3–B9, B13–B17; C7; D4–D6 | D2 (Bretherick's), D3 (CRW 4), D7 (ERG), D8/D9 (ECHA), D10 (test reports, info) |
| 4 | 24 / 27 | A5 (US "no applicable information"), A10, A11 (info) | — |
| 5–7 | all draft rows except those at right | — | 6-C3 (info), 7-D2 (ECHA), 7-D3 (HSE guidance, info) |

Priority: the Section 10 B rows (B3–B9, B13–B17). The synthetic flammable gas, explosive, oxidiser and organic peroxide SDSs already provide test input for most of them.

## Other

- The Sheet title still reads "(Sections 4-8)". It can only be renamed in the Sheet page.
