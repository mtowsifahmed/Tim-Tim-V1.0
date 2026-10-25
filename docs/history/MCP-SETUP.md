# Connecting Tim-Tim to Vercel / Railway / Render

Two different jobs, often confused:

1. **MCP servers** give the AI agent tools to create services, set env vars and trigger deploys in your account.
2. **Hosting this backend** is where the FastAPI app (WebSocket `/ws`, Supabase Postgres) actually runs.

The agent cannot sign in as you, so the one-time token/OAuth step is yours. After that it can deploy,
read logs and change env vars through the MCP tools.

## Which host actually fits

| Host | Free plan | WebSockets | Sleep | Verdict for Tim-Tim |
|---|---|---|---|---|
| **Render** | Yes, 750 h/month | Supported | Sleeps after 15 min idle, ~1 min wake | **Best fit.** Free Docker service, `/health` check. |
| **Railway** | $1 credit/month (+ $5 trial for 30 days) | Supported, no edge timeout | No sleep by default | Fine to try, but always-on 512 MB costs more than $1/month. |
| **Vercel** | Hobby, personal use only | Beta, connection closed at function timeout (**300 s** on Hobby) | Scales down when idle | **Not suitable**: the desktop app keeps one long socket open. |

Render needs a Git repo; Railway can deploy the local folder with its CLI. Docker is not installed on this
machine, so the image is built by the host, not locally.

## Render

### Deploy
1. Put the project in a GitHub repo (`.env` is already ignored):
   ```bash
   cd "T:/Applications/Tim-Tim By Claude/Tim-Tim by claude/Tim-Tim by claude"
   git init && git add . && git commit -m "Tim-Tim backend"
   git remote add origin https://github.com/<you>/tim-tim.git
   git push -u origin main
   ```
2. Render → **New → Blueprint** → choose the repo. `render.yaml` already defines the service:
   Docker build, free plan, health check `/health`, and the four required secrets.
3. Paste `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_DB_URL`, `KEY_ENCRYPTION_SECRET`, plus any provider keys.
4. The backend URL becomes `https://<service>.onrender.com`, and the app uses `wss://<service>.onrender.com/ws`
   (Settings → Developer → Backend URL).

### MCP
Token: Render Dashboard → **Account Settings → API Keys** (the key can do anything your account can).

```json
{
  "mcpServers": {
    "render": {
      "type": "http",
      "url": "https://mcp.render.com/mcp",
      "headers": { "Authorization": "Bearer <RENDER_API_KEY>" }
    }
  }
}
```

Non-JSON clients (Codex CLI example from Render's docs):
```bash
codex mcp add render --url https://mcp.render.com/mcp --bearer-token-env-var RENDER_API_KEY
```

## Railway

### Deploy
```bash
npm i -g @railway/cli
railway login
cd "T:/Applications/Tim-Tim By Claude/Tim-Tim by claude/Tim-Tim by claude"
railway init          # creates the project
railway variables --set SUPABASE_URL=... --set SUPABASE_ANON_KEY=... \
  --set SUPABASE_DB_URL=... --set KEY_ENCRYPTION_SECRET=...
railway up            # builds the Dockerfile and deploys the current folder
railway domain        # prints the public https:// domain
```
`railway.json` already sets the Dockerfile builder and the `/health` check.

### MCP
No token needed — the CLI reuses `railway login`.
```bash
railway mcp install        # registers the MCP server for installed clients
railway mcp                # or run it as a stdio server for a client that launches commands
```
Direct HTTP option for OAuth-capable clients: `https://mcp.railway.com`.

## Vercel

Not recommended for this backend. If you only want the MCP connection:
```bash
claude mcp add --transport http vercel https://mcp.vercel.com
```
or, in JSON:
```json
{ "mcpServers": { "vercel": { "type": "http", "url": "https://mcp.vercel.com" } } }
```
Authorise through the browser; there is no API key for the hosted server.

Reason to skip hosting here: Hobby functions cap a connection at 300 seconds and there is no always-on
container, while Tim-Tim keeps a WebSocket open for the whole session. Every 5 minutes the app would
reconnect, and `asyncpg` pooling on serverless can exhaust Supabase connections.

## After either host is live

- Set `BACKEND_WS_URL` (desktop `src/config.js`) or Settings → Developer → Backend URL to `wss://<host>/ws`.
- Phone pairing QR inherits the address the desktop uses.
- On free Render the first message after 15 quiet minutes takes ~1 minute (cold start); the desktop reconnects.
- Keep `backend/.env` out of git. Only `backend/.env.example` belongs in the repo.
