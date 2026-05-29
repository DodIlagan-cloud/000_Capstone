// M1 - User Access Management Start
// Handles Module 1 administrator user list and temporary-password user creation.
const accessMessage = document.querySelector("#access-message");
const workspace = document.querySelector("#users-workspace");
const userRows = document.querySelector("#user-rows");
const createForm = document.querySelector("#create-user-form");
const createMessage = document.querySelector("#create-message");
const createSubmit = document.querySelector("#create-user-submit");
const isActiveInput = document.querySelector("#is-active");
const refreshUsersButton = document.querySelector("#refresh-users");
const logoutButton = document.querySelector("#logout-button");

// M1 - User Access Management Start
// Activates the custom temporary-password reveal control on the administrator form.
window.statsAccess.initPasswordVisibilityToggles();
// M1 End

function setMessage(node, message, tone = "error") {
  node.textContent = message;
  node.dataset.tone = tone;
}

function textCell(value, className = "") {
  const cell = document.createElement("td");
  cell.textContent = value || "-";
  cell.className = className;
  return cell;
}

function stateCell(value, pending = false) {
  const cell = document.createElement("td");
  const label = document.createElement("span");
  label.className = pending ? "state-pill pending" : "state-pill";
  label.textContent = value;
  cell.append(label);
  return cell;
}

function renderUsers(users) {
  userRows.replaceChildren();
  users.forEach((user) => {
    const row = document.createElement("tr");
    row.append(
      textCell(user.full_name, user.full_name ? "" : "cell-muted"),
      textCell(user.email),
      textCell(user.role),
      stateCell(user.is_active ? "Active" : "Inactive", !user.is_active),
      stateCell(user.must_change_password ? "Change required" : "Set", user.must_change_password),
    );
    userRows.append(row);
  });
}

async function loadUsers() {
  const response = await fetch(window.statsAccess.apiUrl("/api/v1/users"), {
    headers: window.statsAccess.authHeaders(),
  });
  if (!response.ok) {
    throw new Error("Administrator access is required.");
  }
  renderUsers(await response.json());
}

async function startPage() {
  if (!window.statsAccess.token()) {
    window.location.assign("/Login");
    return;
  }

  const user = await window.statsAccess.currentUser();
  if (user.must_change_password) {
    window.location.assign("/Login");
    return;
  }
  if (user.role !== "admin") {
    setMessage(accessMessage, "Administrator access is required.");
    return;
  }

  workspace.hidden = false;
  setMessage(accessMessage, `Signed in as ${user.email}.`, "success");
  await loadUsers();
}

createForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  createSubmit.disabled = true;
  setMessage(createMessage, "");

  try {
    const response = await fetch(window.statsAccess.apiUrl("/api/v1/users"), {
      method: "POST",
      headers: {
        ...window.statsAccess.authHeaders(),
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        email: createForm.email.value,
        full_name: createForm.full_name.value,
        password: createForm.password.value,
        role: createForm.role.value,
        is_active: isActiveInput.checked,
      }),
    });

    if (!response.ok) {
      throw new Error(response.status === 400 ? "Check the user details and use a unique email." : "User creation failed.");
    }

    const user = await response.json();
    createForm.reset();
    isActiveInput.checked = true;
    setMessage(createMessage, `${user.email} created. Password change is required on first login.`, "success");
    await loadUsers();
  } catch (error) {
    setMessage(createMessage, error.message || "User creation failed.");
  } finally {
    createSubmit.disabled = false;
  }
});

refreshUsersButton.addEventListener("click", async () => {
  try {
    await loadUsers();
    setMessage(accessMessage, "User list refreshed.", "success");
  } catch (error) {
    setMessage(accessMessage, error.message || "Could not refresh users.");
  }
});

logoutButton.addEventListener("click", () => {
  window.statsAccess.signOut();
});

startPage().catch((error) => {
  setMessage(accessMessage, error.message || "Could not load user management.");
});
// M1 End
