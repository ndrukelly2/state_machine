# YAML-Driven State Machine For ID90 Account Access

This project implements a login state machine driven by YAML configuration files. It includes implementations in both JavaScript (untested) and Python (tested), along with test runners for validating state transitions based on scenarios defined in `tests.yaml`.

## Overview
The account access state machine manages transitions between different states based on events and a context. States, transitions, and test scenarios are defined in external YAML files, making the logic configurable without code changes.
The initial resolve(username) call sets our context object with combinations of the following values:

```javascript
ctx_options = {
    "resolver_match": [
        "exact",    // username exactly matched an existing account
        "multiple", // username matched more than one account
        "none"      // username did not match any account
    ],
    "flight_access": [
        "yes",      // user has flight-access privileges
        "no"        // user does not have flight-access
    ],
    "first_login": [
        "yes",      // this is the user's first successful login
        "no"        // user has logged in before
    ],
    "login_method": [
        "sso",      // user logs in via SSO
        "password"  // user logs in via password
    ],
    "identifier_type": [
        "email",      // the original input was recognized as an email
        "employeeid"  // the original input was treated as an employee ID
    ],
    "domain_match": [
        "yes",      // submitted email's domain matches an approved org
        "no"        // submitted email's domain does not match
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
*   This is also the same spreadsheet linked in our Confluence Documentation
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

To run the code you can set vars at bottom of state_machine.js file and run it:
```node state_machine.js```

To run the test suite that picks up all tests defined in tests.yaml:
```node tests.js```

## Client-to-Server Communication

### TypeScript Interface Definitions

#### Base Event Payload
```typescript
export interface BaseEventPayload {
  step: string;
  event: string;
  token: string;
}
```

#### Username Entry Events
```typescript
export interface SubmitUsernamePayload extends BaseEventPayload {
  event: "submitUsername";
  data: {
    identifier: string; // username, email, or employee ID
  };
}
```

#### Password Entry Events
```typescript
export interface SubmitPasswordPayload extends BaseEventPayload {
  event: "submitPassword";
  data: {
    password: string;
  };
}

export interface ForgotPasswordPayload extends BaseEventPayload {
  event: "forgotPassword";
  data?: {}; // Note that users without employeeID as username cannot use the standard password recovery flow (need to supress this link in these cases)
}
```

#### Temporary Password Entry Events
```typescript
export interface SubmitTempPasswordPayload extends BaseEventPayload {
  event: "submitPassword";
  data: {
    password: string;
  };
}
```

#### Setup Password Events
```typescript
export interface ProcessTokenPayload extends BaseEventPayload {
  event: "processToken";
  data: {
    token: string; // Token from email link passed to server to pick up where we left off
  };
}

export interface CreatePasswordPayload extends BaseEventPayload {
  event: "createPassword";
  data: {
    password: string;
    confirmPassword: string;
  };
}
```

#### Update Password Events
```typescript
export interface ProcessResetTokenPayload extends BaseEventPayload {
  event: "processToken";
  data: {
    token: string; // Reset token from email link
  };
}

export interface UpdatePasswordPayload extends BaseEventPayload {
  event: "updatePassword";
  data: {
    password: string;
    confirmPassword: string;
  };
}

export interface SkipPasswordUpdatePayload extends BaseEventPayload {
  event: "skip";
  data?: {}; // Token from email link passed to server to pick up where we left off
}
```

#### Forgot Password Email Events
```typescript
export interface SubmitForgotPasswordEmailPayload extends BaseEventPayload {
  event: "forgotPasswordEmailLinkSuccess";
  data: {
    email: string; // this is automatically triggered when the user lands on ForgotPasswordEmailLinkUI after clicking forgotPassword
  };
}

