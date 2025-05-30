/**
 * stateMachine.js
 * ----------------
 * YAML-driven state-machine runner with detailed console debugging.
 *
 * • Expects `states.yaml` and `transitions.yaml` next to this file.
 * • Prints every decision, action, sub-flow entry, view render, and event consumed.
 *
 * Usage:
 *   npm install js-yaml
 *   node stateMachine.js
 */

const fs   = require('fs');
const path = require('path');
const yaml = require('js-yaml');

const BASE   = __dirname;
const STATES = yaml.load(fs.readFileSync(path.join(BASE, 'states.yaml'), 'utf8')).states;
const TRANS  = yaml.load(fs.readFileSync(path.join(BASE, 'transitions.yaml'), 'utf8')).transitions;

class StateMachine {
  /**
   * @param {Object} ctx  – context values, keys lowercase strings
   */
  constructor(ctx) {
    this.ctx = {};
    for (const [k, v] of Object.entries(ctx)) {
      this.ctx[k] = String(v).toLowerCase();
    }
    this.cur          = 'resolver_branch'; // start state
    this.stack        = [];                // sub-flow stack: [ [subflowId, remainingStates], ... ]
    this.pendingError = null;              // holds error_id between transitions
  }

  // ---------- helpers ------------------------------------
  _next(stateId, key) {
    const ent = (TRANS[stateId] || {})[key];
    if (ent && typeof ent === 'object') {
      this.pendingError = ent.error_id || null;
      console.log(`[DEBUG] Transition (with error) from '${stateId}' on '${key}' → target='${ent.target}', error_id='${this.pendingError}'`);
      return ent.target;
    }
    if (ent && typeof ent === 'string') {
      console.log(`[DEBUG] Transition from '${stateId}' on '${key}' → '${ent}'`);
      return ent;
    }
    console.log(`[DEBUG] No transition defined from '${stateId}' on '${key}'`);
    return null;
  }

  _enterSubflow(subId) {
    console.log(`[DEBUG] Entering sub-flow '${subId}'`);
    const seq = STATES[subId].flow;
    this.stack.push([subId, seq.slice(1)]);
    this.cur = seq[0];
  }

  _popSubflow() {
    console.log(`[DEBUG] Exiting sub-flow, popping stack`);
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
    console.log(`[DEBUG] No more states, machine finished`);
  }

  /**
   * Advance the machine by one event.
   *
   * @param {string|null} event  – event name or null
   * @returns {Object|null} view payload or null if finished
   */
  step(event = null) {
    while (this.cur) {
      const state   = STATES[this.cur];
      const stype   = state.type;
      console.log(`\n[STATE] '${this.cur}' (type=${stype}) | pendingError=${this.pendingError} | event=${event}`);

      // ---------- SWITCH ----------
      if (stype === 'switch') {
        const expr = state.expression;
        const val  = this.ctx[expr];
        console.log(`[SWITCH] Evaluating '${expr}' → '${val}'`);
        const nxt = this._next(this.cur, val);
        if (!nxt) throw new Error(`No edge for value '${val}' from switch '${this.cur}'`);
        this.cur          = nxt;
        this.pendingError = null;
        event            = null;
        continue;
      }

      // ---------- ACTION ----------
      if (stype === 'action') {
        console.log(`[ACTION] at '${this.cur}', waiting for event${ event ? '' : ' (no event yet)' }`);
        if (!event) {
          return { stateId: this.cur, action: true };
        }
        const nxt = this._next(this.cur, event);
        if (!nxt) throw new Error(`No edge for action '${event}' from '${this.cur}'`);
        this.cur          = nxt;
        this.pendingError = null;
        event            = null;
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
        const payload = { stateId: this.cur, interface: iface };
        if (this.pendingError) {
          payload.errorId     = this.pendingError;
          console.log(`[VIEW] Emitting errorId='${this.pendingError}'`);
          this.pendingError = null;
        }
        if (!event) {
          console.log(`[VIEW] Pausing for user event on '${this.cur}'`);
          return payload;
        }
        console.log(`[VIEW] Consuming user event '${event}' on '${this.cur}'`);
        const nxt = this._next(this.cur, event);
        event     = null;
        if (nxt) {
          this.cur = nxt;
          continue;
        }
        // unrecognized event: throw
        throw new Error(`No event '${event}' defined for view '${this.cur}'`);
      }

      throw new Error(`Unknown state type '${stype}' for state '${this.cur}'`);
    }

    console.log('[DONE] State machine has finished all flows.');
    return null;
  }
}

// ------------------------------------------------------------------
// Quick demo
if (require.main === module) {
  const exampleCtx = {
    resolver_match: 'exact',
    flight_access:  'yes',
    first_login:    'yes',
    login_method:   'password',
    identifier_type:'email',
    domain_match:   'yes'
  };

  const sm = new StateMachine(exampleCtx);

  // initial view
  console.log(sm.step());
  // submit password
  console.log(sm.step('submit_password'));
  // backend returns invalid_password
  console.log(sm.step('invalid_password'));
  // user clicks forgot password
  console.log(sm.step('forgot_password'));
}

module.exports = StateMachine;
