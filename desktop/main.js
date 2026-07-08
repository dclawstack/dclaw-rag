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

// Self-test feeds the "mic" by stubbing getUserMedia with a Web Audio stream
// decoded from the committed voice fixture (see selfTest) — Chromium's
// fake-capture-from-file flags are unreliable across versions.

const backend = require("./backend");
const settings = require("./settings");

const repoRoot = backend.repoRootOrNull() || path.resolve(__dirname, "..");
const children = [];
let backendLog = "";

function log(...args) {
  console.log("[shell]", ...args);
}

function track(child, name) {
  children.push(child);
  const capture = (d) => {
    if (name === "backend") backendLog = (backendLog + d).slice(-8000);
    else log(`${name}: ${String(d).trim().slice(0, 300)}`);
  };
  child.stdout?.on("data", capture);
  child.stderr?.on("data", capture);
  child.on("exit", (code) => log(`${name} exited (${code})`));
  return child;
}

function startBackend() {
  const { python, cwd } = backend.backendLaunch(process.resourcesPath);
  return track(
    spawn(python, ["-m", "uvicorn", "app.api.main:app", "--port", String(BACKEND_PORT)], {
      cwd,
      env: {
        ...process.env,
        // Stored LLM choice — packaged mode only (dev uses the repo .env);
        // explicitly exported env vars always win.
        ...(backend.repoRootOrNull() ? {} : settings.desktopEnvDefaults(process.env)),
        APP_MODE: "local",
        BOOTSTRAP_API_KEY: "sk_local",
        PYTHONUNBUFFERED: "1", // piped stdout is block-buffered; logs must stream
        // Cached models must not stall on Hugging Face hub checks (anonymous
        // rate limits back off for minutes): fail the check fast and fall
        // back to the local cache; downloads still work when a model is new.
        HF_HUB_ETAG_TIMEOUT: "5",
        // Self-tests must never touch the user's real ~/.dclaw-rag data, and
        // run fully offline (models are cached by the dev/CI environment).
        ...(SELF_TEST
          ? {
              DATA_DIR: fs.mkdtempSync(
                path.join(require("node:os").tmpdir(), "dclaw-selftest-")
              ),
              HF_HUB_OFFLINE: "1",
            }
          : {}),
      },
      stdio: ["ignore", "pipe", "pipe"],
    }),
    "backend"
  );
}

function startUi() {
  const packagedUi = backend.packagedUiServer();
  const standalone =
    !backend.repoRootOrNull() && fs.existsSync(packagedUi)
      ? packagedUi
      : path.join(repoRoot, "frontend", ".next", "standalone", "server.js");
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

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function backendRequest(method, apiPath, body) {
  return new Promise((resolve, reject) => {
    const data = body ? JSON.stringify(body) : null;
    const req = http.request(
      `${BACKEND_URL}${apiPath}`,
      {
        method,
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": "sk_local",
          ...(data ? { "Content-Length": Buffer.byteLength(data) } : {}),
        },
      },
      (res) => {
        let raw = "";
        res.on("data", (d) => (raw += d));
        res.on("end", () => resolve({ status: res.statusCode, json: JSON.parse(raw || "{}") }));
      }
    );
    req.setTimeout(30_000, () => {
      req.destroy(new Error(`backend request timed out: ${method} ${apiPath}`));
    });
    req.on("error", reject);
    if (data) req.write(data);
    req.end();
  });
}

// Packaged app code lives in a read-only asar — write artifacts to tmp there.
const artifactsDir = backend.repoRootOrNull()
  ? __dirname
  : fs.mkdtempSync(path.join(require("node:os").tmpdir(), "dclaw-selftest-artifacts-"));

async function shot(win, name) {
  const image = await win.webContents.capturePage();
  const out = path.join(artifactsDir, `self-test-${name}.png`);
  fs.writeFileSync(out, image.toPNG());
  log(`screenshot: ${out}`);
  return image;
}

async function waitInPage(win, expr, timeoutMs, what) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const result = await win.webContents.executeJavaScript(expr, true);
    if (result) {
      log(`wait satisfied (${what}): ${JSON.stringify(result).slice(0, 300)}`);
      return result;
    }
    await sleep(500);
  }
  throw new Error(`self-test: timed out waiting for ${what}`);
}

