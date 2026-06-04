# Customer Data Collection

Full-stack web app — HTML/CSS/JS frontend, Python Flask backend, MySQL database — containerized with Docker Compose and deployed to AWS EC2 via GitHub Actions.

> Full documentation: see **[docs.md](docs.md)**

## Business Logic

| Rule | Location |
|---|---|
| `some_number × 2` | `frontend/script.js` — before POST |
| `age + 1` | `backend/app.py` — after receiving |
| `submitted_at` | `backend/app.py` — UTC timestamp at insert |

## Quick Start (Local)

```bash
cp .env.example .env
docker-compose up --build
# Open http://localhost:8082
```

## Admin Panel

Click the **Admin Panel** button (top-right corner of the form) to access the admin dashboard.

| URL | |
|---|---|
| Local | `http://localhost:8082/admin.html` |
| EC2 | `http://<EC2-PUBLIC-IP>:8082/admin.html` |

Login with admin credentials, then view all submitted customer records in a table. Session expires after 8 hours. Protected by JWT — no access without valid login.

## Run Tests

```bash
cd backend && pytest tests/ -v
```

## CI/CD

| Workflow | Trigger |
|---|---|
| CI — test + build + push to Docker Hub | Manual (Actions tab → Run workflow) |
| CD — deploy to EC2 | Auto when CI succeeds |

## Docker Hub

```bash
docker push pawarakash2511/customer-api:latest
docker push pawarakash2511/customer-ui:latest
```

## Verify DB on EC2

```bash
docker exec -it mysql mysql -u root -pYOUR_PASSWORD customerdb -e "SELECT * FROM customers;"
```

## Live App

```
http://<EC2-PUBLIC-IP>:8082
http://<EC2-PUBLIC-IP>:8082/admin.html  ← Admin Panel
```
