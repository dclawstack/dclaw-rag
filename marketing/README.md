# DClaw RAG — Marketing Site

Standalone Next.js landing page for [DClaw RAG](https://github.com/dclawstack/dclaw-rag).
Independent from `frontend/` (the app UI) — no backend calls, no shared deps.

Includes a waitlist signup form backed by Neon Postgres (`waitlist` table,
created on first insert).

## Local

```bash
cd marketing
npm install
npm run dev     # http://localhost:3009
```

## Environment

`DATABASE_URL` — Neon Postgres connection string used by `POST /api/waitlist`.
Provisioned automatically by the Neon integration on Vercel. Without it, the
form returns a friendly 503.

`NEXT_PUBLIC_APP_URL` — public URL of the hosted app UI (see `../DEPLOY.md`
§ Render). When set, the nav and hero show "Launch app" links; when unset,
they fall back to the GitHub repo. Baked at build time — redeploy after
changing it.

## Deploy

Configured for Vercel. The Vercel project root must be `marketing/`.

```bash
vercel link              # one-time
vercel                   # preview
vercel --prod            # production
```
