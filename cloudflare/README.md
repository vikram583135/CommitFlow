# Cloudflare Production Deployment Guide for CommitFlow

This guide provides end-to-end, production-grade instructions to deploy the CommitFlow platform on Cloudflare infrastructure:

1. **Frontend:** Deployed to **Cloudflare Pages** (Global Edge CDN, automatic HTTPS, HTTP/3, zero cold starts).
2. **Backend & Workers:** Deployed to your VPS / server inside **Docker Compose** and securely exposed via **Cloudflare Tunnel (`cloudflared`)** with zero open firewall ports.

---

## 🏛 Architecture Diagram

```
                             ┌────────────────────────────────────────┐
                             │       Cloudflare Global Anycast        │
                             │         DNS + DDoS Mitigation          │
                             └───────────────────┬────────────────────┘
                                                 │
                        ┌────────────────────────┴────────────────────────┐
                        ▼                                                 ▼
             Cloudflare Pages (Edge)                             Cloudflare Tunnel
        (commitflow.dev / *.pages.dev)                   (api.commitflow.dev / cloudflared)
                        │                                                 │
                        │ HTTPS REST & SSE Streams                        │ Outbound-only Encrypted Tunnel
                        └────────────────────────┬────────────────────────┘ (Zero inbound ports required)
                                                 ▼
                                     ┌───────────────────────┐
                                     │   Your Host Server    │
                                     │    (Docker Compose)   │
                                     │                       │
                                     │ ┌───────────────────┐ │
                                     │ │   cloudflared     │ │
                                     │ └─────────┬─────────┘ │
                                     │           ▼           │
                                     │ ┌───────────────────┐ │
                                     │ │   Django Gunicorn │ │
                                     │ └─────────┬─────────┘ │
                                     │           ▼           │
                                     │ ┌───────────────────┐ │
                                     │ │  Celery Workers   │ │
                                     │ └─────────┬─────────┘ │
                                     │           ▼           │
                                     │ ┌───────────────────┐ │
                                     │ │  Postgres & Redis │ │
                                     │ └───────────────────┘ │
                                     └───────────────────────┘
```

---

## 📋 Prerequisites

