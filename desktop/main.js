/**
 * DClaw RAG desktop shell.
 *
 * Boots the whole app as one desktop window with zero external services:
 *   1. spawns the FastAPI backend in APP_MODE=local (SQLite + embedded Qdrant)
 *   2. forks the Next.js standalone server for the UI (same-origin as the dev
 *      frontend, so the backend's default CORS already allows it)
 *   3. shows the window once the backend reports healthy
 *
 * Dev mode runs against the repo (.venv python + frontend/.next/standalone);
 * packaged mode will point the same launcher at bundled resources.
 */

const { app, BrowserWindow, dialog, session, shell } = require("electron");
const { spawn } = require("node:child_process");
const http = require("node:http");
const path = require("node:path");
const fs = require("node:fs");

const BACKEND_PORT = 8090;
const UI_PORT = 3003;
const BACKEND_URL = `http://127.0.0.1:${BACKEND_PORT}`;
const UI_URL = `http://localhost:${UI_PORT}`;
const SELF_TEST = process.argv.includes("--self-test");

const repoRoot = path.resolve(__dirname, "..");
const children = [];
let backendLog = "";

function log(...args) {
  console.log("[shell]", ...args);
}

function pythonBin() {
  if (process.env.DCLAW_PYTHON) return process.env.DCLAW_PYTHON;
  const venv = path.join(repoRoot, ".venv", "bin", "python");
  return fs.existsSync(venv) ? venv : "python3";
}

function track(child, name) {
  children.push(child);
  child.stdout?.on("data", (d) => {
    if (name === "backend") backendLog = (backendLog + d).slice(-8000);
  });
  child.stderr?.on("data", (d) => {
    if (name === "backend") backendLog = (backendLog + d).slice(-8000);
  });
  child.on("exit", (code) => log(`${name} exited (${code})`));
  return child;
}

function startBackend() {
  return track(
    spawn(pythonBin(), ["-m", "uvicorn", "app.api.main:app", "--port", String(BACKEND_PORT)], {
      cwd: repoRoot,
      env: {
        ...process.env,
        APP_MODE: "local",
        BOOTSTRAP_API_KEY: "sk_local",
        // Desktop UX: don't inherit a stray server-mode .env pointing at Redis.
      },
      stdio: ["ignore", "pipe", "pipe"],
    }),
    "backend"
  );
}

function startUi() {
  const standalone = path.join(repoRoot, "frontend", ".next", "standalone", "server.js");
  if (!fs.existsSync(standalone)) {
    throw new Error(
      "UI build missing. Run `npm run build:ui` in desktop/ first (builds the frontend for the shell)."
    );
  }
  return track(
    spawn(process.execPath, [standalone], {
      cwd: path.dirname(standalone),
      env: {
        ...process.env,
        ELECTRON_RUN_AS_NODE: "1",
        PORT: String(UI_PORT),
        HOSTNAME: "127.0.0.1",
      },
      stdio: ["ignore", "pipe", "pipe"],
    }),
    "ui"
  );
}

function waitFor(url, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  return new Promise((resolve, reject) => {
    const attempt = () => {
      const req = http.get(url, (res) => {
        res.resume();
        if (res.statusCode && res.statusCode < 500) return resolve();
        retry();
      });
      req.on("error", retry);
      req.setTimeout(2000, () => {
        req.destroy();
        retry();
      });
    };
    const retry = () => {
      if (Date.now() > deadline)
        return reject(new Error(`Timed out waiting for ${url}\n\nBackend log tail:\n${backendLog}`));
      setTimeout(attempt, 500);
    };
    attempt();
  });
}

function stopChildren() {
  for (const child of children) {
    try {
      child.kill("SIGTERM");
    } catch {
      /* already gone */
    }
  }
}

async function selfTest(win) {
  await new Promise((r) => setTimeout(r, 3000)); // let the UI settle
  const image = await win.webContents.capturePage();
  const out = path.join(__dirname, "self-test.png");
  fs.writeFileSync(out, image.toPNG());
  const title = win.webContents.getTitle();
  log(`self-test: title="${title}" screenshot=${out}`);
  if (!title || image.isEmpty()) throw new Error("self-test: window is empty");
}

async function main() {
  const loading = new BrowserWindow({
    width: 420,
    height: 200,
    frame: false,
    resizable: false,
    show: !SELF_TEST,
  });
  loading.loadURL(
    "data:text/html," +
      encodeURIComponent(
        `<body style="font-family:sans-serif;background:#111;color:#eee;display:grid;place-items:center;height:95vh;margin:0">
           <div style="text-align:center"><h3>DClaw RAG</h3><p>Starting local engine…</p></div></body>`
      )
  );

  startBackend();
  startUi();
  await waitFor(`${BACKEND_URL}/health`, 120_000);
  await waitFor(UI_URL, 60_000);

  const win = new BrowserWindow({
    width: 1280,
    height: 840,
    show: !SELF_TEST,
    autoHideMenuBar: true,
  });

  // Voice queries need the microphone.
  session.defaultSession.setPermissionRequestHandler((_wc, permission, cb) => {
    cb(permission === "media");
  });

  // Keep navigation inside the app; external links go to the system browser.
  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });

  await win.loadURL(UI_URL);
  loading.destroy();

  if (SELF_TEST) {
    await selfTest(win);
    app.quit();
  }
}

if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.whenReady().then(() =>
    main().catch((err) => {
      console.error(err);
      if (!SELF_TEST) dialog.showErrorBox("DClaw RAG failed to start", String(err.message || err));
      app.exit(1);
    })
  );
}

app.on("before-quit", stopChildren);
app.on("window-all-closed", () => app.quit());
process.on("exit", stopChildren);
