// Runs the Classification calculator's Article 28 selection on test inputs (read-only use of its engine).
//   node tools/pcalc_harness.js PATH/TO/verification/engine.js < inputs.json > outputs.json
// inputs: [{id, outcomes: [{h: [...], label}], settings: {...}}]
'use strict';
const E = require(require('path').resolve(process.argv[2]));
const input = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const out = {};
for (const t of input) {
  const r = E.selectArticle28(t.outcomes, t.settings || {});
  out[t.id] = {
    candidates: r.candidates.map((c) => ({code: c.code, decision: c.decision, priority: c.priority, text: c.text})),
    selected: r.selected.map((c) => c.code),
    uncovered: r.uncovered,
    review: r.review.map((x) => ({severity: x.severity, code: x.code})),
    excess: r.excessCandidateCount,
  };
}
out._rules = E.P28_RULES.map((r) => ({code: r.code, text: r.text, h: r.h || null, consumer: !!r.consumer,
  priority: r.priority, condition: r.condition || '', needs: r.needs || '', basis: r.basis}));
process.stdout.write(JSON.stringify(out));
