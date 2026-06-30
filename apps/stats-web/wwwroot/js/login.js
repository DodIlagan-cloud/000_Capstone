// M1 - User Access Management Start
// Handles Module 1 login and first-login password setup before app entry.
const loginForm = document.querySelector("#login-form");
const loginMessage = document.querySelector("#login-message");
const loginSubmit = document.querySelector("#login-submit");
const passwordSetupForm = document.querySelector("#password-setup-form");
const passwordSetupMessage = document.querySelector("#password-setup-message");
const passwordSetupSubmit = document.querySelector("#password-setup-submit");

// M1 - User Access Management Start
// Activates custom password reveal controls for login and first-login setup.
window.statsAccess.initPasswordVisibilityToggles();
// M1 End

function setMessage(node, message, tone = "error") {
  node.textContent = message;
  node.dataset.tone = tone;
}

function showPasswordSetup(message) {
  loginForm.hidden = true;
  passwordSetupForm.hidden = false;
  setMessage(loginMessage, "");
  setMessage(passwordSetupMessage, message);
}

async function continueFromSession() {
  try {
    const user = await window.statsAccess.currentUser();
    if (user.must_change_password) {
      showPasswordSetup("A new password is required before continuing.");
      return;
    }
    window.location.assign("/");
  } catch {
    await window.statsAccess.clearToken();
  }
}

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  loginSubmit.disabled = true;
  setMessage(loginMessage, "");

  try {
    const response = await fetch(window.statsAccess.apiUrl("/api/v1/auth/login"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        email: loginForm.email.value,
        password: loginForm.password.value,
      }),
    });

    if (!response.ok) {
      throw new Error(response.status === 403 ? "This account is inactive." : "Email or password is incorrect.");
    }

    await response.json();
    window.statsAccess.setToken();
    const user = await window.statsAccess.currentUser();
    loginForm.reset();

    if (user.must_change_password) {
      showPasswordSetup("A new password is required before continuing.");
      return;
    }

    window.location.assign("/");
  } catch (error) {
    await window.statsAccess.clearToken();
    setMessage(loginMessage, error.message || "Sign in failed.");
  } finally {
    loginSubmit.disabled = false;
  }
});

passwordSetupForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const newPassword = passwordSetupForm.new_password.value;

  if (newPassword !== passwordSetupForm.confirm_password.value) {
    setMessage(passwordSetupMessage, "Passwords must match.");
    return;
  }

  passwordSetupSubmit.disabled = true;
  setMessage(passwordSetupMessage, "");

  try {
    const response = await fetch(window.statsAccess.apiUrl("/api/v1/auth/change-password"), {
      method: "POST",
      headers: {
        ...window.statsAccess.authHeaders(),
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        new_password: newPassword,
      }),
    });

    if (!response.ok) {
      throw new Error("Choose a password with at least eight characters, one letter, and one number.");
    }

    passwordSetupForm.reset();
    window.location.assign("/");
  } catch (error) {
    setMessage(passwordSetupMessage, error.message || "Password setup failed.");
  } finally {
    passwordSetupSubmit.disabled = false;
  }
});

continueFromSession();
// M1 End