- A domain active on Cloudflare (e.g. `yourdomain.com`).
- A Linux VPS (Ubuntu 22.04 / 24.04 or Debian) with **Docker** and **Docker Compose** installed.
- A free or paid [Cloudflare Account](https://dash.cloudflare.com/).

---

## Part 1: Backend Deployment with Cloudflare Tunnel

Cloudflare Tunnel creates an encrypted outbound connection between your server and Cloudflare's edge. You **never need to open ports 80, 443, or 8000** in your VPS firewall.

We support two modes:
- **Option 1 (Default): Quick Tunnel** — 100% free, instant, zero custom domain required.
- **Option 2: Named Tunnel (`commitflow-production`)** — Permanent custom subdomains once a domain is linked to Cloudflare.

---

### Option 1: Quick Tunnel (`*.trycloudflare.com`) — Instant & Zero-Domain (Default)

Use this to get an instant public HTTPS URL without needing a registered domain or Cloudflare account token.

#### Step 1: Docker Compose Setup (Active in repo)
The `cloudflared` service in [`docker/docker-compose.yml`](file:///c:/Users/sanvi/Desktop/PROJ/CommitFlow/docker/docker-compose.yml#L110-L115) is configured by default:

```yaml
  cloudflared:
    image: cloudflare/cloudflared:latest
    container_name: commitflow_tunnel
    restart: unless-stopped
    command: tunnel --no-autoupdate --url http://backend:8000
    depends_on:
      - backend
```

#### Step 2: Start Containers and Retrieve Your Public URL
```bash
# Start your docker compose stack
docker compose -f docker/docker-compose.yml up -d --build

# View the generated trycloudflare URL in container logs
docker logs commitflow_tunnel
```

Look for the log banner:
```
+--------------------------------------------------------------------------------------------+
|  Your quick Tunnel has been created! Visit it at:                                          |
|  https://random-assigned-name.trycloudflare.com                                            |
+--------------------------------------------------------------------------------------------+
```

#### Step 3: Local Windows Testing Without Docker
You can also run the local tunnel directly on your machine:
```powershell
.\cloudflare\cloudflared.exe tunnel --url http://127.0.0.1:8000
```

Both your API and health checks are immediately reachable:
- `https://<your-quick-url>.trycloudflare.com/api/`
- `https://<your-quick-url>.trycloudflare.com/api/health/`

*(Note: CommitFlow backend is already pre-configured to allow `*.trycloudflare.com` in `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`).*

---

### Option 2: Named Production Tunnel (`commitflow-production`) — Permanent Subdomains

When you are ready for a permanent custom domain (e.g. `api.yourdomain.com`):

#### Step 1: Add Token to `.env`
Add your tunnel token to your server's `.env` file (the `commitflow-production` token is already saved in your local `.env`):
```ini
CLOUDFLARE_TUNNEL_TOKEN=eyJoIjoiMjhjNmQ1MGItOWMyNi00ODFjLTg0MGQtMTA0NzA3MmFhMWFhIiwidCI6IjM3ZDI4YWNlNDllNzQ5MTAzZjgxMDE1YThlYjBhZWQ4IiwicyI6Ik1XTmtZVFkwTURndE1qUTNZUzAwTlRVMExUa3lZbVV0WWpJM01ERTVZVEJpTkRVMiJ9
```

#### Step 2: Switch Docker Compose to Named Tunnel Mode
In [`docker/docker-compose.yml`](file:///c:/Users/sanvi/Desktop/PROJ/CommitFlow/docker/docker-compose.yml#L114):
```yaml
  cloudflared:
    image: cloudflare/cloudflared:latest
    container_name: commitflow_tunnel
    restart: unless-stopped
    command: tunnel --no-autoupdate run --token ${CLOUDFLARE_TUNNEL_TOKEN}
    depends_on:
      - backend
```

#### Step 3: Configure Public Hostnames in Cloudflare Zero Trust
1. In [Cloudflare Zero Trust Dashboard](https://one.dash.cloudflare.com/) → **Networks** → **Tunnels**.
2. Click **commitflow-production** → **Configure** → **Public Hostname** tab:
   - **Service 1 (Backend API & SSE):**
     - Subdomain: `api` | Domain: `yourdomain.com`
     - Type: `HTTP` | URL: `backend:8000`
   - **Service 2 (Health Check):**
     - Subdomain: `health` | Domain: `yourdomain.com`
     - Type: `HTTP` | URL: `backend:8000` | Path: `/api/health/`
3. Click **Save Hostname**.

#### 💡 Free Domain Options for Named Tunnels
If you don't own a paid domain:
- **GitHub Student Developer Pack:** Free `.me`, `.tech`, or `.live` domain from Namecheap / Name.com.
- **Free Registrars:** Free domains from `US.kg` or `EU.org` which support Cloudflare nameservers.


---

## Part 2: Backend Production Environment Settings

Ensure the following variables are set in your VPS `.env` file:

```ini
# Core Django
DEBUG=False
DJANGO_SECRET_KEY=generate_with_python_secrets_token_urlsafe_64
ALLOWED_HOSTS=api.yourdomain.com,backend,localhost

# Frontend Origin for CORS & OAuth
FRONTEND_URL=https://yourdomain.com

# PostgreSQL & Redis
POSTGRES_DB=commitflow
POSTGRES_USER=commitflow_user
POSTGRES_PASSWORD=strong_postgres_password_here
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# Encryption Key (Fernet 32-byte key)
# Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
FIELD_ENCRYPTION_KEY=your_generated_32_byte_fernet_key=

# GitHub App / OAuth
GITHUB_APP_ID=123456
GITHUB_APP_NAME=commitflow-bot
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret
GITHUB_WEBHOOK_SECRET=your_webhook_secret

# Google OAuth
GOOGLE_CLIENT_ID=your_google_client_id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_google_client_secret

# AI Provider Keys (Optional defaults)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=AIzaSy...
```

Start the stack on your VPS:
```bash
docker compose -f docker/docker-compose.yml up -d --build
```

Verify the tunnel and API health:
```bash
curl https://api.yourdomain.com/api/health/
# Returns: {"status": "ok", "service": "commitflow-api"}
```

---

## Part 3: Deploying Frontend to Cloudflare Pages

### Method 1: Git Integration (Automatic CI/CD via Cloudflare Dashboard)

1. Push your repository to **GitHub** or **GitLab**.
2. Go to **Cloudflare Dashboard** → **Workers & Pages** → **Create application** → **Pages** → **Connect to Git**.
3. Select your `CommitFlow` repository and choose the `main` branch.
4. Set the **Build configuration**:
   - **Framework preset:** `Next.js (Static / Standalone)`
   - **Root directory:** `frontend`
   - **Build command:** `npm run build`
   - **Build output directory:** `.next` (or `out` if using static export)
5. Add **Environment Variables** in the Pages project settings:
   - `NEXT_PUBLIC_API_URL` = `https://api.yourdomain.com`
   - `NODE_VERSION` = `20.10.0`
6. Click **Save and Deploy**.

### Method 2: Deploying via Wrangler CLI

You can also deploy directly from your local terminal or CI runner:

```bash
cd frontend

# 1. Install Wrangler CLI
npm install -g wrangler

# 2. Login to Cloudflare
npx wrangler login

# 3. Build and deploy
npm run build
npx wrangler pages deploy .next --project-name commitflow-frontend
```

---

## Part 4: Custom Domain & DNS Mapping

1. In Cloudflare Pages, go to **Custom Domains** → **Set up a custom domain**.
2. Enter your apex domain or subdomain:
   - Apex: `yourdomain.com`
   - Or Subdomain: `app.yourdomain.com`
3. Cloudflare will automatically provision a universal SSL/TLS certificate and configure DNS routing.

---

## Part 5: Cloudflare Network & Security Optimizations

### 1. SSL/TLS Mode
- In Cloudflare Dashboard → **SSL/TLS**:
  - Set encryption mode to **Full (strict)** or **Full**.

### 2. Real-Time Server-Sent Events (SSE) Execution Stepper
CommitFlow streams execution progress via Server-Sent Events (`/api/executions/<id>/stream/`).
- In Cloudflare Dashboard → **Network**:
  - Enable **WebSockets**.
  - CommitFlow backend sets `Cache-Control: no-cache` and `X-Accel-Buffering: no`, ensuring Cloudflare does not buffer streaming events.

### 3. Rate Limiting & Anti-DDoS
- In Cloudflare Dashboard → **Security** → **WAF** → **Rate limiting rules**:
  - Set a threshold of 100 requests per 10 seconds for `/api/auth/*` to prevent credential brute-forcing.

---

## Part 6: Verification Checklist

- [ ] `curl -I https://yourdomain.com` → HTTP 200 (Cloudflare Pages CDN cache hit `cf-cache-status`).
- [ ] `curl https://api.yourdomain.com/api/health/` → `{"status": "ok", "service": "commitflow-api"}`.
- [ ] Log in with GitHub or Google OAuth on `https://yourdomain.com`.
- [ ] Create an automation habit and click "Run Now" to test the real-time SSE execution drawer.
- [ ] Check Celery Beat logs on the VPS: `docker compose logs -f celery_beat`.