export interface ResendForgotPasswordEmailPayload extends BaseEventPayload {
  event: "resendEmail";
  data?: {}; // This 'resend email' button triggers the backend to resend the password recovery email in case they never got it.
}
```

#### Password Email Link Events
```typescript
export interface PasswordEmailLinkSuccessPayload extends BaseEventPayload {
  event: "passwordEmailLinkSuccess";
  data?: {}; // this is automatically triggered when the user lands on PasswordEmailLinkUI during new account setup flows (when email is present as username)

export interface ResendPasswordEmailPayload extends BaseEventPayload {
  event: "resendEmail";
  data?: {}; // No additional data required
}
```

#### SSO Redirect Events [unsure if this is how we should handle sso flows.....]
```typescript
export interface SSOContinuePayload extends BaseEventPayload {
  event: "continue";
  data: {
    ssoToken?: string; // SSO authentication token
    userInfo?: any; // User information from SSO provider
  };
}

export interface SSOFailurePayload extends BaseEventPayload {
  event: "failure";
  data: {
    error: string; // Error message from SSO provider
    errorCode?: string; // Error code if available
  };
}

export interface SSOCancelledPayload extends BaseEventPayload {
  event: "cancelled";
  data?: {}; // No additional data required
}
```

#### Organization Picker Events [basically another resolve call from here but with company info added]
#### Note: When a employeeID is submitted as the identifier we will want to math with a "LIKE" db call.
####    Our goal here is to let users login with their employeeID even in cases when they were told to put
####    special characters around it. For example both "AA12345" and "12345" would work as the identifier
####    because we are also passing companyCode (eg AA). This is a big CS call driver.
```typescript
export interface OrganizationSelectedPayload extends BaseEventPayload {
  event: "organizationSelected";
  data: {
    companyCode: string; // Selected organization code
    companyDisplayName: string; // Selected organization display name
    identifier?: string; // Updated user identifier if changed. There are cases where this might not be passed. An example is when a user picks their company from the dropdown and all those company users are SSO by defaul....we will automatically trigger the SSO redirect. This is how it works today.
  };
}
```


### Union Type for All Events
```typescript
export type StateMachineEventPayload = 
  | SubmitUsernamePayload
  | SubmitPasswordPayload
  | ForgotPasswordPayload
  | SubmitTempPasswordPayload
  | ProcessTokenPayload
  | CreatePasswordPayload
  | ProcessResetTokenPayload
  | UpdatePasswordPayload
  | SkipPasswordUpdatePayload
  | SubmitForgotPasswordEmailPayload
  | ResendForgotPasswordEmailPayload
  | PasswordEmailLinkSuccessPayload
  | ResendPasswordEmailPayload
  | SSOContinuePayload
  | SSOFailurePayload
  | SSOCancelledPayload
  | OrganizationSelectedPayload
```

## Server-to-Client Communication

### Variables Passed to Client for Each UI Interface

Each UI interface receives a payload containing specific variables. Here's what each interface receives:

#### UsernameEntryView (`usernameEntryUI`)
```typescript
interface UsernameEntryViewPayload {
  token?: string;
  state_id: "UsernameEntryView";
  interface: "usernameEntryUI";
  cs_contact: boolean;
  identifier?: string;           // Pre-fill username if available (eg return from SSO)
  error_id?: string | null;    // Error identifier if applicable
}
```

#### TempPasswordEntryView (`tempPasswordEntryUI`)
```typescript
interface TempPasswordEntryViewPayload {
  token: string;
  state_id: "TempPasswordEntryView";
  interface: "tempPasswordEntryUI";
  cs_contact: boolean;
  identifier: string;           // Display who the temp password is for
  company_code: string;
  company_display_name: string;
  error_id?: string | null;
}
```

#### PasswordEntryView (`passwordEntryUI`)
```typescript
interface PasswordEntryViewPayload {
  token: string;
  state_id: "PasswordEntryView";
  interface: "passwordEntryUI";
  cs_contact: boolean;
  identifier?: string;           // Display who is logging in
  allow_forgot_password: boolean;  // false if identifier_type is "employeeid"
  company_code: string;
  company_display_name: string;
  error_id?: string | null;
}
```

#### SetupPasswordView (`setupPasswordUI`)
#### Password setup email links will be direct to this interface. When clicking on the email link they will be redirect here with and then passed the token from the tokenized link in the email. The server will then validate the token, and if valid, will be able to create their new password.
```typescript
interface SetupPasswordViewPayload {
  token: string; 
  state_id: "SetupPasswordView";
  interface: "setupPasswordUI";
  cs_contact: boolean;
  token_is_valid: boolean;     // Token validation status
  identifier: string;
  email?: string;
  company_code: string;
  company_display_name: string;
  prompt_check_email: boolean; // This will be true until the token validation is done and will show copy like "check email for password setup link". When taken_is_valid: true, prompt_check_email: false, and we will show the password entry fields.
  error_id?: string | null;
}
```

#### UpdatePasswordView (`updatePasswordUI`)
#### Password update email links will be direct to this interface. When clicking on the email link they will be redirect here with and then passed the token from the tokenized link in the email. The server will then validate the token, and if valid, will be able to create their new password.
```typescript
interface UpdatePasswordViewPayload {
  token: string;
  state_id: "UpdatePasswordView";
  interface: "updatePasswordUI";
  cs_contact: boolean;
  token_is_valid: boolean;     // Token validation status
  identifier: string;
  email?: string;
  company_code: string;
  company_display_name: string;
  prompt_check_email: boolean; // This will be true until the token validation is done and will show copy like "check email for password setup link". When taken_is_valid: true, prompt_check_email: false, and we will show the password entry fields.
  error_id?: string | null;
}
```

#### PasswordEmailLinkView (`passwordEmailLinkUI`)
```typescript
interface PasswordEmailLinkViewPayload {
  token: string;
  state_id: "PasswordEmailLinkView";
  interface: "passwordEmailLinkUI";
  identifier: string;
  email: string;
  company_code?: string;
  company_display_name?: string;
  cs_contact: boolean;
  error_id?: string | null;
}
```

#### SSORedirectView (`ssoRedirectUI`)
### Note: we do not actually render this interface. This is just to trigger the redirect to users SSO endpoint. 
```typescript
interface SSORedirectViewPayload {
  token: string;
  state_id: "SSORedirectView";
  interface: "ssoRedirectUI";
  identifier?: string;         // User identifier for SSO
  email?: string;
  company_code: string;
  company_display_name: string;
  sso_url: string;
  error_id?: string | null;
}
```

#### LoggedInView (`loggedInUI`)
```typescript
interface LoggedInViewPayload {
  token: string;
  state_id: "LoggedInView";
  interface: "loggedInUI";
  identifier?: string;
  display_name?: string;
  access_token?: string;       // Token for user session
  prompt_for_email_on_login: boolean;  // true if employeeid + first_login and we want to update their username to an email. Should launch a modal or something to collect.
  error_id?: string | null;
}
```

#### ForgotPasswordEmailLinkView (`forgotPasswordEmailLinkUI`)
```typescript
interface ForgotPasswordEmailLinkViewPayload {
  token: string;
  state_id: "ForgotPasswordEmailLinkView";
  interface: "forgotPasswordEmailLinkUI";
  identifier: string;
  email: string;
  company_code?: string;
  company_display_name?: string;
  cs_contact: boolean;
  error_id?: string | null;
}
```

#### OrganizationPickerView (`organizationPickerUI`)
#### This essentially fires the resolve call again but with the company code + identfier combined. If a user picks a company from the drop down that is SSO by defaul, we want to launch their SSO redirect and not require the username at all (this is how it works today).
```typescript
interface OrganizationPickerViewPayload {
  state_id: "OrganizationPickerView";
  interface: "organizationPickerUI";
  cs_contact: boolean;
  company_list?: any[];        // List of companies available
  identifier?: string;         // User identifier for the picker
  email?: string;              // Could be null if not available
  company_code?: string;       // Airline code
  company_display_name?: string;
  token?: string;         // Prior state before going to organization picker if any
  show_username_on_picker: boolean;  // Toggle username field visibility. I think this will always be true though.
  error_id?: string | null;
}
```

### Error Handling

All interfaces can receive error identifiers in the `error_id` field:
- `EMAIL_LINK_ERR_1` - Error sending account setup email
- `EMAIL_LINK_ERR_2` - Error sending password reset email
- `SSO_CANCELLED` - User cancelled SSO process
- `RESOLVE_NO_MATCH_001` - Username resolution failed
- `INVALID_RESET_TOKEN` - Password reset token is invalid
- `EXPIRED_RESET_TOKEN` - Password reset token has expired
- `INVALID_SETUP_TOKEN` - Password setup token is invalid
- `EXPIRED_SETUP_TOKEN` - Password setup token has expired
- `CREATE_PW_FAILED` - Password creation failed
- `UPDATE_PW_FAILED` - Password update failed

### Customer Support Contact

Views with `cs_contact: true` will include this flag in their payload, indicating that customer support contact options should be displayed to the user.


