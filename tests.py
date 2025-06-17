# test.py
# --------
# Run through each scenario in tests.yaml and show every step,
# including the initial view and handling of “rich” submit_username events.

import yaml
from state_machine import StateMachine
import sys
import argparse
import pathlib

def run_tests(sm_custom_output_stream): # MODIFIED to accept stream for StateMachine
    tests_file_path = pathlib.Path(__file__).resolve().parent / "tests.yaml"
    tests_data = yaml.safe_load(tests_file_path.read_text(encoding="utf-8"))
    
    if not tests_data or "tests" not in tests_data:
        print("Error: 'tests.yaml' is empty or not formatted correctly.", file=sys.stderr)
        return

    tests = tests_data["tests"]

    for test_index, t in enumerate(tests):
        # Print separator and test info to StateMachine log stream
        if test_index > 0: # Add a separator before the next test, but not before the first one
            print(f"\n\n{'=' * 70}\n", file=sm_custom_output_stream)
        
        test_id = t.get('id', 'N/A')
        test_description = t.get('description', 'No description')
        initial_context = t.get("context", {})
        initial_state_from_yaml = t.get("initial_state") # Get initial_state

        print(f"--- Test Case Start ---", file=sm_custom_output_stream)
        print(f"ID: {test_id}", file=sm_custom_output_stream)
        print(f"Description: {test_description}", file=sm_custom_output_stream)
        print(f"Initial Context: {initial_context}", file=sm_custom_output_stream)
        print(f"{'-' * 70}", file=sm_custom_output_stream)
        
        # This print goes to tests.py's current stdout (console or login_flows.log)
        print(f"\n=== Running test: {test_id} — {test_description} ===")
        
        # Instantiate StateMachine with the custom output stream
        sm = StateMachine(
            ctx=initial_context,
            output_stream=sm_custom_output_stream,
            initial_state=initial_state_from_yaml # Pass it here
        )

        # 1) Get the first view
        result = sm.step()
        print(f"[0] Initial view → {result}") # This print uses tests.py's current stdout

        # 2) Replay all events
        for i, evt in enumerate(t.get("events", []), start=1):
            print(f"\n[{i}] Event → {evt}") # This print uses tests.py's current stdout
            result = sm.step(evt)
            print(f"[{i}] Result → {result}") # This print uses tests.py's current stdout

        # 3) Check final state if specified
        expected_final_state = t.get("final_state")
        if expected_final_state:
            # Ensure comparison handles None correctly if result is None (machine finished)
            current_final_state_repr = result if result is not None else None 
            if current_final_state_repr == expected_final_state:
                print(f"\n[PASS] Final state matches expected: {current_final_state_repr}")
            else:
                print(f"\n[FAIL] Final state mismatch. Expected: {expected_final_state}, Got: {current_final_state_repr}")
        
        # 4) Check final context if specified
        expected_context = t.get("final_context")
        if expected_context:
            match = True
            for k, v_expected in expected_context.items():
                v_actual = sm.ctx.get(k)
                # Ensure consistent comparison (e.g., stringify and lowercase)
                if str(v_actual).lower() != str(v_expected).lower():
                    match = False
                    print(f"[FAIL] Context mismatch for '{k}'. Expected: '{v_expected}', Got: '{v_actual}'")
            if match:
                print(f"[PASS] Final context matches expected.")

        print("\n--- Test complete ---") # This print uses tests.py's current stdout

        # Log test end to StateMachine log stream
        print(f"\n{'-' * 70}", file=sm_custom_output_stream)


# How to use:
#
# Run tests.py from your terminal:
#
# 1. To run normally (all output to console):
#    python tests.py
#
# 2. To redirect StateMachine's internal prints to state_machine_flows.log
#    (and tests.py's own script prints to console):
#    python tests.py --sm-log
#
# 3. To redirect tests.py's own script prints to login_flows.log
#    (and StateMachine's internal prints to console):
#    python tests.py --log
#
# 4. To redirect StateMachine's prints to state_machine_flows.log AND
#    tests.py's own script prints to login_flows.log:
#    python tests.py --sm-log --log
#
# Note: Log files are appended to, so previous logs will be preserved.
#       Log files are created in the directory where the script is run.

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run state machine tests with logging options.")
    parser.add_argument(
        "--log",
        action="store_true",
        help="Redirect tests.py's own stdout (script prints) to login_flows.log."
    )
    parser.add_argument(
        "--sm-log",
        action="store_true",
        help="Redirect StateMachine's internal prints to state_machine_flows.log."
    )
    args = parser.parse_args()

    # --- Setup for tests.py's own logging (--log) ---
    original_stdout = sys.stdout
    tests_script_log_fh = None
    if args.log:
        try:
            tests_log_path = pathlib.Path.cwd() / "login_flows.log"
            tests_script_log_fh = open(tests_log_path, "a", encoding="utf-8")
            sys.stdout = tests_script_log_fh # Redirect print() calls in this script
            print(f"\n--- New Test Script Log Session: {pathlib.Path(__file__).name} ({'--sm-log active' if args.sm_log else '--sm-log inactive'}) ---", file=sys.stdout)
        except IOError as e:
            sys.stdout = original_stdout # Revert if error
            print(f"Error: Could not open test script log file '{tests_log_path}'. Script output will go to console. Details: {e}", file=sys.stderr)
            tests_script_log_fh = None

    # --- Setup for StateMachine's logging (--sm-log) ---
    # Default stream for StateMachine is its original stdout (which might be console or tests_script_log_fh if --log is active)
    sm_output_stream_for_sm_class = sys.stdout 
    sm_specific_log_fh = None
    if args.sm_log:
        try:
            sm_log_path = pathlib.Path.cwd() / "state_machine_flows.log"
            # Announce to original console (or tests.py log if active) that we're trying to set up SM log
            print(f"Attempting to log StateMachine output to: {sm_log_path}", file=sys.stdout) 
            
            sm_specific_log_fh = open(sm_log_path, "a", encoding="utf-8")
            sm_output_stream_for_sm_class = sm_specific_log_fh # This stream will be passed to StateMachine instances
            
            # Write a header to the StateMachine-specific log file
            print(f"\n--- New StateMachine Log Session (triggered by tests.py --sm-log): ---", file=sm_output_stream_for_sm_class)
        except IOError as e:
            # If SM-specific log fails, print error to current sys.stdout (console or tests_script_log_fh)
            print(f"Error: Could not open StateMachine log file '{sm_log_path}'. StateMachine prints will go to the current script's output destination. Details: {e}", file=sys.stdout)
            # sm_output_stream_for_sm_class remains as current sys.stdout
            sm_specific_log_fh = None # Ensure it's None

    try:
        run_tests(sm_custom_output_stream=sm_output_stream_for_sm_class)
    finally:
        # Close StateMachine's dedicated log file if it was opened
        if sm_specific_log_fh:
            # Notify to original console (or tests.py log) that SM logging is complete
            print(f"StateMachine output was logged to {pathlib.Path.cwd() / 'state_machine_flows.log'}", file=sys.stdout)
            sm_specific_log_fh.close()

        # Restore tests.py's stdout and close its log file (if --log was active)
        if tests_script_log_fh:
            sys.stdout = original_stdout # Restore original stdout
            tests_script_log_fh.close()
            # Notify on the actual console that script logging occurred
            print(f"Test script output was logged to {pathlib.Path.cwd() / 'login_flows.log'}", file=original_stdout)
        elif args.log and not tests_script_log_fh:
             # --log was specified, but file opening failed. Error already printed.
            pass
