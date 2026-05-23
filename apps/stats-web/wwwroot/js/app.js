// M1 - User Access Management Start
// Guards the Module 1 web landing page and shows the authenticated user context.
const appMessage = document.querySelector("#app-message");
const landingWorkspace = document.querySelector("#landing-workspace");
const currentUserName = document.querySelector("#current-user-name");
const currentUserEmail = document.querySelector("#current-user-email");
const currentUserRole = document.querySelector("#current-user-role");
const manageUsersLink = document.querySelector("#manage-users-link");
const logoutButton = document.querySelector("#logout-button");

function setAppMessage(message, tone = "error") {
  appMessage.textContent = message;
  appMessage.dataset.tone = tone;
}

async function loadLandingPage() {
  if (!window.statsAccess.token()) {
    window.location.assign("/Login");
    return;
  }

  try {
    const user = await window.statsAccess.currentUser();
    if (user.must_change_password) {
      window.location.assign("/Login");
      return;
    }

    currentUserName.textContent = user.full_name || "Stats user";
    currentUserEmail.textContent = user.email;
    currentUserRole.textContent = user.role;
    manageUsersLink.hidden = user.role !== "admin";
    landingWorkspace.hidden = false;
    setAppMessage("Access granted.", "success");
  } catch (error) {
    sessionStorage.removeItem(window.statsAccess.tokenKey);
    setAppMessage(error.message || "Sign in again.");
    window.location.assign("/Login");
  }
}

logoutButton.addEventListener("click", () => {
  window.statsAccess.signOut();
});

loadLandingPage();
// M1 End
