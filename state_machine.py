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
    def __init__(self, ctx: Dict[str, Any], output_stream=None): # MODIFIED
        # normalize context values to lowercase strings
        self.ctx = {k: str(v).lower() for k, v in ctx.items()}
        self.cur: Optional[str] = "resolver_branch"
        self.stack: List[Tuple[str, List[str]]] = []       # sub-flow stack
        self.pending_error: Optional[str] = None           # carries error_id
        self.output_stream = output_stream if output_stream is not None else sys.stdout # ADDED

    # ---------- helpers ------------------------------------
    def _next(self, state: str, key: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]: # MODIFIED return type
        ent = TRANS.get(state, {}).get(key)
        set_ctx_data = None
        target_state = None

        if isinstance(ent, dict):
            self.pending_error = ent.get("error_id")
            target_state = ent.get("target")
            set_ctx_data = ent.get("set_context") # ADDED: Get set_context
            print(f"[DEBUG] Transition (with error/context) from '{state}' on '{key}' → target='{target_state}', error_id='{self.pending_error}', set_context='{set_ctx_data}'", file=self.output_stream)
        elif ent:
            target_state = ent
            print(f"[DEBUG] Transition from '{state}' on '{key}' → '{target_state}'", file=self.output_stream)
        else:
            print(f"[DEBUG] No transition defined from '{state}' on '{key}'", file=self.output_stream)
        
        return target_state, set_ctx_data # MODIFIED: Return target and set_context data

    def _apply_context_updates(self, context_updates: Optional[Dict[str, Any]]): # ADDED: New helper method
        if context_updates:
            print(f"[DEBUG] Applying context updates: {context_updates}", file=self.output_stream)
            for k, v in context_updates.items():
                self.ctx[str(k).lower()] = str(v).lower()
            print(f"[DEBUG] Updated context: {self.ctx}", file=self.output_stream)

    def _enter_subflow(self, subflow: str):
        print(f"[DEBUG] Entering sub-flow '{subflow}'", file=self.output_stream) # MODIFIED
        seq = STATES[subflow]["flow"]
        self.stack.append((subflow, seq[1:]))  # push remainder
        self.cur = seq[0]

    def _pop_subflow(self):
        print(f"[DEBUG] Exiting sub-flow, popping stack", file=self.output_stream) # MODIFIED
        while self.stack:
            _sub, rest = self.stack[-1]
            if rest:
                self.cur = rest.pop(0)
                print(f"[DEBUG] Next state in sub-flow: '{self.cur}'", file=self.output_stream) # MODIFIED
                return
            print(f"[DEBUG] Sub-flow '{_sub}' complete, popping", file=self.output_stream) # MODIFIED
            self.stack.pop()
        self.cur = None  # finished
        print(f"[DEBUG] No more states, machine finished", file=self.output_stream) # MODIFIED

    # ---------- public API ---------------------------------
    def step(self, event: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Advance the machine. Returns view dict or None if finished.
        Prints debug info at each step.
        """
        while self.cur:
            print(f"\n[STATE] '{self.cur}' (type={STATES[self.cur]['type']}) | ctx={self.ctx} | pending_error={self.pending_error!r} | event={event!r}", file=self.output_stream) # MODIFIED to show context
            state_config = STATES[self.cur] # Renamed 'state' to 'state_config' to avoid conflict
            stype = state_config["type"]

            # ---------- SWITCH ----------
            if stype == "switch":
                expr = state_config["expression"]
                val = self.ctx.get(expr)
                print(f"[SWITCH] Evaluating '{expr}' → '{val}'", file=self.output_stream) 
                nxt, context_updates = self._next(self.cur, val) # MODIFIED: Get context_updates
                self._apply_context_updates(context_updates) # ADDED: Apply context updates
                if nxt is None:
                    raise RuntimeError(f"No edge for value '{val}' from switch '{self.cur}'")
                self.cur, self.pending_error = nxt, None 
                event = None
                continue

            # ---------- ACTION ----------
            if stype == "action":
                print(f"[ACTION] at '{self.cur}', waiting for event" + ("" if event else " (no event yet)"), file=self.output_stream) 
                if event is None:
                    # For actions, we might want to include cs_contact if defined
                    action_payload = {"state_id": self.cur, "action": True}
                    if state_config.get("cs_contact"):
                        action_payload["cs_contact"] = True
                    return action_payload


                if self.cur == "resolveUsernameAction" and isinstance(event, dict):
                    ev = event["type"]
                    new_ctx = event.get("context", {})
                    self._apply_context_updates(new_ctx) # Use helper to apply context
                    event = ev

                nxt, context_updates = self._next(self.cur, event) # MODIFIED: Get context_updates
                self._apply_context_updates(context_updates) # ADDED: Apply context updates
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

                if state_config.get("cs_contact"): # ADDED: Check for cs_contact in view
                    payload["cs_contact"] = True
                    print(f"[VIEW] Emitting cs_contact=True for '{self.cur}'", file=self.output_stream)

                if event is None:
                    print(f"[VIEW] Pausing for user event on '{self.cur}'", file=self.output_stream) 
                    return payload

                print(f"[VIEW] Consuming user event '{event}' on '{self.cur}'", file=self.output_stream) 
                nxt, context_updates = self._next(self.cur, event) # MODIFIED: Get context_updates
                self._apply_context_updates(context_updates) # ADDED: Apply context updates
                event = None
                if nxt:
                    self.cur = nxt
                    # self.pending_error is handled by _next if it sets one
                    continue
                else:
                    # If _next returned None and didn't set a pending_error, it's an undefined event for the view
                    if not self.pending_error: # Check if _next already set an error transition
                        raise RuntimeError(f"No event '{event}' defined for view '{self.cur}' and no error transition found")
                    # If pending_error was set by _next, it means the event led to an error transition.
                    # The loop will continue, and the error will be processed by the next state (likely a view).
                    # self.cur would have been updated by _next if it was an error transition target.
                    # If self.cur is None here, it means an error transition tried to go nowhere, which _next should prevent.
                    # This logic might need refinement based on how error transitions from views are defined.
                    # For now, assuming _next handles setting self.cur correctly for error transitions.
                    # If nxt is None and an error is pending, it implies the event itself was an error trigger.
                    # The current logic: if nxt is None, it's a hard error unless _next specifically set a pending_error and a target.
                    # Let's assume _next returning None means "no valid transition for this event from this state".
                    # If an error_id was set by _next, it means the event *matched* an error transition.
                    # If nxt is None and no pending_error, then it's an unhandled event.
                    # The original code had: raise RuntimeError(f"No event '{event}' defined for view '{self.cur}'")
                    # This should be fine if _next correctly returns a target or None.
                    # If _next returns None, it means no transition (normal or error) was found for that event.
                    raise RuntimeError(f"No event '{event}' defined for view '{self.cur}'")

            raise RuntimeError(f"Unknown state type '{stype}' for state '{self.cur}'")

        print("[DONE] State machine has finished all flows.", file=self.output_stream) # MODIFIED
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
            forgotPassword [still need to make this conditional on an email in our system]
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
            (No outgoing user-driven events defined) [need to add a email collection view here in cases where employeeID is used    ]
        - PasswordEmailLinkView:
            passwordEmailLinkSuccess
            resendEmail
        - ForgotPasswordEmailLinkView:
            forgotPasswordEmailLinkSuccess
            resendEmail
        - OrganizationPickerView:
            organizationSelected
        ------------------------------------------------------------------------------------
        '''

    ctx = {
        "resolver_match": "multiple",
        "identifier_type": "email",
    }

    sm = StateMachine(ctx, output_stream=sys.stdout) # Ensure demo uses the new signature

    # Wind your way through the state machine by calling step() with events
    print(sm.step(), file=sys.stdout) # Direct demo prints to actual stdout
    print(sm.step("submit_password"), file=sys.stdout)
    print(sm.step("success"), file=sys.stdout)
