# YAML-Driven State Machine For ID90 Account Access
This project implements login a state machine driven by YAML configuration files. It includes implementations in both JavaScript (untested) and Python (tested), along with test runners for validating state transitions based on scenarios defined in `tests.yaml`.

## Overview
The account access state machine manages transitions between different states based on events and a context. States, transitions, and test scenarios are defined in external YAML files, making the logic configurable without code changes.
The intial resolve(username) call sets our context object with combinations of the following values:
```        ctx_options = {
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
```

## Features
*   **YAML Configuration**: States and transitions are defined in `states.yaml` and `transitions.yaml`.
*   **Dual Implementations**: Available in JavaScript ([state_machine.js](state_machine.js)) and Python ([state_machine.py](state_machine.py)).
*   **Test Suite**: Scenarios are defined in `tests.yaml` and can be run using [test.js](test.js) (for the JavaScript version) or [tests.py](tests.py) (for the Python version).
*   **Debug Output**: Both implementations provide detailed console output for tracing state transitions and context changes.

## Interface Names
*   All interface names should match what is defined in the Access Flows spreadsheet linked here (with one exception that our state machine appends 'UI' to each name): https://docs.google.com/spreadsheets/d/17uMH_2Ncsnen4JV32JcyiDsDuHLbaZYvdPp1-0moz0I/edit?usp=sharing
*   This is also the same spreadhseet linked in our Confluence Documentation
*   Note that all the Condition/Event names in this spreadsheet are a bit different than what is in this state machine as they were initially placeholders.

## Setup

### Python [this code is tested and works]
You'll need Python 3 installed. Install the PyYAML dependency:
```pip install pyyaml```

To run the code you can set vars at bottom of state_machine.py file and run it:
```python3 state_machine.py```

To run the test suite that picks up all tests defined in tests.yaml:
```python3 tests.py```

### JavaScript [this is translated from the python code and is untested]
You'll need Node.js and npm installed. Install the `js-yaml` dependency:
```npm install js-yaml```

To run the code you can set vars at bottom of state_machine.py file and run it:
```node state_machine.js```

To run the test suite that picks up all tests defined in tests.yaml:
```node tests.js```


