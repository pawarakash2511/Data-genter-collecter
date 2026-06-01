# Customer Data Collection

Full-stack web app — HTML/CSS/JS frontend, Python Flask backend, MySQL database — all containerized with Docker Compose.

## Business Logic

| Rule | Location |
|---|---|
| `some_number × 2` | `frontend/script.js` (before POST) |
| `age + 1` | `backend/app.py` (after receiving) |
| Submission timestamp | `backend/app.py` (UTC, at insert time) |

## Local Development

```bash
cp .env.example .env        # set credentials
docker-compose up --build   # starts frontend:80, backend:5000, mysql:3306
```

Open http://localhost to use the form.

**Verify data in MySQL:**
```bash
docker exec -it mysql mysql -u root -prootpassword customerdb -e "SELECT * FROM customers;"
```

## Docker Hub

```bash
# Build
docker-compose build

# Tag & push
docker tag pawarakash2511/customer-api:v1 pawarakash2511/customer-api:v1
docker push pawarakash2511/customer-api:v1

docker tag pawarakash2511/customer-ui:v1 pawarakash2511/customer-ui:v1
docker push pawarakash2511/customer-ui:v1
```

## AWS EC2 Deployment (Amazon Linux 2)

```bash
sudo yum update -y
sudo yum install docker -y
sudo service docker start
sudo usermod -aG docker ec2-user

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
  -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Clone and run
git clone <repo-url>
cd Data-genter-collecter
cp .env.example .env        # fill in credentials
docker-compose up -d
```

Open http://<ec2-public-ip> in a browser.

## API

**POST /api/customers**

```json
{
  "customer_id": "CUST001",
  "customer_name": "John Doe",
  "gender": "Male",
  "age": 25,
  "some_number": 20
}
```

Response:
```json
{ "status": "success", "message": "Customer data saved successfully" }
```
