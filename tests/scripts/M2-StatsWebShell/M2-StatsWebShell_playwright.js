// M2 - Stats Web Shell Start
// Drives visible Edge checkpoints for the M2 dashboard-first shell evidence flow.
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

const outputDir = configuredPath("evidenceFolders", "M2StatsWebShell");
const adminEmail = "m2.evidence.admin.20260524@example.com";
const adminPassword = "M2EvidenceTemp123";
const adminFinalPassword = "M2EvidenceReady123";
const standardEmail = "m2.evidence.user.20260524@example.com";
const standardTempPassword = "M2UserTemp123";
const standardFinalPassword = "M2UserReady123";

function markerPath(name, suffix) {
  return path.join(outputDir, `${name}.${suffix}`);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function checkpoint(name) {
  fs.writeFileSync(markerPath(name, "ready"), new Date().toISOString());
  for (let index = 0; index < 160; index += 1) {
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
    args: ["--window-position=25,25", "--window-size=1240,880"],
  });

  const page = await browser.newPage({ viewport: { width: 1200, height: 780 } });
  await page.goto(appUrl("Login"), { waitUntil: "networkidle" });
  await checkpoint("login");

  await page.fill("#email", adminEmail);
  await page.fill("#password", adminPassword);
  await page.click("#login-submit");
  await page.waitForSelector("#password-setup-form:not([hidden])", { timeout: 10000 });
  await checkpoint("password-setup");

  await page.fill("#new-password", adminFinalPassword);
  await page.fill("#confirm-password", adminFinalPassword);
  await page.click("#password-setup-submit");
  await page.waitForURL(appUrl(), { timeout: 10000 });
  await page.waitForSelector("#landing-workspace:not([hidden])", { timeout: 10000 });
  await checkpoint("dashboard-home");

  await page.goto(appUrl("Upload"), { waitUntil: "networkidle" });
  await page.waitForSelector("#upload-title", { timeout: 10000 });
  await checkpoint("upload-documents");

  await page.goto(appUrl("EmailSetup"), { waitUntil: "networkidle" });
  await page.waitForSelector("#email-setup-title", { timeout: 10000 });
  await checkpoint("email-setup");

  await page.goto(appUrl("Documents"), { waitUntil: "networkidle" });
  await page.waitForSelector("#documents-title", { timeout: 10000 });
  await checkpoint("documents");

  await page.goto(appUrl("Reports"), { waitUntil: "networkidle" });
  await page.waitForSelector("#reports-title", { timeout: 10000 });
  await checkpoint("reports");

  await page.goto(appUrl("Users"), { waitUntil: "networkidle" });
  await page.waitForSelector("#users-workspace:not([hidden])", { timeout: 10000 });
  await checkpoint("admin-users");

  await page.fill("#full-name", "Standard User");
  await page.fill("#user-email", standardEmail);
  await page.fill("#temporary-password", standardTempPassword);
  await page.selectOption("#role", "user");
  await page.check("#is-active");
  await page.click("#create-user-submit");
  await page.waitForFunction(
    (email) =>
      document.querySelector("#create-message")?.textContent.includes(email) &&
      Array.from(document.querySelectorAll("#user-rows tr")).some((row) => row.textContent.includes(email)),
    standardEmail,
    { timeout: 10000 },
  );

  await page.click("#logout-button");
  await page.waitForURL(appUrl("Login"), { timeout: 10000 });
  await page.fill("#email", standardEmail);
  await page.fill("#password", standardTempPassword);
  await page.click("#login-submit");
  await page.waitForSelector("#password-setup-form:not([hidden])", { timeout: 10000 });
  await page.fill("#new-password", standardFinalPassword);
  await page.fill("#confirm-password", standardFinalPassword);
  await page.click("#password-setup-submit");
  await page.waitForURL(appUrl(), { timeout: 10000 });
  await page.goto(appUrl("Users"), { waitUntil: "networkidle" });
  await page.waitForFunction(
    () => document.querySelector("#access-message")?.textContent.includes("Administrator access is required"),
    { timeout: 10000 },
  );
  await checkpoint("standard-user-blocked");

  await browser.close();
  console.log("M2 Stats Web Shell visible Edge evidence");
  console.log(`Admin test user: ${adminEmail}`);
  console.log(`Standard test user: ${standardEmail}`);
  console.log("Temporary and reset passwords are test-only values.");
  console.log("Result: PASSED");
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
// M2 End