async function selfTest(win) {
  win.webContents.on("console-message", (_e, _lvl, msg) => log(`renderer: ${msg}`));
  await sleep(3000); // let the dashboard settle
  const image = await shot(win, "dashboard");
  if (!win.webContents.getTitle() || image.isEmpty())
    throw new Error("self-test: window is empty");

  // Ingest a fact through the shell's backend, wait until it's queryable.
  const fact =
    "The Zephyr-7 wind turbine uses a magnetic bearing system, which eliminates " +
    "oil lubrication entirely. Its rotor diameter is 164 meters.";
  const ingest = await backendRequest("POST", "/api/v1/rag/documents/text", {
    text: fact,
    metadata: { source: "self-test", title: "Zephyr-7 spec" },
  });
  if (ingest.status !== 200) throw new Error(`self-test: ingest failed (${ingest.status})`);
  for (let i = 0; ; i++) {
    const doc = await backendRequest("GET", `/api/v1/rag/documents/${ingest.json.doc_id}`);
    if (doc.json.status === "ready") break;
    if (doc.json.status === "failed" || i > 240)
      throw new Error(`self-test: ingestion did not become ready (${doc.json.status})`);
    await sleep(1000);
  }

  // Voice query: the fake mic plays the fixture; click record, stop, and let
  // /transcribe fill the question box.
  await win.loadURL(`${UI_URL}/query`);
  await sleep(2000);
  // Make the mic "speak" the committed fixture: getUserMedia returns a stream
  // playing the decoded clip, so record -> /transcribe -> question box runs
  // exactly as it would for a real user.
  const fixture = backend.repoRootOrNull()
    ? path.join(repoRoot, "tests", "fixtures", "voice_query.mp3")
    : path.join(process.resourcesPath, "backend", "voice_query.mp3");
  const clipB64 = fs.readFileSync(fixture).toString("base64");
  await win.webContents.executeJavaScript(
    `(async () => {
      const bytes = Uint8Array.from(atob("${clipB64}"), (c) => c.charCodeAt(0));
      const ctx = new AudioContext();
      const buffer = await ctx.decodeAudioData(bytes.buffer);
      navigator.mediaDevices.getUserMedia = async () => {
        const source = ctx.createBufferSource();
        source.buffer = buffer;
        const dest = ctx.createMediaStreamDestination();
        source.connect(dest);
        source.start();
        return dest.stream;
      };
      return buffer.duration;
    })()`,
    true
  ).then((d) => log(`fixture decoded: ${d.toFixed(1)}s`));
  // Surface the transcribe response + recorded blob size in the shell log.
  await win.webContents.executeJavaScript(
    `(() => {
      const origFetch = window.fetch;
      window.fetch = async (...args) => {
        const res = await origFetch(...args);
        if (String(args[0]).includes("/transcribe")) {
          const body = args[1] && args[1].body;
          const blob = body && body.get && body.get("file");
          const parsed = await res.clone().json().catch(() => ({}));
          window.__lastClip = blob;
          console.log("TRANSCRIBE size=" + (blob ? blob.size : "?") + " result=" + JSON.stringify(parsed));
        }
        return res;
      };
    })()`,
    true
  );
  const micBtn = `document.querySelector('button[aria-label="Ask by voice"], button[aria-label="Stop recording"]')`;
  await win.webContents.executeJavaScript(`${micBtn}.click()`, true);
  await sleep(7000); // fixture is ~5s
  await win.webContents.executeJavaScript(`${micBtn}.click()`, true);
  try {
    await waitInPage(
      win,
      `document.getElementById("question").value.toLowerCase().includes("turbine")`,
      120_000,
      "voice transcript in the question box"
    );
  } catch (err) {
    await shot(win, "voice-failure");
    const value = await win.webContents.executeJavaScript(
      `document.getElementById("question").value`,
      true
    );
    log(`question box at failure: "${value}"`);
    const b64 = await win.webContents.executeJavaScript(
      `window.__lastClip ? new Promise(r => { const fr = new FileReader();
         fr.onload = () => r(fr.result.split(",")[1]); fr.readAsDataURL(window.__lastClip); })
       : null`,
      true
    );
    if (b64) {
      const clipPath = path.join(artifactsDir, "self-test-clip.webm");
      fs.writeFileSync(clipPath, Buffer.from(b64, "base64"));
      log(`recorded clip saved: ${clipPath}`);
    }
    log(`backend log tail:\n${backendLog.slice(-2000)}`);
    throw err;
  }
  const transcript = await win.webContents.executeJavaScript(
    `document.getElementById("question").value`,
    true
  );
  log(`voice transcript: "${transcript}"`);

  // Submit the transcribed question and wait for a cited answer.
  await win.webContents.executeJavaScript(
    `document.getElementById("question").closest("form").requestSubmit()`,
    true
  );
  try {
    await waitInPage(
      win,
      `(() => {
        const m = (document.body.innerText.match(/[^\\n]*magnetic[^\\n]*/i) || [""])[0];
        if (!m) return "";
        const mic = document.querySelector('button[aria-label="Ask by voice"], button[aria-label="Stop recording"]');
        return JSON.stringify({
          match: m,
          question: (document.getElementById("question") || {}).value,
          micLabel: mic && mic.getAttribute("aria-label"),
          citations: (document.body.innerText.match(/Citations \\(\\d+\\)/) || [null])[0],
        });
      })()`,
      180_000,
      "answer mentioning the ingested fact"
    );
  } catch (err) {
    await shot(win, "answer-failure");
    const text = await win.webContents.executeJavaScript(
      `document.body.innerText.slice(0, 1500)`,
      true
    );
    log(`page text at failure:\n${text}`);
    log(`backend log tail:\n${backendLog.slice(-1500)}`);
    throw err;
  }
  // Screenshot is best-effort evidence: an occluded window can yield a stale
  // compositor frame — the wait's DOM snapshot above is the authoritative check.
  win.focus();
  await sleep(500);
  await shot(win, "voice-answer");
  log("self-test: voice query round-trip OK");
}

