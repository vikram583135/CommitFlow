# CommitFlow

CommitFlow proposes repository changes using a user-supplied AI provider, validates
those changes, and publishes a pull request after approval. It uses Django, Celery,
PostgreSQL/Redis, and a Next.js dashboard. The supported framework baselines are
Django 5.2 LTS, Next.js 16, React 19, and Node 24 for container deployments.

New rules require manual approval. Direct pushes always require approval. Missing
credentials and failed provider operations return errors; there is no demo login
or simulated publication in the application path.

## Development

1. Copy `.env.example` to `.env`. Keep `DEBUG=True` locally. Generate an encryption
   key before saving credentials:

   ```powershell
   backend\.venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

2. For Docker, set a database password and start the stack explicitly using the root
   environment file:

   ```powershell
   docker compose --env-file .env -f docker/docker-compose.yml up --build
   ```

   Open http://localhost:3000. Database and Redis ports are private to the Compose
   network. The API binds to localhost:8000. No public tunnel starts by default.

3. To run the backend directly, install `backend/requirements.txt` in a virtual
   environment, set `USE_SQLITE=True`, then run:

   ```powershell
   cd backend
   python manage.py migrate
   python manage.py reconcile_schedules
   python manage.py runserver
   ```

   Start Celery worker and Beat separately for queued/scheduled executions. A
   broker connection alone does not mean a worker is online. Production workers
   run on Linux; local API development and tests work on Windows.

4. Start the frontend with its existing `dev` script. Its API rewrite targets
   `http://127.0.0.1:8000` locally; `API_INTERNAL_URL` selects another backend.
   `NEXT_PUBLIC_API_URL` is optional and intended for a separately hosted API.

Email registration requires verification. In development, verification and password
reset links appear in backend console output. Existing unverified accounts can use
**Resend verification email** in the sign-in dialog. Production requires SMTP.

## Provider setup

- GitHub/Google sign-in requires real OAuth client IDs and secrets. Register the
  exact callback `${FRONTEND_URL}/auth/callback`; there are no credential fallbacks.
- OAuth uses single-use state, a browser-held PKCE verifier, and verified provider
  emails. Existing accounts must sign in before linking another provider.
- A GitHub App additionally needs its App ID and private key. Installation linking
  requires a verified GitHub user connection and installation ownership or
  organization administrator membership. The webhook secret is mandatory for
  webhook processing.
- Save an AI key through **AI Config**. **Save & Test** performs a real model request.
  OpenAI, Anthropic, and Gemini route to their corresponding provider endpoints.
  Model availability depends on your provider account.

## Execution guarantees and limits

- Related repositories and AI configurations are scoped to their owner, including
  a second ownership check in the worker.
- Allowed directories use repository-relative `/` paths, such as `src/, tests/`.
  Empty boundaries, sibling-prefix escapes, sensitive files, duplicate paths,
  common credential patterns, excessive file counts, and unchanged files fail
  validation. These rules do not replace a maintained external secret scanner.
- Context is pinned to a Git commit. Only files whose complete contents were read
  can be modified. Context is bounded to 15 text files / 150 KB and a 10,000-entry
  nontruncated tree; larger repositories need narrower task scopes or an extended
  context selection implementation.
- Proposals record their target, base commit, policy, contents, metadata, and hash.
  Approval applies to that snapshot. Policy changes invalidate it. Modified target
  branches are rejected before a new publication.
- Execution claims are atomic. Manual request keys and deterministic branches
  prevent duplicate publication when requests or queue deliveries repeat. A retry
  reconciles the original branch/PR instead of generating a replacement proposal.
- Transient provider failures retry with backoff. Interrupted workers become failed
  after 15 minutes and can be retried. A new run is needed to regenerate stale or
  rejected proposals. Queue failures never execute the pipeline inside an HTTP
  request.
- `MAX_DAILY_EXECUTIONS` limits AI generation attempts per user over a rolling
  24-hour window. Generation output is also bounded. This is a request budget,
  not a dollar-denominated spending guarantee. Provider billing remains external.
- Cron uses five fields and an IANA timezone. Schedules are registered in Celery
  Beat. Slots missed by more than five minutes are skipped; repeated local clock
  slots during DST changes deduplicate. Run exactly one Beat scheduler.
- The dashboard polls execution details and shows real validation results and
  diffs. Aggregate metrics cover all records, not just the current history page.

## Generated-code validation

Default checks are static: path policy, common secrets, substantive changes, and
Python/JSON syntax. They do not execute generated code or prove correctness. Other
languages still require a reviewer and repository CI.

An optional Python `unittest` runner is available with `ENABLE_PYTHON_SANDBOX=True`.
Run the validation worker directly on a dedicated Linux Docker host so its staging
directory is visible to the Docker daemon. It requires a preloaded
`PYTHON_SANDBOX_IMAGE`. Prefer a pinned image digest. The application never pulls
images automatically. The runner has no network, a read-only source mount/root,
no application secrets, an unprivileged user, dropped capabilities, and CPU,
memory, process, temporary-storage, output, and time limits. It rejects proposals
when no tests run, tests fail, or Docker is unavailable. Dependencies must already
exist in the chosen image. The default Compose deployment does not mount a Docker
socket into the worker; enable this only on an isolated validation worker host.

## Tests

Tests use an in-memory database and synthetic credentials, with no provider calls:

```powershell
cd backend
python -B manage.py test tests --settings=commitflow.test_settings
python -B manage.py makemigrations --check --dry-run --settings=commitflow.test_settings
```

Frontend type/build checks use `npm run typecheck` and `npm run build`.
GitHub regression tests exercise real HTTP request construction through a mocked
transport, including denied pushes, stale branches, and ambiguous PR creation.
The CI workflow runs the concurrency tests against PostgreSQL. To run that job
locally, point `TEST_POSTGRES_*` variables at a disposable database and use
`--settings=commitflow.postgres_test_settings`. Live provider/tunnel behavior also
requires deployment integration testing.

## Upgrading an existing installation

Back up the database and existing encryption key first. Stop workers/Beat, deploy
matching backend/frontend code, run migrations and `reconcile_schedules`, then
restart workers/Beat. Old proposals without an immutable snapshot must be
regenerated. Existing rules are moved to manual approval, and legacy App
installations are paused until ownership is verified again. Existing email accounts need verification; valid social sign-in
verifies the matching email. Retain the original encryption key to read stored
credentials. Changing it without a rotation/migration makes those records unreadable.

The previously embedded tunnel token must be revoked if it was ever used. Removing
it from this working tree does not revoke it or remove copies from Git history.
See [deployment instructions](cloudflare/README.md).
