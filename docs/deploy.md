# Deploying MediBot on free tiers

Two-part deploy:

- **Backend** → **Hugging Face Spaces** (Docker SDK). Free, no card, AI-discoverable.
- **Frontend** → **Vercel** (or **Cloudflare Pages** — same steps, different host).

Total cost: **$0**. Total time: **~25 minutes** the first time.

---

## Part 1 — Backend on Hugging Face Spaces

### 1.1 Create the Space

1. Sign in at <https://huggingface.co> (free account is fine).
2. **New Space** → name it (e.g. `medibot`) → choose:
   - **SDK:** Docker
   - **Hardware:** *CPU basic — free*
   - **Visibility:** Public (recruiters won't see Private)
3. After creation, copy the Space's git URL: `https://huggingface.co/spaces/<you>/medibot`.

### 1.2 Add secrets

In the Space → **Settings** → **Variables and secrets**, add:

| Key | Type | Source |
|---|---|---|
| `PINECONE_API_KEY` | secret | your Pinecone console |
| `GROQ_API_KEY` | secret | <https://console.groq.com> |
| `HF_TOKEN` | secret | <https://huggingface.co/settings/tokens> (Read scope) |
| `SECRET_KEY` | secret | `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `GOOGLE_CLIENT_ID` | secret | (only if you want Google OAuth) |
| `GOOGLE_CLIENT_SECRET` | secret | (same) |
| `BACKEND_CORS_ORIGINS` | variable | `https://<your-vercel-url>.vercel.app,http://localhost:5173` |
| `JINA_API_KEY` | secret | optional — auto-enables the reranker if set |
| `LANGFUSE_ENABLED` | variable | `true` if you want traces |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | secret | optional |
| `AGENT_ENABLED` | variable | `true` to enable the LangGraph agent endpoint |

HF injects these as env vars at container runtime — no code change needed.

### 1.3 Prepare the Space remote

The Space's `README.md` must start with HF-specific YAML frontmatter. **Don't commit this frontmatter to your GitHub `main`** — keep it Space-local.

```bash
# From the repo root:
git remote add space https://huggingface.co/spaces/<you>/medibot

# Sync a branch dedicated to the Space:
git checkout -b deploy/hf-space
```

Then prepend this block to the top of `README.md` on the `deploy/hf-space` branch only:

```yaml
---
title: MediBot
emoji: 🩺
colorFrom: purple
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: Agentic medical RAG with hybrid retrieval and runtime safety
---
```

Commit + push to the Space:

```bash
git add README.md
git commit -m "deploy: HF Space metadata"
git push space deploy/hf-space:main
```

HF starts building the Docker image immediately. First build takes ~5–8 min (torch + sentence-transformers are the bulk). Subsequent builds are cached.

### 1.4 Verify

Once the Space shows "Running":

```bash
curl https://<you>-medibot.hf.space/api/v1/health
# {"status": "healthy", ...}
```

That URL is now your backend. Note it down — Vercel needs it.

---

## Part 2 — Frontend on Vercel

### 2.1 Import

1. <https://vercel.com> → **Add New Project** → import your GitHub repo.
2. Vercel will detect Vite. **Root Directory:** `frontend`. Framework preset stays `Vite`.
3. **Environment Variables** (Production + Preview):
   - `VITE_API_URL` = `https://<you>-medibot.hf.space`

### 2.2 Deploy

Click **Deploy**. Build takes ~30s. Vercel hands you a `*.vercel.app` URL.

### 2.3 Close the CORS loop

Back in HF Space → Settings → update `BACKEND_CORS_ORIGINS` to include the exact Vercel URL:

```
https://medibot-frontend.vercel.app,http://localhost:5173
```

Restart the Space (Settings → **Factory rebuild** isn't needed — a normal restart is fine).

### 2.4 Test

Open the Vercel URL. Stream a chat message. Confirm:

- Response streams (token-by-token via WebSocket on `wss://...hf.space/api/v1/chat/ws`)
- Sources show up if you upload a document
- Browser DevTools → Network shows no CORS errors

---

## Alternative: Cloudflare Pages (instead of Vercel)

Identical steps, but the build config goes in `wrangler.toml` or the dashboard:

- Build command: `cd frontend && npm ci && npm run build`
- Build output directory: `frontend/dist`
- Environment variable: `VITE_API_URL` = your HF Space URL
- SPA routing: Cloudflare Pages auto-detects `index.html` fallback — no extra config

Cloudflare's free tier has **unlimited bandwidth**, so it's a strict upgrade over Vercel for high-traffic demos.

---

## Cold-start behavior

Hugging Face Spaces on CPU Basic:

- Wakes on first request after ~48h of zero traffic. Cold start: **~10s** (vs Render's 30–60s).
- Stays warm as long as there's traffic. Ping `/api/v1/health` every 5 min from a cron if you want guaranteed always-on (free option: <https://cron-job.org>).

**Demo trick:** before a recruiter visits, hit `/api/v1/health` once. By the time they click the chat, the Space is warm.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| HF build fails on `pip install` | torch wheel exceeded build memory | Add `--no-deps` for torch in requirements.txt, or split into separate `RUN` layers |
| `502 Bad Gateway` on first request | container started but app not bound to `$PORT` | Confirm `app_port: 7860` in README frontmatter matches `EXPOSE 7860` in Dockerfile |
| Browser console: "blocked by CORS policy" | `BACKEND_CORS_ORIGINS` doesn't include Vercel URL | Add it (no trailing slash) and restart the Space |
| WebSocket fails with `wss` error | mixed-content: HTTPS frontend hitting HTTP backend | Set `VITE_API_URL` to `https://` (not `http://`) |
| Streaming works locally, batched on HF | nginx-in-front buffering | The `X-Accel-Buffering: no` header in `chat.py` handles this for Render-style proxies; HF uses Caddy which respects this header out of the box |
| Pinecone "index not found" | `PINECONE_INDEX_NAME` env not set | Default is `medicbot`; set explicitly in HF if your index name differs |

---

## Why this stack

- **HF Spaces is where AI recruiters look.** A Space page with a public chat widget signals "this engineer ships ML" more than any deploy on a generic PaaS.
- **No credit card anywhere.** Render free expires under load. Fly.io ended free tier in 2024. HF + Vercel are the only genuinely-zero-dollar combo that doesn't degrade.
- **Same Docker image as production.** The `Dockerfile` you push to HF is the same one CI builds and pushes to GHCR. No platform-specific drift.
