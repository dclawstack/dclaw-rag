/**
 * LLM settings for the packaged app.
 *
 * Answers need an LLM the backend can reach: the user's OpenRouter key
 * (bring-your-own-key) or a local Ollama. Choices persist as KEY=VALUE lines
 * in ~/.dclaw-rag/desktop.env, merged into the backend's env on every launch
 * (explicitly exported env vars still win). First packaged launch with no
 * config shows a small form; editing the file later works too.
 */

const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const ENV_FILE = path.join(os.homedir(), ".dclaw-rag", "desktop.env");

function readDesktopEnv() {
  if (!fs.existsSync(ENV_FILE)) return null;
  const env = {};
  for (const line of fs.readFileSync(ENV_FILE, "utf8").split("\n")) {
    const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/);
    if (m) env[m[1]] = m[2];
  }
  return env;
}

/** desktop.env as backend-env defaults (explicit env vars win). */
function desktopEnvDefaults(processEnv) {
  const stored = readDesktopEnv() || {};
  const defaults = {};
  for (const [key, value] of Object.entries(stored)) {
    if (!(key in processEnv)) defaults[key] = value;
  }
  return defaults;
}

const FORM_HTML = `<body style="font-family:sans-serif;background:#111;color:#eee;margin:0;padding:24px">
  <h3 style="margin-top:0">DClaw RAG — choose your answer engine</h3>
  <p style="font-size:13px;color:#aaa">Documents, search, and voice stay fully local.
  Generating the final written answer needs a language model:</p>
  <form id="f">
    <label style="display:block;margin:10px 0">
      <input type="radio" name="provider" value="local" checked>
      <b>Fully local</b> (bundled model — <span style="color:#aaa">no key, nothing leaves your machine</span>)
    </label>
    <p style="font-size:12px;color:#888;margin:2px 0 12px 22px">Downloads a ~2&nbsp;GB model once on first use, then runs offline.</p>
    <label style="display:block;margin:10px 0">
      <input type="radio" name="provider" value="openrouter">
      <b>OpenRouter</b> (bring your own key — <span style="color:#aaa">openrouter.ai/keys</span>)
    </label>
    <input id="key" placeholder="sk-or-..." style="width:100%;padding:6px;background:#222;color:#eee;border:1px solid #444">
    <label style="display:block;margin:14px 0 4px">
      <input type="radio" name="provider" value="ollama">
      <b>Ollama</b> (local — needs a separate Ollama running)
    </label>
    <input id="model" placeholder="model, e.g. llama3.2:3b" style="width:100%;padding:6px;background:#222;color:#eee;border:1px solid #444">
    <div style="margin-top:18px;display:flex;gap:8px">
      <button type="submit" style="padding:8px 16px">Save</button>
      <button type="button" id="skip" style="padding:8px 16px;background:#333;color:#ccc">Skip for now</button>
    </div>
  </form>
  <script>
    const go = (params) => { window.location.href = "dclaw-settings://save?" + params.toString(); };
    document.getElementById("f").onsubmit = (e) => {
      e.preventDefault();
      const provider = document.querySelector('input[name=provider]:checked').value;
      const params = new URLSearchParams({ provider });
      params.set("key", document.getElementById("key").value.trim());
      params.set("model", document.getElementById("model").value.trim());
      go(params);
    };
    document.getElementById("skip").onclick = () => go(new URLSearchParams({ provider: "skip" }));
  </script>
</body>`;

function buildEnvFile(params) {
  const provider = params.get("provider");
  if (provider === "local") {
    // Bundled in-process llama.cpp GGUF — no key, no external service. The
    // model downloads on first query (see LOCAL_LLM_* in .env.example).
    return "LLM_PROVIDER=local\n";
  }
  if (provider === "openrouter" && params.get("key")) {
    return `LLM_PROVIDER=openrouter\nOPENROUTER_API_KEY=${params.get("key")}\n`;
  }
  if (provider === "ollama") {
    const model = params.get("model") || "llama3.2:3b";
    return `LLM_PROVIDER=ollama\nOLLAMA_MODEL=${model}\n`;
  }
  return "# no LLM configured yet — see desktop/README.md\n";
}

/** Show the first-run form; resolves once a choice is stored (or skipped). */
function firstRunSettings() {
  const { BrowserWindow } = require("electron");
  return new Promise((resolve) => {
    const win = new BrowserWindow({ width: 520, height: 420, resizable: false });
    win.setMenuBarVisibility(false);
    win.webContents.on("will-navigate", (event, url) => {
      if (!url.startsWith("dclaw-settings://")) return;
      event.preventDefault();
      const params = new URL(url).searchParams;
      fs.mkdirSync(path.dirname(ENV_FILE), { recursive: true });
      fs.writeFileSync(ENV_FILE, buildEnvFile(params));
      win.destroy();
      resolve();
    });
    win.on("closed", resolve); // closing the window counts as skip
    win.loadURL("data:text/html," + encodeURIComponent(FORM_HTML));
  });
}

module.exports = { ENV_FILE, readDesktopEnv, desktopEnvDefaults, firstRunSettings };
