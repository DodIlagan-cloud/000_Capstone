// M1 - User Access Management Start
// Shares server-cookie session and backend API helpers across the Module 1 Razor pages.
window.statsAccess = {
  refreshTimer: null,
  refreshInFlight: null,
  sessionMarker: "server-cookie-session",
  apiUrl(path) {
    return `${document.body.dataset.apiBaseUrl}${path}`;
  },
  setToken() {
    // The real bearer token is now held only in a server-set HttpOnly cookie.
    return this.sessionMarker;
  },
  token() {
    return this.sessionMarker;
  },
  async clearToken() {
    if (this.refreshTimer) {
      window.clearInterval(this.refreshTimer);
      this.refreshTimer = null;
    }
    try {
      await fetch(this.apiUrl("/api/v1/auth/logout"), {
        method: "POST",
        headers: this.authHeaders(),
      });
    } catch {
      // Ignore logout transport errors; redirecting to Login clears the user flow.
    }
  },
  authHeaders() {
    return {
      "X-Stats-CSRF": "1",
    };
  },
  async refreshSession(options = {}) {
    if (this.refreshInFlight) {
      return this.refreshInFlight;
    }

    this.refreshInFlight = fetch(this.apiUrl("/api/v1/auth/refresh"), {
      method: "POST",
      headers: this.authHeaders(),
    })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error("Session expired. Sign in again.");
        }
        return this.sessionMarker;
      })
      .finally(() => {
        this.refreshInFlight = null;
      });

    return this.refreshInFlight;
  },
  startSessionKeepAlive(intervalMs = 10 * 60 * 1000) {
    if (this.refreshTimer) {
      return;
    }

    const refresh = () => {
      if (document.visibilityState === "hidden") {
        return;
      }
      this.refreshSession().catch(() => {
        // Let the next protected action show the normal session-expired path.
      });
    };
    refresh();
    this.refreshTimer = window.setInterval(refresh, intervalMs);
    document.addEventListener("visibilitychange", refresh);
  },
  async signOut() {
    await this.clearToken();
    window.location.assign("/Login");
  },
  async currentUser() {
    let response = await fetch(this.apiUrl("/api/v1/auth/me"), {
      headers: this.authHeaders(),
    });

    if (response.status === 401) {
      await this.refreshSession({ force: true });
      response = await fetch(this.apiUrl("/api/v1/auth/me"), {
        headers: this.authHeaders(),
      });
    }

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