async function main() {
  const loading = new BrowserWindow({
    width: 420,
    height: 200,
    frame: false,
    resizable: false,
    show: true, // hidden self-test windows get compositor/CPU-throttled and starve the flow
  });
  loading.loadURL(
    "data:text/html," +
      encodeURIComponent(
        `<body style="font-family:sans-serif;background:#111;color:#eee;display:grid;place-items:center;height:95vh;margin:0">
           <div style="text-align:center"><h3>DClaw RAG</h3><p id="msg">Starting local engine…</p>
           <p id="detail" style="font-size:11px;color:#888;max-width:380px;overflow:hidden;white-space:nowrap"></p></div></body>`
      )
  );
  const splash = (msg, detail = "") =>
    loading.webContents
      .executeJavaScript(
        `document.getElementById("msg").textContent = ${JSON.stringify(msg)};
         document.getElementById("detail").textContent = ${JSON.stringify(detail)};`
      )
      .catch(() => {});

  // Packaged first run with no LLM configured anywhere: ask once.
  if (
    !SELF_TEST &&
    !backend.repoRootOrNull() &&
    !settings.readDesktopEnv() &&
    !process.env.OPENROUTER_API_KEY &&
    !process.env.LLM_PROVIDER
  ) {
    await settings.firstRunSettings();
  }

  // Packaged first run: install the private Python runtime (one-off, ~2GB —
  // the same first-run network the ML models need anyway).
  if (!backend.repoRootOrNull() && !process.env.DCLAW_PYTHON) {
    if (!backend.runtimeReady(process.resourcesPath)) {
      log("bootstrapping backend runtime (first run)");
      await splash("First run: setting up the local engine…", "downloading Python + dependencies");
      await backend.bootstrapRuntime(process.resourcesPath, (line) =>
        splash("First run: setting up the local engine…", line)
      );
      log("runtime bootstrap complete");
    }
  }

  await splash("Starting local engine…");
  startBackend();
  startUi();
  await waitFor(`${BACKEND_URL}/health`, 120_000);
  await waitFor(UI_URL, 60_000);

  const win = new BrowserWindow({
    width: 1280,
    height: 840,
    show: true, // hidden self-test windows get compositor/CPU-throttled and starve the flow
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
      if (SELF_TEST) console.error(`backend log tail:\n${backendLog.slice(-3000)}`);
      else dialog.showErrorBox("DClaw RAG failed to start", String(err.message || err));
      app.exit(1);
    })
  );
}

app.on("before-quit", stopChildren);
app.on("window-all-closed", () => app.quit());
process.on("exit", stopChildren);
// Signals bypass "exit" handlers — without these, killing the shell would
// leak the backend/UI child processes.
for (const sig of ["SIGTERM", "SIGINT"]) {
  process.on(sig, () => {
    stopChildren();
    app.exit(0);
  });
}
