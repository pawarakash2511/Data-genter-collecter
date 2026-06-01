# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**Customer Data Collection** — a full-stack web app that collects customer info via a form, applies business logic, and stores records in MySQL. Containerized with Docker Compose; deployable to AWS EC2.

## Stack

| Layer | Technology |
|---|---|
| Frontend | HTML5, CSS3, Vanilla JS (Nginx in Docker) |
| Backend | Python 3.11 + Flask |
| Database | MySQL 8.0 |
| Containers | Docker + Docker Compose |

## Commands

```bash
# Run backend tests locally (no Docker / no MySQL needed — DB is mocked)
cd backend && pytest tests/ -v

# Start everything (first time or after code changes)
docker-compose up --build

# Start in background
docker-compose up -d

# Stop
docker-compose down

# View logs
docker-compose logs -f backend

# Verify DB records
docker exec -it mysql mysql -u root -prootpassword customerdb -e "SELECT * FROM customers;"

# Build and push images to Docker Hub
docker-compose build
docker push pawarakash2511/customer-api:v1
docker push pawarakash2511/customer-ui:v1
```

## Architecture

```
frontend/ (port 80)  →  backend/ (port 5000)  →  mysql (port 3306)
```

- **`frontend/script.js`** — multiplies `some_number × 2` before POSTing to `/api/customers`
- **`backend/app.py`** — increments `age + 1`, generates `submitted_at`, calls `insert_customer()`
- **`backend/database.py`** — MySQL connection via env vars (`DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`)
- **`backend/models.py`** — `insert_customer(data)` executes the INSERT
- **`database/init.sql`** — auto-runs on first MySQL container start; creates `customerdb` and `customers` table

## Environment

Credentials live in `.env` (gitignored). Copy `.env.example` to `.env` and fill in values before running.

## Docker Hub

Images: `pawarakash2511/customer-api:v1` and `pawarakash2511/customer-ui:v1`

## Responsive Design

Frontend works on desktop, Android, and iPhone. Key techniques in `frontend/style.css` and `frontend/index.html`:
- `viewport-fit=cover` + `env(safe-area-inset-*)` — iPhone notch / Dynamic Island
- `font-size: 16px` on all inputs — prevents iOS auto-zoom on focus
- `min-height: 44px` on inputs/buttons — meets Apple HIG touch target size
- `100dvh` body height — fixes iOS Safari address bar issue
- `inputmode="numeric"` on number fields — shows numeric keypad on mobile
- `-webkit-text-size-adjust: 100%` — prevents font inflation on orientation change

## Tests

`backend/tests/test_app.py` — 18 pytest unit tests covering:
- Successful submission (201 + correct field values)
- `age + 1` business logic
- `some_number` stored as received (JS doubles it before POST)
- `submitted_at` is a `datetime` object
- Whitespace stripping on string fields
- All 3 gender options
- Boundary case: age = 0 → stored as 1
- Missing / empty field validation (400)
- Invalid JSON, no body (400)
- DB exception → 500

## CI/CD (GitHub Actions)

| Workflow | File | Trigger |
|---|---|---|
| CI | `.github/workflows/ci.yml` | Manual (`workflow_dispatch`) |
| CD | `.github/workflows/cd.yml` | Auto, when CI succeeds (`workflow_run`) |

**CI** — builds backend + frontend Docker images and pushes to Docker Hub under `pawarakash2511`.

**CD** — SSHs into AWS EC2, pulls latest images, runs `docker compose down && docker compose up -d`.

**GitHub Secrets to configure:**
- `DOCKER_USERNAME` = `pawarakash2511`
- `DOCKER_PASSWORD` = Docker Hub access token
- `EC2_HOST` = EC2 public IP
- `EC2_USER` = `ec2-user`
- `EC2_SSH_KEY` = PEM private key content
