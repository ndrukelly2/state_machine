
/**
 * state_machine.js
 * ----------------
 * YAML‑driven state‑machine runner with detailed console debugging.
 *
 *  • Expects `states.yaml` and `transitions.yaml` next to this file.
 *  • Prints every decision, action, sub‑flow entry, view render, and event consumed.
 *
 *  Usage:
 *      npm install js-yaml
 *      node state_machine.js
 */
const fs   = require('fs');
const path = require('path');
const yaml = require('js-yaml');

const BASE   = __dirname;
const STATES = yaml.load(fs.readFileSync(path.join(BASE, 'states.yaml'), 'utf8')).states;
const TRANS  = yaml.load(fs.readFileSync(path.join(BASE, 'transitions.yaml'), 'utf8')).transitions;

class StateMachine {
  /**
   * @param {Object} ctx – initial context values (any primitives); values are normalised to lower‑case strings
   */
  constructor(ctx) {
    // normalise context to lower‑case strings to match Python implementation
    this.ctx = {};
    for (const [k, v] of Object.entries(ctx || {})) {
      this.ctx[k] = String(v).toLowerCase();
    }

    this.cur          = 'resolver_branch'; // start state
    this.stack        = [];                // sub‑flow stack: [ [subflowId, remainingStates], ... ]
    this.pendingError = null;              // carries error_id between transitions
  }

  // ---------- helpers ------------------------------------
  _next(stateId, key) {
    const ent = (TRANS[stateId] || {})[key];
    if (ent && typeof ent === 'object') {
      this.pendingError = ent.error_id || null;
      console.log(`[DEBUG] Transition (with error) from '${stateId}' on '${key}' → target='${ent.target}', error_id='${this.pendingError}'`);
      return ent.target;
    }
    if (ent) {
      console.log(`[DEBUG] Transition from '${stateId}' on '${key}' → '${ent}'`);
      return ent;
    }
    console.log(`[DEBUG] No transition defined from '${stateId}' on '${key}'`);
    return null;
  }

  _enterSubflow(subId) {
    console.log(`[DEBUG] Entering sub-flow '${subId}'`);
    const seq = STATES[subId].flow;
    this.stack.push([subId, seq.slice(1)]);   // push remainder onto stack
    this.cur = seq[0];
  }

  _popSubflow() {
    console.log('[DEBUG] Exiting sub-flow, popping stack');
    while (this.stack.length) {
      const [sub, rest] = this.stack[this.stack.length - 1];
      if (rest.length) {
        this.cur = rest.shift();
        console.log(`[DEBUG] Next state in sub-flow '${sub}': '${this.cur}'`);
        return;
      }
      console.log(`[DEBUG] Sub-flow '${sub}' complete, popping`);
      this.stack.pop();
    }
    this.cur = null;
    console.log('[DEBUG] No more states, machine finished');
  }

  /**
   * Advance the machine by one event.
   * @param {string|Object|null} event – event name, event object (special‑case) or null
   * @returns {Object|null} view payload or null if finished
   */
  step(event = null) {
    while (this.cur) {
      const state = STATES[this.cur];
      const stype = state.type;
      console.log(`\n[STATE] '${this.cur}' (type=${stype}) | pending_error=${this.pendingError} | event=${JSON.stringify(event)}`);

      // ---------- SWITCH ----------
      if (stype === 'switch') {
        const expr = state.expression;
        const val  = this.ctx[expr];
        console.log(`[SWITCH] Evaluating '${expr}' → '${val}'`);
        const nxt = this._next(this.cur, val);
        if (nxt === null) throw new Error(`No edge for value '${val}' from switch '${this.cur}'`);
        this.cur          = nxt;
        this.pendingError = null;
        event             = null;
        continue;
      }

      // ---------- ACTION ----------
      if (stype === 'action') {
        console.log('[ACTION] at', `'${this.cur}', waiting for event${ event ? '' : ' (no event yet)' }`);

        // SPECIAL-CASE: resolveUsernameAction accepts an object payload
        if (this.cur === 'resolveUsernameAction' && event !== null && typeof event === 'object') {
          const evType   = event.type;
          const newCtx   = event.context || {};
          for (const [k, v] of Object.entries(newCtx)) {
            this.ctx[k] = String(v).toLowerCase();
          }
          event = evType;  // replace event with its type for transition lookup
        }

        if (event === null) {
          return { state_id: this.cur, action: true };
        }

        const nxt = this._next(this.cur, event);
        if (nxt === null) throw new Error(`No edge for action '${event}' from '${this.cur}'`);
        this.cur          = nxt;
        this.pendingError = null;
        event             = null;
        continue;
      }

      // ---------- SUB-FLOW ----------
      if (stype === 'sub-flow') {
        this._enterSubflow(this.cur);
        event = null;
        continue;
      }

      // ---------- VIEW ----------
      if (stype === 'view') {
        const iface = state.interface;
        console.log(`[VIEW] Rendering interface '${iface}'`);
        const payload = { state_id: this.cur, interface: iface };

        if (this.pendingError) {
          payload.error_id   = this.pendingError;
          console.log(`[VIEW] Emitting error_id='${this.pendingError}'`);
          this.pendingError  = null;
        }

        if (event === null) {
          console.log(`[VIEW] Pausing for user event on '${this.cur}'`);
          return payload;   // wait for UI event
        }

        console.log(`[VIEW] Consuming user event '${event}' on '${this.cur}'`);
        const nxt = this._next(this.cur, event);
        const originalEvent = event;    // preserve for error
        event = null;
        if (nxt) {
          this.cur = nxt;
          continue;
        }
        throw new Error(`No event '${originalEvent}' defined for view '${this.cur}'`);
      }

      throw new Error(`Unknown state type '${stype}' for state '${this.cur}'`);
    }

    console.log('[DONE] State machine has finished all flows.');
    return null;
  }
}

// ------------------------------------------------------------------
// Quick demo (adapt as needed)
if (require.main === module) {
  const ctx = {
    resolver_match: 'multiple',
    flight_access:  'yes',
    first_login:    'no',
    login_method:   'password',
    identifier_type:'email',
    domain_match:   'yes',
  };

  const sm = new StateMachine(ctx);

  // drive the state machine with sample events
  console.log(sm.step());                 // initial view/action
  console.log(sm.step('submit_password')); // user submits password
  console.log(sm.step('success'));         // backend returns success
}

module.exports = StateMachine;
