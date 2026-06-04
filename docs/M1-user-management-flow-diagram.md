<!-- M1 - User Access Management Start -->
<!-- Illustrates the Module 1 bootstrap, login, authorization, and user-addition flow. -->

# M1 User Access Management Activity Diagram

## Scope

<!-- This activity diagram shows the Module 1 path from initial administrator setup to authenticated access and administrator-managed user creation across three roles: User, Frontend, and Backend. -->
<!-- This activity diagram shows the Module 1 path from initial administrator setup to authenticated access and administrator-managed user creation across architecture-aligned swimlanes: User, ASP.NET Core Stats Web frontend, Python FastAPI Identity API, and the shared PostgreSQL `stats` database. -->
This activity workflow shows the Module 1 path from initial administrator setup to authenticated access and administrator-managed user creation across architecture-aligned swimlanes: User / Project Operator, ASP.NET Core Stats Web frontend, Python FastAPI Identity Access API, and the shared PostgreSQL `stats` database.

The PDF-friendly copy is saved as `docs/M1-user-management-activity-workflow.pdf`.

<!-- The earlier wide left-to-right Mermaid flowchart was replaced because it did not fit a normal PDF page cleanly. -->
```mermaid
sequenceDiagram
    autonumber
    actor User as User / Project Operator
    participant Web as ASP.NET Core Stats Web<br/>Razor Pages + JavaScript
    participant API as Python FastAPI<br/>Identity Access API
    database DB as PostgreSQL<br/>stats database

    User->>API: Run first-admin bootstrap command
    API->>API: Load M1 config and database URL
    API->>DB: Check whether any user exists
    alt No user exists
        API->>DB: Create M1 user table if needed
        API->>DB: Store first active admin with hashed password
    else User already exists
        API-->>User: Reject bootstrap attempt
    end

    User->>Web: Open /Login and enter credentials
    Web->>API: POST login request
    API->>DB: Read user account and password hash
    alt Credentials invalid or account inactive
        API-->>Web: Return controlled login error
        Web-->>User: Show login error
    else Credentials accepted
        API-->>Web: Return bearer token and password state
        Web->>Web: Store bearer token in browser session storage
        Web->>API: Request current-user profile
        API-->>Web: Return current-user role and status
    end

    alt Password setup required
        Web-->>User: Display first-login password setup form
        User->>Web: Enter new password
        Web->>API: Submit password change request
        API->>DB: Update password hash and password-change flag
        API-->>Web: Confirm password change
    end

    Web-->>User: Open authenticated app landing page
    alt User is administrator
        User->>Web: Open /Users and enter new user details
        Web->>API: Submit add-user request with admin token
        API->>API: Validate admin authorization and user fields
        alt New user data invalid or duplicate
            API-->>Web: Return validation error
            Web-->>User: Show user creation error
        else New user data accepted
            API->>DB: Store new user with hashed temporary password
            API-->>Web: Return user creation result
            Web-->>User: Show created user
        end
    else User is standard user
        Web-->>User: Allow authenticated standard-user access only
    end

    User->>Web: Sign out
    Web->>Web: Clear browser session token
```

## Notes

<!-- - The User lane includes the local first-admin setup action because it is triggered manually by the project operator. -->
- The User / Project Operator lane includes the local first-admin setup action because it is triggered manually by the project operator.
<!-- - The Frontend lane covers the ASP.NET Core `/Login` page, first-login password setup, the authenticated `/` app landing page, the `/Users` administrator list and create-user page, session token handling, and sign out. -->
- The ASP.NET Core Stats Web frontend lane covers the Razor Pages `/Login` page, first-login password setup, the authenticated `/` app landing page, the `/Users` administrator list and create-user page, browser session token handling, JavaScript API calls, password visibility behavior, and sign out.
<!-- - The Backend lane covers bootstrap protection, credential validation, token validation, authorization, and user persistence. -->
- The Python FastAPI Identity Access API lane covers config loading, bootstrap protection, credential validation, token validation, authorization, password-state changes, and identity API responses.
- The PostgreSQL `stats` database lane shows that M1 identity records are persisted in the shared application database rather than a module-only database.
- Admin-created users receive temporary passwords in M1 and follow the same first-login password setup branch before ordinary access.
- Standard users cannot create or manage other users.
- Later modules can reuse the current-user and role checks introduced in M1.

<!-- M1 End -->
