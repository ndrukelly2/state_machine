"""
state_machine.py
----------------
YAML-driven state-machine runner with detailed print debugging:

• Expects states.yaml & transitions.yaml in the same directory.
• Prints every decision, action, sub-flow entry, view render, and event consumed.
"""

from typing import Dict, Any, List, Tuple, Optional
import yaml, pathlib
import sys # Ensure sys is imported

BASE = pathlib.Path(__file__).resolve().parent
TRANS = yaml.safe_load((BASE / "transitions.yaml").read_text(encoding="utf-8"))["transitions"]
STATES = yaml.safe_load((BASE / "states.yaml").read_text(encoding="utf-8"))["states"]


class StateMachine:
    def __init__(self, ctx: Dict[str, Any], output_stream=None, initial_state: Optional[str] = None):
        # normalize context values to lowercase strings
        self.ctx = {k: str(v).lower() for k, v in ctx.items()}
        self.cur: Optional[str] = initial_state if initial_state else "resolver_branch"
        self.stack: List[Tuple[str, List[str]]] = []       # sub-flow stack
        self.pending_error: Optional[str] = None           # carries error_id
        self.output_stream = output_stream if output_stream is not None else sys.stdout

    # ---------- helpers ------------------------------------
    def _next(self, state: str, key: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        ent = TRANS.get(state, {}).get(key)
        set_ctx_data = None
        target_state = None

        if isinstance(ent, dict):
            self.pending_error = ent.get("error_id")
            target_state = ent.get("target")
            set_ctx_data = ent.get("set_context")
            print(f"[DEBUG] Transition (with error/context) from '{state}' on '{key}' → target='{target_state}', error_id='{self.pending_error}', set_context='{set_ctx_data}'", file=self.output_stream)
        elif ent:
            target_state = ent
            print(f"[DEBUG] Transition from '{state}' on '{key}' → '{target_state}'", file=self.output_stream)
        else:
            print(f"[DEBUG] No transition defined from '{state}' on '{key}'", file=self.output_stream)
        
        return target_state, set_ctx_data

    def _apply_context_updates(self, context_updates: Optional[Dict[str, Any]]):
        if context_updates:
            print(f"[DEBUG] Applying context updates: {context_updates}", file=self.output_stream)
            for k, v in context_updates.items():
                self.ctx[str(k).lower()] = str(v).lower()
            print(f"[DEBUG] Updated context: {self.ctx}", file=self.output_stream)

    def _enter_subflow(self, subflow: str):
        print(f"[DEBUG] Entering sub-flow '{subflow}'", file=self.output_stream)
        seq = STATES[subflow]["flow"]
        self.stack.append((subflow, seq[1:]))  # push remainder
        self.cur = seq[0]

    def _pop_subflow(self):
        print(f"[DEBUG] Exiting sub-flow, popping stack", file=self.output_stream)
        while self.stack:
            _sub, rest = self.stack[-1]
            if rest:
                self.cur = rest.pop(0)
                print(f"[DEBUG] Next state in sub-flow: '{self.cur}'", file=self.output_stream)
                return
            print(f"[DEBUG] Sub-flow '{_sub}' complete, popping", file=self.output_stream)
            self.stack.pop()
        self.cur = None  # finished
        print(f"[DEBUG] No more states, machine finished", file=self.output_stream)

    # ---------- public API ---------------------------------
    def step(self, event: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Advance the machine. Returns view dict or None if finished.
        Prints debug info at each step.
        """
        while self.cur:
            print(f"\n[STATE] '{self.cur}' (type={STATES[self.cur]['type']}) | ctx={self.ctx} | pending_error={self.pending_error!r} | event={event!r}", file=self.output_stream)
            state_config = STATES[self.cur]
            stype = state_config["type"]

            # ---------- SWITCH ----------
            if stype == "switch":
                expr = state_config["expression"]
                val = self.ctx.get(expr)
                print(f"[SWITCH] Evaluating '{expr}' → '{val}'", file=self.output_stream) 
                nxt, context_updates = self._next(self.cur, val)
                self._apply_context_updates(context_updates)
                if nxt is None:
                    raise RuntimeError(f"No edge for value '{val}' from switch '{self.cur}'")
                #self.cur, self.pending_error = nxt, None 
                self.cur = nxt
                event = None
                continue

            # ---------- ACTION ----------
            if stype == "action":
                print(f"[ACTION] at '{self.cur}', waiting for event" + ("" if event else " (no event yet)"), file=self.output_stream) 
                if event is None:
                    action_payload = {"state_id": self.cur, "action": True}
                    if state_config.get("cs_contact"):
                        action_payload["cs_contact"] = True
                    return action_payload

                # MODIFIED: Added 'deduplicateNameAction' to handle complex events
                if (self.cur == "resolveUsernameAction" or self.cur == "deduplicateNameAction") and isinstance(event, dict):
                    ev = event["type"]
                    new_ctx = event.get("context", {})
                    self._apply_context_updates(new_ctx)
                    event = ev

                nxt, context_updates = self._next(self.cur, event)
                self._apply_context_updates(context_updates)
                if nxt is None:
                    raise RuntimeError(f"No edge for action '{event}' from '{self.cur}'")
                self.cur = nxt
                event = None
                continue

            # ---------- SUB-FLOW ----------
            if stype == "sub-flow":
                self._enter_subflow(self.cur)
                event = None
                continue

            # ---------- VIEW ----------
            if stype == "view":
                iface = state_config["interface"]
                print(f"[VIEW] Rendering interface '{iface}'", file=self.output_stream) 
                payload = {"state_id": self.cur, "interface": iface}
                if self.pending_error:
                    payload["error_id"] = self.pending_error
                    print(f"[VIEW] Emitting error_id='{self.pending_error}'", file=self.output_stream) 
                    self.pending_error = None 

                if state_config.get("cs_contact"):
                    payload["cs_contact"] = True
                    print(f"[VIEW] Emitting cs_contact=True for '{self.cur}'", file=self.output_stream)

                if event is None:
                    print(f"[VIEW] Pausing for user event on '{self.cur}'", file=self.output_stream) 
                    return payload

                print(f"[VIEW] Consuming user event '{event}' on '{self.cur}'", file=self.output_stream) 
                nxt, context_updates = self._next(self.cur, event)
                self._apply_context_updates(context_updates)
                event = None
                if nxt:
                    self.cur = nxt
                    continue
                else:
                    raise RuntimeError(f"No event '{event}' defined for view '{self.cur}'")

            raise RuntimeError(f"Unknown state type '{stype}' for state '{self.cur}'")

        print("[DONE] State machine has finished all flows.", file=self.output_stream)
        return None


# ------------------------------------------------------------------
# Quick demo (adapt as needed)
if __name__ == "__main__":
    '''
        Context Values
        These are set in the initial context and determine the flow. They can be updated by actions or views.
        # Context object keys and their valid values
        ctx_options = {
            "resolver_match": [
                "exact",    # username exactly matched an existing account
                "multiple", # username matched more than one account
                "none"      # username did not match any account
            ],
            "flight_access": [
                "yes",      # user has flight-access privileges
                "no"        # user does not have flight-access
            ],
            "first_login": [
                "yes",      # this is the user's first successful login
                "no"        # user has logged in before
            ],
            "login_method": [
                "sso",      # user logs in via SSO
                "password"  # user logs in via password
            ],
            "identifier_type": [
                "email",      # the original input was recognized as an email
                "employeeID"  # the original input was treated as an employee ID
            ],
            "domain_match": [
                "yes",      # submitted email's domain matches an approved org
                "no"        # submitted email's domain does not match
            ]
        }

        ------------------------------------------------------------------------------------
        View States and Their Possible Events (based on transitions.yaml):
        ------------------------------------------------------------------------------------
        - UsernameEntryView:
            submitUsername
        - TempPasswordEntryView:
            submitPassword
        - PasswordEntryView:
            submitPassword
            forgotPassword
        - SetupPasswordView:
            processToken
            createPassword
        - UpdatePasswordView:
            processToken
            updatePassword
            skip
        - SSORedirectView:
            continue
            failure
            cancelled
        - LoggedInView:
            (No outgoing user-driven events defined in transitions.yaml)
        - PasswordEmailLinkView:
            resendEmail
        - ForgotPasswordEmailLinkView:
            resendEmail
        - OrganizationPickerView:
            organizationSelected
        ------------------------------------------------------------------------------------
        '''

    ctx = {
        "resolver_match": "multiple",
        "identifier_type": "email",
    }

    sm = StateMachine(ctx, output_stream=sys.stdout)

    # Wind your way through the state machine by calling step() with events
    print(sm.step(), file=sys.stdout)
    print(sm.step("submit_password"), file=sys.stdout)
    print(sm.step("success"), file=sys.stdout)