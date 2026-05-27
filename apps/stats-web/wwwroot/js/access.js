// M1 - User Access Management Start
// Shares browser-session token and backend API helpers across the Module 1 Razor pages.
window.statsAccess = {
  tokenKey: "stats.accessToken",
  apiUrl(path) {
    return `${document.body.dataset.apiBaseUrl}${path}`;
  },
  token() {
    return sessionStorage.getItem(this.tokenKey);
  },
  authHeaders() {
    return {
      Authorization: `Bearer ${this.token()}`,
    };
  },
  signOut() {
    sessionStorage.removeItem(this.tokenKey);
    window.location.assign("/Login");
  },
  async currentUser() {
    const response = await fetch(this.apiUrl("/api/v1/auth/me"), {
      headers: this.authHeaders(),
    });

    if (!response.ok) {
      throw new Error("Session expired. Sign in again.");
    }

    return response.json();
  },
  // M1 - User Access Management Start
  // Enables a single custom show/hide password control across browsers.
  initPasswordVisibilityToggles() {
    const icon = (isVisible) => `
      <svg class="password-toggle-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <path d="M2.8 12s3.4-5.4 9.2-5.4S21.2 12 21.2 12s-3.4 5.4-9.2 5.4S2.8 12 2.8 12Z"></path>
        <circle cx="12" cy="12" r="2.6"></circle>
        ${isVisible ? '<path class="password-toggle-slash" d="M4.5 4.5 19.5 19.5"></path>' : ""}
      </svg>
    `;

    document.querySelectorAll("[data-password-toggle]").forEach((toggle) => {
      const input = document.getElementById(toggle.dataset.passwordToggle);
      if (!input) {
        return;
      }

      const showLabel = toggle.getAttribute("aria-label") || "Show password";
      const hideLabel = showLabel.replace("Show", "Hide");
      toggle.innerHTML = icon(false);

      toggle.addEventListener("click", () => {
        const isHidden = input.type === "password";
        input.type = isHidden ? "text" : "password";
        toggle.setAttribute("aria-label", isHidden ? hideLabel : showLabel);
        toggle.setAttribute("aria-pressed", String(isHidden));
        toggle.setAttribute("title", isHidden ? hideLabel : showLabel);
        toggle.innerHTML = icon(isHidden);
      });
    });
  },
  // M1 End
};
// M1 End
