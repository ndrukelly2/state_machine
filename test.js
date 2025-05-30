/**
 * test.js
 * -------
 * Node.js test runner equivalent to test.py
 *
 * Reads scenarios from tests.yaml, then drives state_machine.js
 * for each scenario, printing every step (initial view and each event result).
 *
 * Usage:
 *   npm install js-yaml
 *   node test.js
 */
const fs   = require('fs');
const yaml = require('js-yaml');
const path = require('path');

// Adjust path if state_machine.js is located elsewhere
const StateMachine = require('./state_machine');

function runTests() {
  const testsPath = path.join(__dirname, 'tests.yaml');
  const raw       = fs.readFileSync(testsPath, 'utf8');
  const tests     = yaml.load(raw).tests;

  for (const t of tests) {
    console.log(`\n=== Running test: ${t.id} — ${t.description} ===`);
    const sm = new StateMachine(t.context || {});

    // 1) Initial view
    let result = sm.step();
    console.log(`[0] Initial view →`, result);

    // 2) Replay events
    (t.events || []).forEach((evt, idx) => {
      const i = idx + 1;
      console.log(`\n[${i}] Event →`, evt);
      result = sm.step(evt);
      console.log(`[${i}] Result →`, result);
    });

    console.log('\n--- Test complete ---');
  }
}

if (require.main === module) {
  runTests();
}
