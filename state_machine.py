"""
state_machine.py
----------------
YAML-driven state-machine runner with detailed print debugging:

• Expects states.yaml & transitions.yaml in the same directory.
• Prints every decision, action, sub-flow entry, view render, and event consumed.
"""

from typing import Dict, Any, List, Tuple, Optional
import yaml, pathlib

BASE = pathlib.Path(__file__).resolve().parent
TRANS = yaml.safe_load((BASE / "transitions.yaml").read_text(encoding="utf-8"))["transitions"]
STATES = yaml.safe_load((BASE / "states.yaml").read_text(encoding="utf-8"))["states"]


class StateMachine:
    def __init__(self, ctx: Dict[str, Any]):
        # normalize context values to lowercase strings
        self.ctx = {k: str(v).lower() for k, v in ctx.items()}
        self.cur: Optional[str] = "resolver_branch"
        self.stack: List[Tuple[str, List[str]]] = []       # sub-flow stack
        self.pending_error: Optional[str] = None           # carries error_id

    # ---------- helpers ------------------------------------
    def _next(self, state: str, key: str):
        ent = TRANS.get(state, {}).get(key)
        if isinstance(ent, dict):
            self.pending_error = ent.get("error_id")
            print(f"[DEBUG] Transition (with error) from '{state}' on '{key}' → target='{ent['target']}', error_id='{self.pending_error}'")
            return ent["target"]
        elif ent:
            print(f"[DEBUG] Transition from '{state}' on '{key}' → '{ent}'")
            return ent
        else:
            print(f"[DEBUG] No transition defined from '{state}' on '{key}'")
            return None

    def _enter_subflow(self, subflow: str):
        print(f"[DEBUG] Entering sub-flow '{subflow}'")
        seq = STATES[subflow]["flow"]
        self.stack.append((subflow, seq[1:]))  # push remainder
        self.cur = seq[0]

    def _pop_subflow(self):
        print(f"[DEBUG] Exiting sub-flow, popping stack")
        while self.stack:
            _sub, rest = self.stack[-1]
            if rest:
                self.cur = rest.pop(0)
                print(f"[DEBUG] Next state in sub-flow: '{self.cur}'")
                return
            print(f"[DEBUG] Sub-flow '{_sub}' complete, popping")
            self.stack.pop()
        self.cur = None  # finished
        print(f"[DEBUG] No more states, machine finished")

    # ---------- public API ---------------------------------
    def step(self, event: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Advance the machine. Returns view dict or None if finished.
        Prints debug info at each step.
        """
        while self.cur:
            print(f"\n[STATE] '{self.cur}' (type={STATES[self.cur]['type']}) | pending_error={self.pending_error!r} | event={event!r}")
            state = STATES[self.cur]
            stype = state["type"]

            # ---------- SWITCH ----------
            if stype == "switch":
                expr = state["expression"]
                val = self.ctx.get(expr)
                print(f"[SWITCH] Evaluating '{expr}' → '{val}'")
                nxt = self._next(self.cur, val)
                if nxt is None:
                    raise RuntimeError(f"No edge for value '{val}' from switch '{self.cur}'")
                self.cur, self.pending_error = nxt, None
                event = None
                continue

            # ---------- ACTION ----------
            if stype == "action":
                print(f"[ACTION] at '{self.cur}', waiting for event" + ("" if event else " (no event yet)"))
                if event is None:
                    return {"state_id": self.cur, "action": True}

                # always compute nxt
                if self.cur == "resolveUsernameAction" and isinstance(event, dict):
                    ev = event["type"]
                    new_ctx = event.get("context", {})
                    for k,v in new_ctx.items():
                        self.ctx[k] = str(v).lower()
                    event = ev

                nxt = self._next(self.cur, event)    # ← MOVE this outside the special‐case
                if nxt is None:
                    raise RuntimeError(f"No edge for action '{event}' from '{self.cur}'")
                self.cur, self.pending_error, event = nxt, None, None
                continue

            # ---------- SUB-FLOW ----------
            if stype == "sub-flow":
                self._enter_subflow(self.cur)
                event = None
                continue

            # ---------- VIEW ----------
            if stype == "view":
                iface = state["interface"]
                print(f"[VIEW] Rendering interface '{iface}'")
                payload = {"state_id": self.cur, "interface": iface}
                if self.pending_error:
                    payload["error_id"] = self.pending_error
                    print(f"[VIEW] Emitting error_id='{self.pending_error}'")
                    self.pending_error = None

                if event is None:
                    print(f"[VIEW] Pausing for user event on '{self.cur}'")
                    return payload

                print(f"[VIEW] Consuming user event '{event}' on '{self.cur}'")
                nxt = self._next(self.cur, event)
                event = None
                if nxt:
                    self.cur = nxt
                    continue
                # # no transition: pop subflow or finish
                # self._pop_subflow()
                else:
                    # unrecognized event: raise or ignore 
                    raise RuntimeError(f"No event '{event}' defined for view '{self.cur}'")
                #continue

            raise RuntimeError(f"Unknown state type '{stype}' for state '{self.cur}'")

        print("[DONE] State machine has finished all flows.")
        return None


# ------------------------------------------------------------------
# Quick demo (adapt as needed)
if __name__ == "__main__":
    ''' The user experience starts with a basic username input field. This is either:
      a) the login screen
      b) account creation screen
      In either case, the user will submit their username (TBD on company dropdown -> SSO flow)
      which will trigger our resolve() call and start our state machine to build context. All
      states start from the resolver_branch. From there, depending on the ctx values set below, 
      the next login step will be determined. 

      Action States
      These come from your backend calls. You pass them into .step(event) when the machine is paused at an action state.
      # Action states and their possible events
      action_events = {
            "resolveUsernameAction":          ["exact", "multiple", "none", "error"],
            "verifyTempPasswordAction":        ["success", "invalid_password", "account_locked"],
            "verifyPasswordAction":            ["success", "invalid_password", "account_locked"],
            "sendResetEmailAction":           ["email_sent"],
            "checkEmailDomainAction":         ["match", "no_match"],
            "fetchOrganizationListAction":    ["success", "failure"],
            "fetchEmployeeIDSuggestionsAction": ["suggestions", "no_suggestions"],
            "initiateSSOAction":              ["success", "failure"],
            "logLoginAttemptAction":          ["logged"],
            "checkAccountLockStatusAction":   ["locked", "unlocked"],
            "createAccountAction":            ["success", "failure"],
            "sendUsernameReminderAction":     ["emailed", "failed"],
            "sendMFACodeAction":              ["code_sent", "error"],
            "verifyMFACodeAction":            ["valid", "invalid"],
            "fetchUserPoliciesAction":        ["success", "no_policies"],
        }

        View States
        These are user-driven events (buttons, form submits, etc.). Whenever the machine is paused at that view, you call .step("that_event").
        # View states and their possible user-driven events. 
        view_events = {
            "UsernameEntryView":              ["submit_username"],
            #"UsernameReminderSentView":       ["continue"],
            "MfaCodeEntryView":               ["submit_code"],
            "TempPasswordEntryView":          ["submit_password"],
            "PasswordEntryView":              ["submit_password","forgot_password"],
            "SetupPasswordView":              ["submit_new_password"],
            "SSORedirectView":                ["continue"],
            "LoggedInView":                   [],  # terminal
            "CreateAccountView":              ["submit_signup"],
            "AccountCreatedConfirmationView": ["continue"],
            "ForgotPwView":                   ["submit_email"],
            "PasswordResetConfirmationView":  ["continue"],
            "employeeIDCompanyPickerView":    ["organization_selected", "continue"],
            "organizationPickerView":         ["selected", "continue"],
            "UnsupportedWorkEmailView":       [],  # terminal
        }

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
                "yes",      # this is the user’s first successful login
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
    
    '''

    ctx = {
        "resolver_match": "multiple",
        "flight_access": "yes",
        "first_login": "no",
        "login_method": "password",
        "identifier_type": "email",
        "domain_match": "yes",
    }

    sm = StateMachine(ctx)

    # 
    print(sm.step())
    print(sm.step("submit_password"))
    print(sm.step("success"))  # backend returns success
    #print(sm.step("submit_new_password"))  # backend returns success
    #backend returns invalid_password
    #print(sm.step("invalid_password"))
    # user clicks forgot_password
    #print(sm.step("forgot_password"))
    # and so on...
    # When you need to reset context object and refire the resolver branch (eg when user re-submits their
    # username on a different screen), you can do that likes so:
    '''resp = resolve_api(new_username)'''
    # resp == {"resolver_match":"exact", "flight_access":"yes", …} # Or we can fake it here
    '''sm.step({"type":"exact", "context": resp})'''
