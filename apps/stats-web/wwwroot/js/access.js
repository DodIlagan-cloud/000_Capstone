// M1 - User Access Management Start
// Shares browser-session token and backend API helpers across the Module 1 Razor pages.
window.statsAccess = {
  tokenKey: "stats.accessToken",
  tokenCookieName: "stats_access_token",
  refreshTimer: null,
  refreshInFlight: null,
  refreshSkewSeconds: 15 * 60,
  apiUrl(path) {
    return `${document.body.dataset.apiBaseUrl}${path}`;
  },
  setToken(token) {
    sessionStorage.setItem(this.tokenKey, token);
    this.setTokenCookie(token);
  },
  setTokenCookie(token) {
    document.cookie = `${this.tokenCookieName}=${encodeURIComponent(token)}; path=/; SameSite=Lax`;
  },
  cookieToken() {
    const prefix = `${this.tokenCookieName}=`;
    const cookie = document.cookie
      .split(";")
      .map((value) => value.trim())
      .find((value) => value.startsWith(prefix));
    return cookie ? decodeURIComponent(cookie.slice(prefix.length)) : null;
  },
  token() {
    const sessionToken = sessionStorage.getItem(this.tokenKey);
    if (sessionToken) {
      return sessionToken;
    }

    const cookieToken = this.cookieToken();
    if (cookieToken) {
      sessionStorage.setItem(this.tokenKey, cookieToken);
    }

    return cookieToken;
  },
  clearToken() {
    sessionStorage.removeItem(this.tokenKey);
    document.cookie = `${this.tokenCookieName}=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT; SameSite=Lax`;
    if (this.refreshTimer) {
      window.clearInterval(this.refreshTimer);
      this.refreshTimer = null;
    }
  },
  authHeaders() {
    return {
      Authorization: `Bearer ${this.token()}`,
    };
  },
  tokenPayload() {
    const token = this.token();
    if (!token) {
      return null;
    }

    const parts = token.split(".");
    if (parts.length < 2) {
      return null;
    }

    try {
      const payload = parts[1].replace(/-/g, "+").replace(/_/g, "/");
      const paddedPayload = payload.padEnd(payload.length + ((4 - (payload.length % 4)) % 4), "=");
      return JSON.parse(window.atob(paddedPayload));
    } catch {
      return null;
    }
  },
  tokenExpiresWithin(seconds) {
    const payload = this.tokenPayload();
    if (!payload?.exp) {
      return true;
    }

    return payload.exp * 1000 <= Date.now() + seconds * 1000;
  },
  async refreshSession(options = {}) {
    const token = this.token();
    if (!token) {
      throw new Error("Session expired. Sign in again.");
    }
    if (!options.force && !this.tokenExpiresWithin(this.refreshSkewSeconds)) {
      return token;
    }
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
        const payload = await response.json();
        this.setToken(payload.access_token);
        return payload.access_token;
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
  signOut() {
    this.clearToken();
    window.location.assign("/Login");
  },
  async currentUser() {
    const token = this.token();
    if (!token) {
      throw new Error("Session expired. Sign in again.");
    }

    await this.refreshSession();
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
