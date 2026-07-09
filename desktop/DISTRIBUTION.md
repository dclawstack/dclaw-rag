# Building & distributing the desktop app (E5.13)

The Electron shell packages into installers for **Linux, macOS, and Windows** via
electron-builder, with **auto-update** (electron-updater ← GitHub Releases) and a
shared **app icon** (`build/icon.png`, from which electron-builder derives
`.icns`/`.ico` at build time).

> ⚠️ **What is wired vs. what needs credentials/hardware.** The build config,
> entitlements, icon, and auto-update code are complete and committed. Producing
> **signed, notarized macOS and Windows installers cannot be done on a Linux dev
> box** — each OS's artifact (and its bundled `uv` + private Python runtime) must
> be built on that OS, and signing needs certificates. The steps below are what a
> maintainer with the certs + a CI matrix runs; the Linux AppImage/deb path is the
> only one exercised here.

## Per-OS builds

electron-builder cannot cross-compile these installers, because each bundles a
platform-specific `uv` and (on first run) a platform-specific Python runtime. Run
the matching command **on each OS** (or on the CI matrix in
`.github/workflows/desktop-build.yml`):

| OS      | Command            | Output                          |
|---------|--------------------|---------------------------------|
| Linux   | `npm run dist`     | `dist/*.AppImage`, `dist/*.deb` |
| macOS   | `npm run dist:mac` | `dist/*.dmg`, `dist/*.zip` (arm64 + x64) |
| Windows | `npm run dist:win` | `dist/*.exe` (NSIS)             |

Each first runs `build:ui` + `build:bundle` (the latter copies the **host** `uv`,
so it must run on the target OS — it names it `uv.exe` on Windows).

## Code signing & notarization

electron-builder reads signing material from env vars — nothing secret is committed.

**macOS** (Developer ID + notarization; `build/entitlements.mac.plist` is already
set for the hardened runtime — the app JITs and loads unsigned ML `.dylib`s):

```
export CSC_LINK=/path/to/DeveloperIDApplication.p12   # or base64 in CI
export CSC_KEY_PASSWORD=…
export APPLE_ID=…                # notarization (electron-builder ≥ notarytool)
export APPLE_APP_SPECIFIC_PASSWORD=…
export APPLE_TEAM_ID=…
npm run dist:mac
```

**Windows** (Authenticode):

```
export CSC_LINK=/path/to/codesign.pfx
export CSC_KEY_PASSWORD=…
npm run dist:win
```

Without these, builds still succeed but are **unsigned** — macOS Gatekeeper and
Windows SmartScreen will warn, and auto-update signature checks won't pass.

## Auto-update (electron-updater)

`update.js` checks GitHub Releases on packaged launch (see the `publish` block in
`package.json` → `dclawstack/dclaw-rag`) and installs on next quit. To ship an
update: bump `version` in `package.json`, build **signed** artifacts on each OS,
and publish them to a GitHub Release for that tag (electron-builder uploads with
`--publish always` when `GH_TOKEN` is set). Clients on the previous version pick it
up automatically. Unsigned/dev builds skip updating (guarded, best-effort).

## CI matrix

`.github/workflows/desktop-build.yml` is **manual-dispatch** (`workflow_dispatch`)
so it never runs unattended (each build downloads ~2 GB). Add the signing secrets
above as repo secrets to get signed artifacts; without them it produces unsigned
installers as workflow artifacts.

## Still open

Real signed/notarized macOS + Windows installers (needs certs + per-OS runners),
and an in-app "change LLM / settings" screen (today the LLM choice is edited in
`~/.dclaw-rag/desktop.env`).
