# test.py
# --------
# Run through each scenario in tests.yaml and show every step,
# including the initial view and handling of “rich” submit_username events.

import yaml
from state_machine import StateMachine

def run_tests():
    tests = yaml.safe_load(open("tests.yaml", encoding="utf-8"))["tests"]
    for t in tests:
        print(f"\n=== Running test: {t['id']} — {t['description']} ===")
        # instantiate with initial context (without resolver_match if you re-resolve later)
        sm = StateMachine(t.get("context", {}))

        # 1) Get the first view (could be a prompt, error, etc.)
        result = sm.step()
        print(f"[0] Initial view → {result}")

        # 2) Replay all events
        for i, evt in enumerate(t["events"], start=1):
            print(f"\n[{i}] Event → {evt}")
            result = sm.step(evt)
            print(f"[{i}] Result → {result}")

        print("\n--- Test complete ---")

if __name__ == "__main__":
    run_tests()
