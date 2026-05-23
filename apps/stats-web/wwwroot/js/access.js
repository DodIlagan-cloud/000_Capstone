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
};
// M1 End
