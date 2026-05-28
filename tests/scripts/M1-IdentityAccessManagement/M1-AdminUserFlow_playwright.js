// M1 - User Access Management Start
// Drives the visible Edge admin-created user and first-login password setup evidence flow.
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const repoRoot = path.resolve(__dirname, "..", "..");
const settings = JSON.parse(fs.readFileSync(path.join(repoRoot, "test-scripts", "config", "test-script-settings.json"), "utf8"));
const localSettingsPath = path.join(repoRoot, "test-scripts", "config", "test-script-settings.local.json");
if (fs.existsSync(localSettingsPath)) {
  const localSettings = JSON.parse(fs.readFileSync(localSettingsPath, "utf8"));
  for (const section of ["evidenceFolders", "localPaths", "runtime"]) {
    settings[section] = { ...(settings[section] || {}), ...(localSettings[section] || {}) };
  }
}

function configuredPath(section, key) {
  const value = settings[section][key];
  return path.isAbsolute(value) ? value : path.join(repoRoot, value);
}

function appUrl(route = "") {
  return `${settings.runtime.statsWebBaseUrl.replace(/\/$/, "")}/${route.replace(/^\//, "")}`;
}

const outputDir = configuredPath("evidenceFolders", "M1AdminUserFlow");
const adminEmail = "m1.regression.admin.20260523@example.com";
const adminPassword = "AdminTest123";
const newUserEmail = "m1.regression.user.20260523@example.com";
const newUserTempPassword = "UserTemp123";
const newUserFinalPassword = "UserReady123";

function markerPath(name, suffix) {
  return path.join(outputDir, `${name}.${suffix}`);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function checkpoint(name) {
  fs.writeFileSync(markerPath(name, "ready"), new Date().toISOString());
  for (let index = 0; index < 120; index += 1) {
    if (fs.existsSync(markerPath(name, "done"))) {
      return;
    }
    await sleep(250);
  }
  throw new Error(`Timed out waiting for screenshot checkpoint: ${name}`);
}

async function main() {
  fs.mkdirSync(outputDir, { recursive: true });
  for (const file of fs.readdirSync(outputDir)) {
    if (file.endsWith(".ready") || file.endsWith(".done")) {
      fs.rmSync(path.join(outputDir, file), { force: true });
    }
  }

  const browser = await chromium.launch({
    channel: "msedge",
    headless: false,
    args: ["--window-position=25,25", "--window-size=1220,860"],
  });

  const page = await browser.newPage({ viewport: { width: 1180, height: 760 } });
  await page.goto(appUrl("Login"), { waitUntil: "networkidle" });
  await page.fill("#email", adminEmail);
  await page.fill("#password", adminPassword);
  await page.click("#login-submit");
  await page.waitForURL(appUrl(), { timeout: 10000 });

  await page.goto(appUrl("Users"), { waitUntil: "networkidle" });
  await page.waitForSelector("#users-workspace:not([hidden])", { timeout: 10000 });
  await page.fill("#full-name", "Module One Regression User");
  await page.fill("#user-email", newUserEmail);
  await page.fill("#temporary-password", newUserTempPassword);
  await page.selectOption("#role", "user");
  await page.check("#is-active");
  await page.click("#create-user-submit");
  await page.waitForFunction(
    (email) =>
      document.querySelector("#create-message")?.textContent.includes(email) &&
      Array.from(document.querySelectorAll("#user-rows tr")).some((row) => row.textContent.includes(email)),
    newUserEmail,
    { timeout: 10000 },
  );
  await page.bringToFront();
  await checkpoint("admin-created-user");

  await page.click("#logout-button");
  await page.waitForURL(appUrl("Login"), { timeout: 10000 });
  await page.bringToFront();
  await checkpoint("admin-signed-out");

  await page.fill("#email", newUserEmail);
  await page.fill("#password", newUserTempPassword);
  await page.click("#login-submit");
  await page.waitForSelector("#password-setup-form:not([hidden])", { timeout: 10000 });
  await page.bringToFront();
  await checkpoint("new-user-password-setup");

  await page.fill("#new-password", newUserFinalPassword);
  await page.fill("#confirm-password", newUserFinalPassword);
  await page.click("#password-setup-submit");
  await page.waitForURL(appUrl(), { timeout: 10000 });
  await page.waitForFunction(
    (email) => document.querySelector("#current-user-email")?.textContent.includes(email),
    newUserEmail,
    { timeout: 10000 },
  );
  await page.bringToFront();
  await checkpoint("new-user-main-app");

  await browser.close();
  console.log("M1 admin-created user browser evidence");
  console.log(`Admin test user: ${adminEmail}`);
  console.log(`Created user: ${newUserEmail}`);
  console.log("Temporary and reset passwords are test-only values.");
  console.log("Result: PASSED");
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
// M1 End
