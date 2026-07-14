# Testing Plaid OAuth banks locally (Chase, BofA, …)

OAuth institutions require an **HTTPS** redirect URI registered in the Plaid
Dashboard — `http://localhost` will not work. To exercise the full OAuth Link flow
on your machine, front the dev servers with an HTTPS tunnel.

## Why the extra config exists
`next.config.ts` adds two opt-in hooks (both inactive by default):

- **`allowedDevOrigins`** (env `DEV_TUNNEL_HOSTS`) — Next dev otherwise rejects a
  tunnel origin as `Unauthorized`, so the page HTML loads but the client never
  hydrates (the "Connect" button does nothing). Whitelisting the tunnel host fixes it.
- **`/_api/*` rewrite** — an HTTPS page can't call `http://localhost:8000` (mixed
  content). Setting `NEXT_PUBLIC_API_URL=/_api` routes API calls same-origin; Next
  proxies them to the backend server-side (`API_PROXY_TARGET`, default
  `http://localhost:8000`).

## Steps
1. **Start a tunnel to the web app.** Cloudflare is reliable and has no interstitial:
   ```bash
   cloudflared tunnel --url http://localhost:3000    # → https://<name>.trycloudflare.com
   # (ngrok http 3000 also works)
   ```
2. **Register the redirect URI** in the Plaid Dashboard
   (Developers → API → Allowed redirect URIs), exactly:
   ```
   https://<name>.trycloudflare.com/settings
   ```
3. **Point the backend at it** — set `FT_PLAID_REDIRECT_URI` to the same value and
   start the API (`uvicorn app.main:app --port 8000 --reload`).
4. **Start the web app** whitelisting the tunnel host and routing the API through the
   proxy:
   ```bash
   DEV_TUNNEL_HOSTS=<name>.trycloudflare.com \
   NEXT_PUBLIC_API_URL=/_api \
     npm run dev
   ```
5. Open the app **via the tunnel URL** (not localhost) and use Connect Bank Account.

## Notes
- The redirect URI must match **exactly** between `FT_PLAID_REDIRECT_URI` and the
  Dashboard registration, or `/link/token/create` returns a redirect-uri error.
- OAuth banks additionally require your Plaid account to be **authorized for that
  institution in Production** (full production access + institution OAuth
  registration). Sandbox needs none of this and is the fastest way to prove the flow.
- The tunnel exposes the app publicly for its lifetime — tear it down when done.
