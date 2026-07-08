/**
 * Backend resolution for the shell.
 *
 * Dev mode (repo checkout present): run uvicorn from the repo's .venv.
 *
 * Packaged mode (no repo): the app ships `resources/backend/` containing a
 * `uv` binary and the dclaw-rag wheel. On first launch we bootstrap a private
 * runtime under ~/.dclaw-rag/runtime — uv downloads a standalone CPython,
 * CPU-only torch, and installs the wheel — then every launch runs uvicorn
 * from that venv. First run needs the network (the ML models are downloaded
 * on first use anyway, so this adds no new requirement); later runs are
 * offline. A `.complete` marker stamped with the wheel name keeps upgrades
 * honest: a new wheel re-runs the bootstrap.
 */

const { spawn, spawnSync } = require("node:child_process");
const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const PYTHON_VERSION = "3.11";
const TORCH_INDEX = "https://download.pytorch.org/whl/cpu";

function repoRootOrNull() {
  const root = path.resolve(__dirname, "..");
  return fs.existsSync(path.join(root, "app", "api", "main.py")) ? root : null;
}

function runtimeDir() {
  return path.join(os.homedir(), ".dclaw-rag", "runtime");
}

function bundledBackendDir(resourcesPath) {
  return path.join(resourcesPath, "backend");
}

function findWheel(backendDir) {
  const wheel = fs.readdirSync(backendDir).find((f) => f.endsWith(".whl"));
  if (!wheel) throw new Error(`No backend wheel in ${backendDir}`);
  return path.join(backendDir, wheel);
}

// Hash, not filename: rebuilds of the same version must re-bootstrap.
function wheelDigest(resourcesPath) {
  const wheel = findWheel(bundledBackendDir(resourcesPath));
  return crypto.createHash("sha256").update(fs.readFileSync(wheel)).digest("hex");
}

/** True when the packaged runtime (venv + extracted UI) matches the shipped wheel. */
function runtimeReady(resourcesPath) {
  const marker = path.join(runtimeDir(), ".complete");
  if (!fs.existsSync(marker)) return false;
  if (!fs.existsSync(path.join(runtimeDir(), "ui", "server.js"))) return false;
  return fs.readFileSync(marker, "utf8").trim() === wheelDigest(resourcesPath);
}

/** Packaged UI location (extracted from ui.tar at bootstrap). */
function packagedUiServer() {
  return path.join(runtimeDir(), "ui", "server.js");
}

/**
 * Create the runtime venv and install the backend into it.
 * onProgress(line) receives installer output for the splash screen.
 */
async function bootstrapRuntime(resourcesPath, onProgress) {
  const backendDir = bundledBackendDir(resourcesPath);
  const uv = path.join(backendDir, "uv");
  const wheel = findWheel(backendDir);
  const venv = path.join(runtimeDir(), "venv");
  fs.mkdirSync(runtimeDir(), { recursive: true });

  const env = { ...process.env, UV_PYTHON_INSTALL_DIR: path.join(runtimeDir(), "python") };
  const python = path.join(venv, "bin", "python");
  const steps = [
    [uv, ["venv", venv, "--python", PYTHON_VERSION, "--allow-existing"], env],
    // CPU torch first (mirrors CI/Dockerfile) so the app install resolves
    // against it instead of pulling ~5GB of CUDA wheels.
    [uv, ["pip", "install", "--python", python, "torch", "torchvision", "--index-url", TORCH_INDEX], env],
    // --reinstall-package: a rebuilt wheel keeps its version; same-version
    // installs would otherwise be treated as already satisfied.
    [uv, ["pip", "install", "--python", python, "--reinstall-package", "dclaw-rag", wheel], env],
  ];

  // The UI ships as a tarball: electron-builder's extraResources copy strips
  // node_modules and dot-dirs (.next), so a plain directory arrives gutted.
  const uiTar = path.join(resourcesPath, "ui.tar");
  const uiDir = path.join(runtimeDir(), "ui");
  fs.rmSync(uiDir, { recursive: true, force: true });
  fs.mkdirSync(uiDir, { recursive: true });
  steps.push(["tar", ["-xf", uiTar, "-C", uiDir], process.env]);

  for (const [cmd, args, stepEnv] of steps) {
    await new Promise((resolve, reject) => {
      const child = spawn(cmd, args, { env: stepEnv, stdio: ["ignore", "pipe", "pipe"] });
      const feed = (d) => {
        const line = d.toString().split("\n").filter(Boolean).pop();
        if (line) onProgress(line.slice(0, 120));
      };
      child.stdout.on("data", feed);
      child.stderr.on("data", feed);
      child.on("exit", (code) =>
        code === 0 ? resolve() : reject(new Error(`${path.basename(cmd)} ${args[0]} failed (${code})`))
      );
      child.on("error", reject);
    });
  }

  fs.writeFileSync(path.join(runtimeDir(), ".complete"), wheelDigest(resourcesPath));
}

/** {python, cwd} to launch uvicorn with, for dev or packaged mode. */
function backendLaunch(resourcesPath) {
  if (process.env.DCLAW_PYTHON) {
    return { python: process.env.DCLAW_PYTHON, cwd: repoRootOrNull() || os.homedir() };
  }
  const repo = repoRootOrNull();
  if (repo) {
    const venv = path.join(repo, ".venv", "bin", "python");
    return { python: fs.existsSync(venv) ? venv : "python3", cwd: repo };
  }
  return { python: path.join(runtimeDir(), "venv", "bin", "python"), cwd: os.homedir() };
}

/** Best-effort sanity check that a python can import the app. */
function pythonHasApp(python) {
  try {
    return spawnSync(python, ["-c", "import app.api.main"], { timeout: 30_000 }).status === 0;
  } catch {
    return false;
  }
}

module.exports = {
  repoRootOrNull,
  runtimeReady,
  bootstrapRuntime,
  backendLaunch,
  packagedUiServer,
  pythonHasApp,
};
