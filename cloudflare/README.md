# Deployment with a named Cloudflare Tunnel

Deploy the Django/Celery services and standalone Next.js Node server using Docker.
The frontend depends on server-side API rewrites, so uploading a raw `.next`
directory to Cloudflare Pages is not a supported deployment for this configuration.
A separate Workers/static-export deployment needs its own build and routing setup.

## Prepare production configuration

Copy `.env.example` and set:

- `DEBUG=False`.
- A unique `DJANGO_SECRET_KEY` of at least 50 characters. Generate it with Python's
  `secrets.token_urlsafe(64)`.
- A generated, unique `FIELD_ENCRYPTION_KEY` from `Fernet.generate_key()`.
- `FRONTEND_URL=https://app.example.com` and
  `ALLOWED_HOSTS=app.example.com,api.example.com,backend,localhost`.
- A strong PostgreSQL password, GitHub/Google credentials, GitHub App private key,
  and a strong `GITHUB_WEBHOOK_SECRET`.
- Working SMTP settings and a verified `DEFAULT_FROM_EMAIL` sender.
- `CLOUDFLARE_TUNNEL_TOKEN` from a named tunnel you control. Never put tokens in
  documentation, source control, browser code, or command history.

For existing data, preserve the encryption key until credentials have been
explicitly migrated or re-entered. Take a database backup before schema upgrades.
Production startup refuses missing/known development signing and encryption keys.
HSTS preload is left opt-in; enable it only after reviewing your domain and
subdomains' long-term HTTPS requirements.

## Start and verify

```powershell
docker compose --env-file .env -f docker/docker-compose.yml up --build -d
docker compose --env-file .env -f docker/docker-compose.yml ps
```

A migration service finishes schema migrations, schedule reconciliation, and static
collection before the API starts. Workers and Beat wait for API readiness. The
health endpoint checks both the database and cache. Keep exactly one Beat instance.

Containers run Gunicorn and the built Next.js server as unprivileged users. Redis
and PostgreSQL have no published host ports. API/frontend ports bind only to host
loopback. The optional tunnel is the public ingress. Serve Django admin static
assets from a separate trusted static server/CDN if using the admin in production.

## Configure the tunnel

In the named tunnel's public-hostname settings, route:

- `app.example.com` to `http://frontend:3000`.
- Optionally `api.example.com` to `http://backend:8000` for webhooks and direct API
  clients. Browser requests can use the frontend's same-origin `/api` rewrite.

Then start the explicitly enabled tunnel service:

```powershell
docker compose --env-file .env -f docker/docker-compose.yml --profile tunnel up -d
```

The token is passed through the container environment, not command-line arguments.
The checked-in YAML tunnel configurations contain placeholders for locally managed
tunnels. Quick Tunnels are for development, have changing hostnames, and do not
support SSE. The dashboard uses authenticated polling.

## Operational checks

- Open the public frontend and confirm the readiness endpoint returns HTTP 200.
- Complete email verification or real OAuth sign-in and connect GitHub.
- Save/test a real AI key and synchronize repositories.
- Create a rule with manual approval; inspect its actual diff before approval.
- Confirm the resulting PR/commit on GitHub. Local unit tests do not establish live
  installation permissions, organization policy, branch protections, or provider
  model access.
- Confirm scheduled dispatch, retry/reconciliation, SMTP delivery, and worker
  restart behavior against PostgreSQL before enabling unattended execution.
- Configure edge rate limits for authentication and execution endpoints. Application
  throttles are an additional control; they are not a complete DDoS defense.
- Monitor failed executions, repeated queue failures, worker availability, daily
  generation usage, GitHub rate limits, and database/Redis backups. Do not log
  request bodies or provider credentials.

The project previously contained a tunnel token in this guide. If it was genuine,
revoke it in Cloudflare and replace the affected deployment token. Scrubbing this
file does not invalidate the token or erase its history. No credential rotation or
production deployment is performed by editing these files.
