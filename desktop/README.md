# DClaw RAG — desktop shell

One window, zero external services: an Electron shell that spawns the FastAPI
backend in `APP_MODE=local` (SQLite KV + embedded Qdrant + inline ingestion)
and serves the Next.js UI from its standalone build. Voice queries and audio
ingestion run on the local whisper model; answers need an LLM (OpenRouter key
or Ollama — see the repo `.env`).

**Why Electron (not Tauri):** the app payload is dominated by the Python
backend and its models (~2GB), so Tauri's small-binary advantage is noise;
Electron needs no Rust toolchain or webkit2gtk system packages; and Chromium's
`MediaRecorder`/`getUserMedia` (voice queries) are solid where WebKitGTK is not.
Recorded in the `dclaw-rag-desktop` tracker, task 1.

## Dev setup

```bash
# one-time: backend venv at repo root (see AGENTS.md), then:
cd desktop
npm install

# Ubuntu 24.04: AppArmor blocks Electron's unprivileged sandbox — give the
# helper its SUID bit (re-run after every npm install; installers do this
# themselves in packaged builds):
sudo chown root:root node_modules/electron/dist/chrome-sandbox
sudo chmod 4755 node_modules/electron/dist/chrome-sandbox

npm run build:ui   # builds the frontend with the shell's baked API URL + key
npm start
```

- Backend python resolves to the repo `.venv` (override with `DCLAW_PYTHON`).
- Data lives in `~/.dclaw-rag` (the backend's local-mode default).
- Ports are fixed: backend `8090`, UI `3003` (baked into the UI build).

## Self-test

```bash
npm run self-test
```

Boots everything against a throwaway data dir (never `~/.dclaw-rag`), then:
dashboard screenshot → ingest a fact → mic-record a spoken question (the mic is
stubbed with a committed audio fixture) → `/transcribe` fills the question box →
submit → assert a cited answer in the live DOM. Exit 0 = pass. Screenshots land
in `desktop/self-test-*.png`.

Needs a display, cached models, and an LLM (repo `.env` key or Ollama) — it's a
dev-machine tool, not a CI job.

Hard-won notes baked into `main.js` (don't undo silently):

- **Windows stay visible during self-test** — hidden windows get compositor/CPU
  throttled and the whole flow starves.
- **`HF_HUB_ETAG_TIMEOUT=5`** — anonymous Hugging Face hub checks can back off
  for minutes; cached models must not stall on them.
- **`getUserMedia` is stubbed in-page for the fake mic** — Chromium's
  `--use-file-for-fake-audio-capture` silently plays the beep tone instead of
  the file in Electron 43.
- **`capturePage` can return a stale frame when the window is occluded** — DOM
  assertions are authoritative; screenshots are best-effort evidence.
- **SIGTERM/SIGINT handlers kill the backend/UI children** — plain
  `process.on("exit")` does not run on signals.

## Not done yet (tracker: `dclaw-rag-desktop`)

- M2: packaged builds (PyInstaller vs bundled-venv spike, electron-builder
  AppImage/deb)
- M3: in-app LLM settings (OpenRouter key / Ollama) passed to the backend
- macOS/Windows targets, signing, auto-update
