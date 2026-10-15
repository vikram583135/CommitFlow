# Cloudflare Production Deployment Guide for CommitFlow

This guide provides instructions to deploy CommitFlow onto Cloudflare infrastructure:
1. **Frontend:** Deployed to **Cloudflare Pages** (Global Edge CDN, automatic TLS, zero cold-starts).
2. **Backend & Workers:** Connected via **Cloudflare Tunnel (`cloudflared`)** (Zero exposed firewall ports, DDoS shielded, authenticated origin).

---

## Architecture Overview

```
                      ┌────────────────────────────────────────┐
                      │        Cloudflare Global Network       │
                      └───────────────────┬────────────────────┘
                                          │
                  ┌───────────────────────┴───────────────────────┐
                  ▼                                               ▼
       Cloudflare Pages                                 Cloudflare Tunnel
    (commitflow.dev / Next.js)                      (api.commitflow.dev / cloudflared)
                  │                                               │
                  │ HTTPS REST & SSE Streams                      │ Encrypted Tunnel
                  └───────────────────────┬───────────────────────┘
                                          ▼
                               ┌─────────────────────┐
                               │  Your Server / VPC  │
                               │  (Docker Compose)   │
                               │  - Django API       │
                               │  - Celery Workers   │
                               │  - Redis & Postgres │
                               └─────────────────────┘
```

---

## 1. Frontend: Deploy to Cloudflare Pages

### Step A: Connect Repository
1. Log in to the [Cloudflare Dashboard](https://dash.cloudflare.com/).
2. Navigate to **Workers & Pages** → **Create application** → **Pages** → **Connect to Git**.
3. Select the `CommitFlow` repository (`main` branch).

### Step B: Build Settings
- **Framework preset:** Next.js (Static / Standalone)
- **Build command:** `cd frontend && npm install && npm run build`
- **Build output directory:** `frontend/.next` (or `out` if static export)
- **Root directory:** `/`

### Step C: Environment Variables in Cloudflare Pages
Add the following in the Pages project settings:
```ini
NEXT_PUBLIC_API_URL=https://api.commitflow.dev
NODE_VERSION=20.10.0
```

---

## 2. Backend: Deploy via Cloudflare Tunnel (`cloudflared`)

Cloudflare Tunnel exposes the Django REST API directly to `api.commitflow.dev` securely through an outbound-only connection. **No inbound ports (e.g. port 80/443) need to be opened on your firewall.**

### Step A: Install Cloudflare Tunnel Client
```bash
# On Debian / Ubuntu:
curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared.deb
```

### Step B: Authenticate and Create Tunnel
```bash
# 1. Login to Cloudflare account:
cloudflared tunnel login

# 2. Create the tunnel:
cloudflared tunnel create commitflow-prod-tunnel

# Note the Tunnel ID printed (e.g. 11111111-2222-3333-4444-555555555555)
```

### Step C: Route DNS Hostnames
```bash
cloudflared tunnel route dns commitflow-prod-tunnel api.commitflow.dev
cloudflared tunnel route dns commitflow-prod-tunnel health.commitflow.dev
```

### Step D: Run the Tunnel via Docker Compose
Mount the `cloudflare/config.yml` configuration and start the stack:
```bash
docker compose -f docker/docker-compose.yml up -d
cloudflared tunnel --config ./cloudflare/config.yml run commitflow-prod-tunnel
```

---

## 3. Production Environment Checklist

Before activating scheduled habit automation tasks:

- [ ] `DJANGO_SECRET_KEY`: Generate a random 64-character secret.
- [ ] `FIELD_ENCRYPTION_KEY`: Generate using `cryptography.fernet.Fernet.generate_key()`.
- [ ] `GITHUB_APP_ID`, `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`: Configured from your GitHub App.
- [ ] `GITHUB_PRIVATE_KEY_PATH`: Path to GitHub App `.pem` private key.
- [ ] `GITHUB_WEBHOOK_SECRET`: Secure webhook verification string.
- [ ] AI Provider Key: Encrypted in PostgreSQL via Dashboard UI or environment defaults.
- [ ] Verify health status: `curl https://api.commitflow.dev/api/health/` -> `{"status": "ok", "service": "commitflow-api"}`
