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

## Deploy

Configured for Vercel. The Vercel project root must be `marketing/`.

```bash
vercel link              # one-time
vercel                   # preview
vercel --prod            # production
```
