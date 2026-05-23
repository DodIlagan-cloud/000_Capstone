-- M1 - User Access Management Start
-- Direct PostgreSQL evidence query showing the admin and created test user are saved in the shared stats database.
SELECT
    email,
    full_name,
    role,
    is_active,
    must_change_password
FROM users
WHERE email IN (
    'm1.regression.admin.20260523@example.com',
    'm1.regression.user.20260523@example.com'
)
ORDER BY email;
-- M1 End
