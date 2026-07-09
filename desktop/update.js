/**
 * Auto-update (electron-updater).
 *
 * On a packaged launch we ask GitHub Releases (the `publish` block in
 * package.json) whether a newer signed build exists; if so it downloads in the
 * background and installs on the next quit. Best-effort — a network failure or
 * an unsigned/dev build must never block startup, so everything is guarded and
 * errors are swallowed with a log line.
 *
 * No-ops in dev (unpackaged) and during --self-test.
 */

function initAutoUpdate({ isPackaged, selfTest, log }) {
  if (!isPackaged || selfTest) return;

  let autoUpdater;
  try {
    ({ autoUpdater } = require("electron-updater"));
  } catch (err) {
    log(`auto-update unavailable: ${err.message}`);
    return;
  }

  autoUpdater.autoDownload = true;
  autoUpdater.autoInstallOnAppQuit = true;
  autoUpdater.on("error", (err) => log(`update error: ${err && err.message}`));
  autoUpdater.on("update-available", (info) => log(`update available: ${info.version}`));
  autoUpdater.on("update-not-available", () => log("no update available"));
  autoUpdater.on("update-downloaded", (info) =>
    log(`update downloaded: ${info.version} (installs on quit)`)
  );

  autoUpdater.checkForUpdates().catch((err) => log(`update check failed: ${err.message}`));
}

module.exports = { initAutoUpdate };
