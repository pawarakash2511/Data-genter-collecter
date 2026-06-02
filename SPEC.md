# Project Specification (spec.md)

## Project Name

Customer Data Collection Web Application

---

# Objective

Build a full-stack web application that collects customer information through a web form, processes specific business logic, and stores the data in a SQL database.

The complete solution must be containerized using Docker and deployed using Docker Compose on an AWS Linux server.

---

# Technology Stack

## Frontend

* HTML5
* CSS3
* JavaScript (Vanilla JS)

## Backend

* Python
* Flask Framework

## Database

* MySQL

## Containerization

* Docker
* Docker Compose

## Deployment Environment

* AWS Linux EC2 Instance

---

# Functional Requirements

## Customer Input Form

The UI should contain the following fields:

| Field Name    | Type     | Required |
| ------------- | -------- | -------- |
| Customer ID   | Text     | Yes      |
| Customer Name | Text     | Yes      |
| Gender        | Dropdown | Yes      |
| Age           | Number   | Yes      |
| Some Number   | Number   | Yes      |

### Gender Options

* Male
* Female
* Other

---

## Submit Button

A Submit button should be provided.

When the user clicks Submit:

1. Form data should be validated.
2. Business logic should execute.
3. Data should be stored in the database.
4. Success message should be displayed.
5. Form fields should be cleared/reset automatically.

---

# Business Logic

## Age Processing (Python Backend)

The age value entered by the user must be incremented by 1.

Example:

Input Age:
25

Stored Age:
26

This logic must execute in Python backend code.

---

## Some Number Processing (JavaScript Frontend)

The entered number should be multiplied by 2 using JavaScript before sending data to backend.

Example:

Input:
10

Processed Value:
20

The processed value should be sent to the backend API.

---

# Database Requirements

## Database Engine

MySQL

## Table Name

customers

## Table Structure

| Column Name   | Data Type                      |
| ------------- | ------------------------------ |
| id            | INT AUTO_INCREMENT PRIMARY KEY |
| customer_id   | VARCHAR(100)                   |
| customer_name | VARCHAR(255)                   |
| gender        | VARCHAR(20)                    |
| age           | INT                            |
| some_number   | INT                            |
| submitted_at  | DATETIME                       |

---

# Submission Timestamp

The application must automatically store the submission date and time.

Example:

submitted_at:
2026-06-01 21:30:45

Timestamp should be generated on the backend during record insertion.

---

# API Requirements

## POST /api/customers

Purpose:
Store customer information.

Request Example

```json
{
  "customer_id": "CUST001",
  "customer_name": "John Doe",
  "gender": "Male",
  "age": 25,
  "some_number": 20
}
```

Response Example

```json
{
  "status": "success",
  "message": "Customer data saved successfully"
}
```

---

# User Interface Requirements

## Theme

Background:

* Light Blue

Text:

* Black

Buttons:

* Blue

Form:

* Center aligned

Responsive:

* Yes

---

# Frontend Requirements

The frontend must:

* Call backend REST API
* Perform JavaScript calculation:

  * some_number = some_number * 2
* Display success message
* Reset form after successful submission
* Handle API errors gracefully

---

# Backend Requirements

The backend must:

* Expose REST APIs
* Validate request payload
* Increase age by 1
* Insert records into MySQL
* Store submission timestamp
* Return JSON responses
* Handle exceptions properly

---

# Docker Requirements

## Containers

1. Frontend Container
2. Backend Container
3. MySQL Container

All services must run using Docker Compose.

---

## docker-compose.yml

Services:

* frontend
* backend
* mysql

Requirements:

* Internal Docker networking
* Persistent MySQL volume
* Environment variables for DB credentials

---

# AWS Deployment Requirements

Deploy on AWS Linux EC2 instance.

Steps:

1. Launch EC2 instance.
2. Install Docker.
3. Install Docker Compose.
4. Clone repository.
5. Pull images from Docker Hub.
6. Start application using Docker Compose.

Commands should be documented in README.md.

---

# Docker Hub Requirements

Build and push images:

Frontend Image:

* akash/customer-ui

Backend Image:

* akash/customer-api

Images should be versioned using tags.

Example:

```bash
docker tag customer-api akash/customer-api:v1
docker push akash/customer-api:v1
```

---

# Project Structure

```text
project-root/
│
├── frontend/
│   ├── index.html
│   ├── style.css
│   ├── script.js
│   └── Dockerfile
│
├── backend/
│   ├── app.py
│   ├── requirements.txt
│   ├── models.py
│   ├── database.py
│   └── Dockerfile
│
├── database/
│   └── init.sql
│
├── docker-compose.yml
├── README.md
└── .env
```

---

# Non-Functional Requirements

* Clean and modular code
* Proper error handling
* Dockerized architecture
* Environment variable configuration
* Responsive UI — fully compatible with desktop browsers, Android, and iPhone (including notch/Dynamic Island safe areas)
* REST API design standards
* MySQL persistent storage
* Production-ready deployment structure

---

# Acceptance Criteria

✓ User can submit customer information

✓ some_number is multiplied by 2 in JavaScript

✓ age is incremented by 1 in Python backend

✓ Data is stored in MySQL

✓ Submission timestamp is stored

✓ Form resets after successful submission

✓ Application runs through Docker Compose

✓ Images can be pushed to Docker Hub

✓ Solution deploys successfully on AWS Linux EC2

✓ UI follows blue theme with black text

✓ UI is responsive and works on desktop, Android, and iPhone (safe-area-inset, 16px inputs, 44px touch targets)

✓ Backend unit tests pass (pytest, DB mocked)

✓ CI pipeline runs tests then builds and pushes Docker images to Docker Hub (manual trigger)

✓ CD pipeline deploys to AWS EC2 automatically after CI succeeds

---

# CI/CD Requirements

## Platform

GitHub Actions

## Workflows

### CI — `.github/workflows/ci.yml`

* Trigger: Manual (`workflow_dispatch`)
* Steps:
  1. Checkout code
  2. Log in to Docker Hub (`pawarakash2511`)
  3. Build backend image → push as `pawarakash2511/customer-api:v1` and `:latest`
  4. Build frontend image → push as `pawarakash2511/customer-ui:v1` and `:latest`

### CD — `.github/workflows/cd.yml`

* Trigger: Automatically when CI workflow completes successfully (`workflow_run` on `completed` + `conclusion == success`)
* Steps:
  1. SSH into AWS EC2 instance
  2. Pull latest images from Docker Hub
  3. `docker compose down && docker compose up -d`

## GitHub Secrets Required

| Secret | Value |
| --- | --- |
| `DOCKER_USERNAME` | `pawarakash2511` |
| `DOCKER_PASSWORD` | Docker Hub access token |
| `EC2_HOST` | EC2 public IP or hostname |
| `EC2_USER` | `ec2-user` (Amazon Linux) |
| `EC2_SSH_KEY` | Private SSH key (PEM content) |

