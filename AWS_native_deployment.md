# AWS Native Deployment Guide

## Customer Data Collection App — ECR + ECS Fargate + RDS

This guide migrates the app from Docker Compose on EC2 to fully managed AWS services.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [AWS Services Used](#aws-services-used)
4. [Prerequisites](#prerequisites)
5. [Step 1: VPC & Networking](#step-1-vpc--networking)
6. [Step 2: Security Groups](#step-2-security-groups)
7. [Step 3: RDS MySQL 8.0](#step-3-rds-mysql-80)
8. [Step 4: Secrets Manager](#step-4-secrets-manager)
9. [Step 5: ECR — Docker Image Registry](#step-5-ecr--docker-image-registry)
10. [Step 6: IAM Roles](#step-6-iam-roles)
11. [Step 7: Cloud Map — Service Discovery](#step-7-cloud-map--service-discovery)
12. [Step 8: ECS Cluster](#step-8-ecs-cluster)
13. [Step 9: ECS Task Definitions](#step-9-ecs-task-definitions)
14. [Step 10: ECS Services](#step-10-ecs-services)
15. [Step 11: Application Load Balancer](#step-11-application-load-balancer)
16. [Step 12: Update CI/CD Workflows](#step-12-update-cicd-workflows)
17. [Step 13: nginx.conf Update for ECS](#step-13-nginxconf-update-for-ecs)
18. [Verification](#verification)
19. [Cost Estimate](#cost-estimate)
20. [EC2 Docker Compose vs AWS Native](#ec2-docker-compose-vs-aws-native)
21. [Troubleshooting](#troubleshooting)

---

## Overview

### Why migrate from EC2 + Docker Compose to AWS native services?

| Concern | EC2 + Docker Compose | ECR + ECS + RDS |
|---|---|---|
| Server management | Manual — you patch OS, restart crashed containers | Zero — AWS manages everything |
| Database backups | Manual or scripted | Automated daily snapshots, point-in-time recovery |
| Scaling | Manual — resize EC2 or add instances | Auto-scaling — ECS adds/removes containers automatically |
| High availability | Single EC2 = single point of failure | Multi-AZ RDS + ECS across 2 AZs |
| Image storage | Docker Hub (public) | ECR (private, inside your AWS account) |
| Secret management | `.env` file on server | AWS Secrets Manager (encrypted, audited, rotatable) |
| Logs | `docker logs` (lost if container restarts) | CloudWatch Logs (persistent, searchable, alarming) |
| Deployment | SSH + git pull + docker-compose up | `aws ecs update-service` — rolling update, zero downtime |

---

## Architecture

```
                          Internet
                              │
                    ┌─────────▼─────────┐
                    │  ALB (port 80)    │  ← Single public entry point
                    │  Public Subnet    │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼──────────────────┐
                    │  ECS Fargate                │
                    │  Frontend Service (Nginx)   │  ← Public Subnet
                    │  Serves HTML/CSS/JS         │
                    │  Proxies /api/ →            │
                    └─────────┬──────────────────-┘
                              │ Cloud Map DNS
                              │ backend.app.local:5000
                    ┌─────────▼──────────────────┐
                    │  ECS Fargate                │
                    │  Backend Service (Flask)    │  ← Private Subnet
                    │  POST /api/customers        │
                    └─────────┬──────────────────-┘
                              │
                    ┌─────────▼──────────────────┐
                    │  RDS MySQL 8.0             │  ← Private Subnet
                    │  Multi-AZ (optional)        │
                    │  Automated backups          │
                    └────────────────────────────┘

Supporting services:
  ECR          — stores customer-api and customer-ui Docker images
  Secrets Mgr  — stores DB_PASSWORD (encrypted)
  CloudWatch   — logs from both ECS services
  Cloud Map    — internal DNS: backend.app.local resolves to backend ECS tasks
  IAM          — roles for ECS to pull images, read secrets, write logs
```

---

## AWS Services Used

| Service | Role | Replaces |
|---|---|---|
| **ECR** | Private Docker image registry | Docker Hub |
| **ECS Fargate** | Serverless container runtime | `docker-compose` on EC2 |
| **RDS MySQL 8.0** | Managed database with automated backups | `mysql` container |
| **ALB** | Layer-7 load balancer, public entry point | EC2 port 8082 |
| **Cloud Map** | Internal service discovery DNS | Docker internal network DNS |
| **Secrets Manager** | Encrypted credential storage | `.env` file |
| **CloudWatch Logs** | Log storage, retention, search | `docker logs` |
| **VPC** | Network isolation | Docker `app-network` |
| **IAM** | Permissions for ECS tasks | N/A |

---

## Prerequisites

- AWS account with admin or sufficient IAM permissions
- AWS CLI v2 installed and configured (`aws configure`)
- Docker installed locally
- GitHub repo with existing CI/CD workflows
- Existing Docker images pushed to Docker Hub (we will also push to ECR)

### Install and configure AWS CLI

```bash
# Install AWS CLI v2 (Linux/Mac)
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Configure with your IAM credentials
aws configure
# Enter: AWS Access Key ID, Secret Access Key, Region (e.g. ap-south-1), output format (json)

# Verify
aws sts get-caller-identity
```

Set your region as a variable for all commands:

```bash
export AWS_REGION=ap-south-1       # change to your region
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "Account: $AWS_ACCOUNT_ID | Region: $AWS_REGION"
```

---

## Step 1: VPC & Networking

### Option A: Use AWS Console (easiest)

1. Go to **VPC → Create VPC**
2. Select **VPC and more** (auto-creates subnets, IGW, route tables)
3. Settings:
   - Name: `customer-app-vpc`
   - IPv4 CIDR: `10.0.0.0/16`
   - Availability Zones: `2`
   - Public subnets: `2` (for ALB and ECS frontend)
   - Private subnets: `2` (for ECS backend and RDS)
   - NAT Gateway: `1` (needed for ECS tasks in private subnet to pull images)
4. Click **Create VPC**

> Note down the VPC ID, public subnet IDs, and private subnet IDs — you'll need them in every step.

### Option B: AWS CLI

```bash
# Create VPC
VPC_ID=$(aws ec2 create-vpc \
  --cidr-block 10.0.0.0/16 \
  --tag-specifications 'ResourceType=vpc,Tags=[{Key=Name,Value=customer-app-vpc}]' \
  --query 'Vpc.VpcId' --output text)
echo "VPC: $VPC_ID"

# Enable DNS hostnames (required for RDS)
aws ec2 modify-vpc-attribute --vpc-id $VPC_ID --enable-dns-hostnames

# Create Internet Gateway
IGW_ID=$(aws ec2 create-internet-gateway \
  --tag-specifications 'ResourceType=internet-gateway,Tags=[{Key=Name,Value=customer-app-igw}]' \
  --query 'InternetGateway.InternetGatewayId' --output text)
aws ec2 attach-internet-gateway --internet-gateway-id $IGW_ID --vpc-id $VPC_ID

# Create public subnets (2 AZs)
PUB_SUBNET_1=$(aws ec2 create-subnet \
  --vpc-id $VPC_ID --cidr-block 10.0.1.0/24 \
  --availability-zone ${AWS_REGION}a \
  --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=public-subnet-1}]' \
  --query 'Subnet.SubnetId' --output text)

PUB_SUBNET_2=$(aws ec2 create-subnet \
  --vpc-id $VPC_ID --cidr-block 10.0.2.0/24 \
  --availability-zone ${AWS_REGION}b \
  --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=public-subnet-2}]' \
  --query 'Subnet.SubnetId' --output text)

# Create private subnets (2 AZs)
PRIV_SUBNET_1=$(aws ec2 create-subnet \
  --vpc-id $VPC_ID --cidr-block 10.0.3.0/24 \
  --availability-zone ${AWS_REGION}a \
  --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=private-subnet-1}]' \
  --query 'Subnet.SubnetId' --output text)

PRIV_SUBNET_2=$(aws ec2 create-subnet \
  --vpc-id $VPC_ID --cidr-block 10.0.4.0/24 \
  --availability-zone ${AWS_REGION}b \
  --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=private-subnet-2}]' \
  --query 'Subnet.SubnetId' --output text)

echo "Public: $PUB_SUBNET_1, $PUB_SUBNET_2"
echo "Private: $PRIV_SUBNET_1, $PRIV_SUBNET_2"

# Public route table → Internet Gateway
PUB_RT=$(aws ec2 create-route-table --vpc-id $VPC_ID \
  --tag-specifications 'ResourceType=route-table,Tags=[{Key=Name,Value=public-rt}]' \
  --query 'RouteTable.RouteTableId' --output text)
aws ec2 create-route --route-table-id $PUB_RT --destination-cidr-block 0.0.0.0/0 --gateway-id $IGW_ID
aws ec2 associate-route-table --route-table-id $PUB_RT --subnet-id $PUB_SUBNET_1
aws ec2 associate-route-table --route-table-id $PUB_RT --subnet-id $PUB_SUBNET_2

# NAT Gateway for private subnets (ECS tasks need this to pull images from ECR)
EIP=$(aws ec2 allocate-address --domain vpc --query 'AllocationId' --output text)
NAT_GW=$(aws ec2 create-nat-gateway \
  --subnet-id $PUB_SUBNET_1 --allocation-id $EIP \
  --tag-specifications 'ResourceType=natgateway,Tags=[{Key=Name,Value=customer-nat}]' \
  --query 'NatGateway.NatGatewayId' --output text)
echo "Waiting for NAT Gateway to become available..."
aws ec2 wait nat-gateway-available --nat-gateway-ids $NAT_GW

# Private route table → NAT Gateway
PRIV_RT=$(aws ec2 create-route-table --vpc-id $VPC_ID \
  --tag-specifications 'ResourceType=route-table,Tags=[{Key=Name,Value=private-rt}]' \
  --query 'RouteTable.RouteTableId' --output text)
aws ec2 create-route --route-table-id $PRIV_RT --destination-cidr-block 0.0.0.0/0 --nat-gateway-id $NAT_GW
aws ec2 associate-route-table --route-table-id $PRIV_RT --subnet-id $PRIV_SUBNET_1
aws ec2 associate-route-table --route-table-id $PRIV_RT --subnet-id $PRIV_SUBNET_2
```

---

## Step 2: Security Groups

Create 4 security groups with least-privilege rules:

```bash
# ALB Security Group — accepts internet traffic
ALB_SG=$(aws ec2 create-security-group \
  --group-name alb-sg --description "ALB inbound" --vpc-id $VPC_ID \
  --query 'GroupId' --output text)
aws ec2 authorize-security-group-ingress --group-id $ALB_SG \
  --ip-permissions '[{"IpProtocol":"tcp","FromPort":80,"ToPort":80,"IpRanges":[{"CidrIp":"0.0.0.0/0"}]},{"IpProtocol":"tcp","FromPort":443,"ToPort":443,"IpRanges":[{"CidrIp":"0.0.0.0/0"}]}]'

# Frontend (Nginx) Security Group — accepts traffic from ALB only
FRONTEND_SG=$(aws ec2 create-security-group \
  --group-name frontend-sg --description "Frontend ECS" --vpc-id $VPC_ID \
  --query 'GroupId' --output text)
aws ec2 authorize-security-group-ingress --group-id $FRONTEND_SG \
  --protocol tcp --port 80 --source-group $ALB_SG

# Backend (Flask) Security Group — accepts traffic from Frontend ECS only
BACKEND_SG=$(aws ec2 create-security-group \
  --group-name backend-sg --description "Backend ECS" --vpc-id $VPC_ID \
  --query 'GroupId' --output text)
aws ec2 authorize-security-group-ingress --group-id $BACKEND_SG \
  --protocol tcp --port 5000 --source-group $FRONTEND_SG

# RDS Security Group — accepts traffic from Backend ECS only
RDS_SG=$(aws ec2 create-security-group \
  --group-name rds-sg --description "RDS MySQL" --vpc-id $VPC_ID \
  --query 'GroupId' --output text)
aws ec2 authorize-security-group-ingress --group-id $RDS_SG \
  --protocol tcp --port 3306 --source-group $BACKEND_SG

echo "ALB SG: $ALB_SG | Frontend SG: $FRONTEND_SG | Backend SG: $BACKEND_SG | RDS SG: $RDS_SG"
```

### Console alternative
- EC2 → Security Groups → Create security group
- Name each SG, select your VPC, add inbound rules as above

---

## Step 3: RDS MySQL 8.0

### Create DB Subnet Group

```bash
aws rds create-db-subnet-group \
  --db-subnet-group-name customer-db-subnet-group \
  --db-subnet-group-description "Subnet group for customer app RDS" \
  --subnet-ids $PRIV_SUBNET_1 $PRIV_SUBNET_2
```

### Create RDS MySQL Instance

```bash
aws rds create-db-instance \
  --db-instance-identifier customer-mysql \
  --db-instance-class db.t3.micro \
  --engine mysql \
  --engine-version 8.0 \
  --master-username root \
  --master-user-password YOUR_DB_PASSWORD \
  --db-name customerdb \
  --vpc-security-group-ids $RDS_SG \
  --db-subnet-group-name customer-db-subnet-group \
  --no-publicly-accessible \
  --storage-type gp2 \
  --allocated-storage 20 \
  --backup-retention-period 7 \
  --tags Key=Name,Value=customer-mysql
```

> This takes ~5 minutes. Wait for it:

```bash
aws rds wait db-instance-available --db-instance-identifier customer-mysql

# Get the RDS endpoint (you'll need this later)
RDS_ENDPOINT=$(aws rds describe-db-instances \
  --db-instance-identifier customer-mysql \
  --query 'DBInstances[0].Endpoint.Address' --output text)
echo "RDS Endpoint: $RDS_ENDPOINT"
```

### Initialize the database table

Connect via a temporary EC2 instance in the same VPC, or use ECS Exec after the backend is running:

```bash
# After ECS is running, execute inside backend container:
aws ecs execute-command \
  --cluster customer-cluster \
  --task <TASK_ID> \
  --container backend \
  --command "mysql -h $RDS_ENDPOINT -u root -pYOUR_PASSWORD customerdb" \
  --interactive
```

Then paste the contents of `database/init.sql`:

```sql
CREATE DATABASE IF NOT EXISTS customerdb;
USE customerdb;
CREATE TABLE IF NOT EXISTS customers (
  id INT AUTO_INCREMENT PRIMARY KEY,
  customer_id VARCHAR(100) NOT NULL,
  customer_name VARCHAR(255) NOT NULL,
  gender VARCHAR(20) NOT NULL,
  age INT NOT NULL,
  some_number INT NOT NULL,
  submitted_at DATETIME NOT NULL
);
```

### Console alternative
- RDS → Create database → Standard create → MySQL 8.0
- Template: Free tier (for dev) or Production (for prod)
- DB instance identifier: `customer-mysql`
- Master username: `root`, set password
- DB name: `customerdb`
- VPC: select your VPC, private subnets, RDS security group
- Public access: No

---

## Step 4: Secrets Manager

Store the DB password securely — ECS will inject it as an environment variable:

```bash
aws secretsmanager create-secret \
  --name customer-app/db-password \
  --description "MySQL password for customer app" \
  --secret-string "{\"DB_PASSWORD\":\"YOUR_DB_PASSWORD\"}"

# Get the secret ARN (save this for task definitions)
SECRET_ARN=$(aws secretsmanager describe-secret \
  --secret-id customer-app/db-password \
  --query 'ARN' --output text)
echo "Secret ARN: $SECRET_ARN"
```

### Console alternative
- Secrets Manager → Store a new secret
- Secret type: Other type of secret
- Key: `DB_PASSWORD`, Value: your password
- Secret name: `customer-app/db-password`

---

## Step 5: ECR — Docker Image Registry

### Create ECR repositories

```bash
# Create backend repo
aws ecr create-repository \
  --repository-name customer-api \
  --image-scanning-configuration scanOnPush=true \
  --region $AWS_REGION

# Create frontend repo
aws ecr create-repository \
  --repository-name customer-ui \
  --image-scanning-configuration scanOnPush=true \
  --region $AWS_REGION
```

### Authenticate Docker to ECR

```bash
aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin \
  ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com
```

### Build and push images to ECR

```bash
# Backend
docker build -t customer-api ./backend
docker tag customer-api:latest \
  ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/customer-api:latest
docker push \
  ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/customer-api:latest

# Frontend
docker build -t customer-ui ./frontend
docker tag customer-ui:latest \
  ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/customer-ui:latest
docker push \
  ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/customer-ui:latest
```

---

## Step 6: IAM Roles

### ECS Task Execution Role (ECS agent uses this to pull images and write logs)

```bash
# Create trust policy
cat > /tmp/ecs-trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "ecs-tasks.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}
EOF

# Create execution role
aws iam create-role \
  --role-name ecsTaskExecutionRole-customer \
  --assume-role-policy-document file:///tmp/ecs-trust-policy.json

# Attach AWS-managed policy for ECR pull + CloudWatch logs
aws iam attach-role-policy \
  --role-name ecsTaskExecutionRole-customer \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

# Add Secrets Manager read permission
cat > /tmp/secrets-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": ["secretsmanager:GetSecretValue"],
    "Resource": "$SECRET_ARN"
  }]
}
EOF

aws iam put-role-policy \
  --role-name ecsTaskExecutionRole-customer \
  --policy-name SecretsManagerAccess \
  --policy-document file:///tmp/secrets-policy.json

EXEC_ROLE_ARN=$(aws iam get-role \
  --role-name ecsTaskExecutionRole-customer \
  --query 'Role.Arn' --output text)
echo "Execution Role ARN: $EXEC_ROLE_ARN"
```

### ECS Task Role (the app container uses this at runtime)

```bash
aws iam create-role \
  --role-name ecsTaskRole-customer \
  --assume-role-policy-document file:///tmp/ecs-trust-policy.json

TASK_ROLE_ARN=$(aws iam get-role \
  --role-name ecsTaskRole-customer \
  --query 'Role.Arn' --output text)
echo "Task Role ARN: $TASK_ROLE_ARN"
```

---

## Step 7: Cloud Map — Service Discovery

ECS uses Cloud Map so the frontend container can reach the backend container by DNS name (`backend.app.local`).

```bash
# Create private DNS namespace
NAMESPACE_ID=$(aws servicediscovery create-private-dns-namespace \
  --name app.local \
  --vpc $VPC_ID \
  --query 'OperationId' --output text)

# Wait and get namespace ID
sleep 10
NAMESPACE_ID=$(aws servicediscovery list-namespaces \
  --query "Namespaces[?Name=='app.local'].Id" --output text)
echo "Namespace ID: $NAMESPACE_ID"

# Create service discovery service for backend
DISCOVERY_SERVICE_ARN=$(aws servicediscovery create-service \
  --name backend \
  --namespace-id $NAMESPACE_ID \
  --dns-config "NamespaceId=$NAMESPACE_ID,DnsRecords=[{Type=A,TTL=10}]" \
  --health-check-custom-config FailureThreshold=1 \
  --query 'Service.Arn' --output text)
echo "Discovery Service ARN: $DISCOVERY_SERVICE_ARN"
```

After this, the backend ECS tasks will be reachable at `backend.app.local:5000` from within the VPC.

---

## Step 8: ECS Cluster

```bash
aws ecs create-cluster \
  --cluster-name customer-cluster \
  --capacity-providers FARGATE \
  --default-capacity-provider-strategy capacityProvider=FARGATE,weight=1 \
  --tags key=Name,value=customer-cluster
```

### Console alternative
- ECS → Clusters → Create cluster
- Cluster name: `customer-cluster`
- Infrastructure: AWS Fargate (serverless)

---

## Step 9: ECS Task Definitions

### Create CloudWatch Log Groups first

```bash
aws logs create-log-group --log-group-name /ecs/customer-backend
aws logs create-log-group --log-group-name /ecs/customer-frontend
```

### Backend Task Definition

```bash
cat > /tmp/backend-task-def.json << EOF
{
  "family": "customer-backend",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "executionRoleArn": "$EXEC_ROLE_ARN",
  "taskRoleArn": "$TASK_ROLE_ARN",
  "containerDefinitions": [
    {
      "name": "backend",
      "image": "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/customer-api:latest",
      "portMappings": [
        {"containerPort": 5000, "protocol": "tcp"}
      ],
      "environment": [
        {"name": "DB_HOST", "value": "$RDS_ENDPOINT"},
        {"name": "DB_USER", "value": "root"},
        {"name": "DB_NAME",  "value": "customerdb"}
      ],
      "secrets": [
        {"name": "DB_PASSWORD", "valueFrom": "${SECRET_ARN}:DB_PASSWORD::"}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/customer-backend",
          "awslogs-region": "$AWS_REGION",
          "awslogs-stream-prefix": "backend"
        }
      },
      "essential": true
    }
  ]
}
EOF

aws ecs register-task-definition --cli-input-json file:///tmp/backend-task-def.json
```

### Frontend Task Definition

> Before this step, update `frontend/nginx.conf` to use `backend.app.local` — see [Step 13](#step-13-nginxconf-update-for-ecs), rebuild, and push the image.

```bash
cat > /tmp/frontend-task-def.json << EOF
{
  "family": "customer-frontend",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "executionRoleArn": "$EXEC_ROLE_ARN",
  "taskRoleArn": "$TASK_ROLE_ARN",
  "containerDefinitions": [
    {
      "name": "frontend",
      "image": "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/customer-ui:latest",
      "portMappings": [
        {"containerPort": 80, "protocol": "tcp"}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/customer-frontend",
          "awslogs-region": "$AWS_REGION",
          "awslogs-stream-prefix": "frontend"
        }
      },
      "essential": true
    }
  ]
}
EOF

aws ecs register-task-definition --cli-input-json file:///tmp/frontend-task-def.json
```

### Console alternative
- ECS → Task definitions → Create new task definition
- Launch type: Fargate
- Task role: `ecsTaskRole-customer`
- Task execution role: `ecsTaskExecutionRole-customer`
- Add container: set image URI from ECR, port, environment variables
- For secrets: use "ValueFrom" pointing to Secrets Manager ARN

---

## Step 10: ECS Services

### Backend Service (private, no public IP, with Cloud Map)

```bash
DISCOVERY_SERVICE_ID=$(aws servicediscovery list-services \
  --query "Services[?Name=='backend'].Id" --output text)

aws ecs create-service \
  --cluster customer-cluster \
  --service-name customer-backend \
  --task-definition customer-backend \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$PRIV_SUBNET_1,$PRIV_SUBNET_2],securityGroups=[$BACKEND_SG],assignPublicIp=DISABLED}" \
  --service-registries "registryArn=$DISCOVERY_SERVICE_ARN" \
  --enable-execute-command
```

### Frontend Service (public, behind ALB)

> Create the ALB target group and ALB first (Step 11), then come back to create the frontend service with the `--load-balancers` flag.

```bash
# After Step 11 — replace TARGET_GROUP_ARN with your actual TG ARN
aws ecs create-service \
  --cluster customer-cluster \
  --service-name customer-frontend \
  --task-definition customer-frontend \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$PUB_SUBNET_1,$PUB_SUBNET_2],securityGroups=[$FRONTEND_SG],assignPublicIp=ENABLED}" \
  --load-balancers "targetGroupArn=TARGET_GROUP_ARN,containerName=frontend,containerPort=80" \
  --health-check-grace-period-seconds 60
```

---

## Step 11: Application Load Balancer

### Create ALB

```bash
ALB_ARN=$(aws elbv2 create-load-balancer \
  --name customer-alb \
  --subnets $PUB_SUBNET_1 $PUB_SUBNET_2 \
  --security-groups $ALB_SG \
  --scheme internet-facing \
  --type application \
  --query 'LoadBalancers[0].LoadBalancerArn' --output text)
echo "ALB ARN: $ALB_ARN"

ALB_DNS=$(aws elbv2 describe-load-balancers \
  --load-balancer-arns $ALB_ARN \
  --query 'LoadBalancers[0].DNSName' --output text)
echo "ALB DNS: $ALB_DNS"
```

### Create Target Group (for frontend ECS service)

```bash
TG_ARN=$(aws elbv2 create-target-group \
  --name customer-frontend-tg \
  --protocol HTTP \
  --port 80 \
  --vpc-id $VPC_ID \
  --target-type ip \
  --health-check-path / \
  --health-check-interval-seconds 30 \
  --healthy-threshold-count 2 \
  --unhealthy-threshold-count 3 \
  --query 'TargetGroups[0].TargetGroupArn' --output text)
echo "Target Group ARN: $TG_ARN"
```

### Create Listener

```bash
aws elbv2 create-listener \
  --load-balancer-arn $ALB_ARN \
  --protocol HTTP \
  --port 80 \
  --default-actions Type=forward,TargetGroupArn=$TG_ARN
```

> **Live URL:** `http://$ALB_DNS` — this is your app URL after deployment.

### Console alternative
- EC2 → Load Balancers → Create load balancer → Application Load Balancer
- Scheme: internet-facing, IP type: IPv4
- VPC: your VPC, select public subnets
- Security group: `alb-sg`
- Listener: HTTP:80
- Target group: new → IP type → port 80 → health check path `/`

---

## Step 12: Update CI/CD Workflows

### Updated CI workflow additions

Add these steps to `.github/workflows/ci.yml` in the `build-and-push` job, after the Docker Hub push:

```yaml
- name: Configure AWS credentials
  uses: aws-actions/configure-aws-credentials@v4
  with:
    aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
    aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
    aws-region: ${{ secrets.AWS_REGION }}

- name: Login to Amazon ECR
  id: login-ecr
  uses: aws-actions/amazon-ecr-login@v2

- name: Push backend image to ECR
  env:
    ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
  run: |
    docker tag pawarakash2511/customer-api:latest \
      $ECR_REGISTRY/customer-api:${{ github.sha }}
    docker tag pawarakash2511/customer-api:latest \
      $ECR_REGISTRY/customer-api:latest
    docker push $ECR_REGISTRY/customer-api:${{ github.sha }}
    docker push $ECR_REGISTRY/customer-api:latest

- name: Push frontend image to ECR
  env:
    ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
  run: |
    docker tag pawarakash2511/customer-ui:latest \
      $ECR_REGISTRY/customer-ui:${{ github.sha }}
    docker tag pawarakash2511/customer-ui:latest \
      $ECR_REGISTRY/customer-ui:latest
    docker push $ECR_REGISTRY/customer-ui:${{ github.sha }}
    docker push $ECR_REGISTRY/customer-ui:latest
```

### Updated CD workflow (replace SSH section)

Replace `.github/workflows/cd.yml` deploy step with:

```yaml
- name: Configure AWS credentials
  uses: aws-actions/configure-aws-credentials@v4
  with:
    aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
    aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
    aws-region: ${{ secrets.AWS_REGION }}

- name: Deploy backend to ECS
  run: |
    aws ecs update-service \
      --cluster customer-cluster \
      --service customer-backend \
      --force-new-deployment \
      --query 'service.serviceName' --output text

- name: Deploy frontend to ECS
  run: |
    aws ecs update-service \
      --cluster customer-cluster \
      --service customer-frontend \
      --force-new-deployment \
      --query 'service.serviceName' --output text

- name: Wait for backend deployment
  run: |
    aws ecs wait services-stable \
      --cluster customer-cluster \
      --services customer-backend

- name: Wait for frontend deployment
  run: |
    aws ecs wait services-stable \
      --cluster customer-cluster \
      --services customer-frontend

- name: Print live URL
  run: |
    ALB_DNS=$(aws elbv2 describe-load-balancers \
      --names customer-alb \
      --query 'LoadBalancers[0].DNSName' --output text)
    echo "============================================"
    echo "  Deployment complete — $(date)"
    echo "  Web URL: http://${ALB_DNS}"
    echo "============================================"
```

### New GitHub Secrets to add

Go to GitHub repo → Settings → Secrets and variables → Actions → New repository secret:

| Secret | Value |
|---|---|
| `AWS_ACCESS_KEY_ID` | IAM user access key ID |
| `AWS_SECRET_ACCESS_KEY` | IAM user secret access key |
| `AWS_REGION` | Your AWS region (e.g. `ap-south-1`) |

> Create an IAM user with policies: `AmazonECR_FullAccess`, `AmazonECS_FullAccess`, `ElasticLoadBalancingFullAccess`

---

## Step 13: nginx.conf Update for ECS

The current `frontend/nginx.conf` uses `backend` as the hostname (Docker Compose internal DNS). In ECS, Cloud Map provides `backend.app.local`.

Update `frontend/nginx.conf`:

```nginx
server {
    listen 80;

    location / {
        root /usr/share/nginx/html;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        # ECS Cloud Map DNS: backend.app.local
        # Local docker-compose DNS: backend
        proxy_pass http://backend.app.local:5000/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

> For local development, add `backend.app.local` to your hosts file, or use two separate nginx.conf files: `nginx.conf` (local) and `nginx.ecs.conf` (ECS, used in Dockerfile).

After updating, rebuild and push the frontend image to ECR before creating the ECS service.

---

## Verification

### Check ECS services are running

```bash
# Check service status
aws ecs describe-services \
  --cluster customer-cluster \
  --services customer-backend customer-frontend \
  --query 'services[*].{Name:serviceName,Running:runningCount,Desired:desiredCount,Status:status}'

# List running tasks
aws ecs list-tasks --cluster customer-cluster
```

### Check application health

```bash
# Get ALB DNS name
ALB_DNS=$(aws elbv2 describe-load-balancers \
  --names customer-alb \
  --query 'LoadBalancers[0].DNSName' --output text)

# Test frontend
curl -I http://$ALB_DNS

# Test API
curl -X POST http://$ALB_DNS/api/customers \
  -H "Content-Type: application/json" \
  -d '{"customer_id":"TEST001","customer_name":"Test User","gender":"Male","age":25,"some_number":10}'
```

### Check logs in CloudWatch

```bash
# View backend logs
aws logs tail /ecs/customer-backend --follow

# View frontend logs
aws logs tail /ecs/customer-frontend --follow
```

### Verify data in RDS

Connect to the backend ECS task using ECS Exec:

```bash
# Get a running task ARN
TASK_ARN=$(aws ecs list-tasks \
  --cluster customer-cluster \
  --service-name customer-backend \
  --query 'taskArns[0]' --output text)

# Open shell in the running container
aws ecs execute-command \
  --cluster customer-cluster \
  --task $TASK_ARN \
  --container backend \
  --command "/bin/sh" \
  --interactive

# Inside the container:
mysql -h $DB_HOST -u root -p$DB_PASSWORD customerdb -e "SELECT * FROM customers;"
```

---

## Cost Estimate

Approximate monthly costs (us-east-1 / ap-south-1 — varies by region):

| Service | Configuration | Estimated Monthly Cost |
|---|---|---|
| ECS Fargate — Backend | 0.25 vCPU, 0.5 GB, 1 task | ~$7–10 |
| ECS Fargate — Frontend | 0.25 vCPU, 0.5 GB, 1 task | ~$7–10 |
| RDS MySQL | db.t3.micro, 20 GB gp2, Single-AZ | ~$15–20 |
| ALB | 1 ALB, ~1 LCU/hour | ~$18–22 |
| NAT Gateway | 1 NAT GW + data transfer | ~$32–45 |
| ECR | 2 repos, ~1 GB storage | ~$0.10 |
| Secrets Manager | 1 secret | ~$0.40 |
| CloudWatch Logs | ~1 GB/month logs | ~$0.50 |
| **Total (approx)** | | **~$80–110/month** |

> **Cost-saving tips:**
> - Remove NAT Gateway and use VPC endpoints for ECR + Secrets Manager (saves ~$32/month)
> - Use RDS Single-AZ for dev/test
> - Use Fargate Spot for non-critical workloads (up to 70% cheaper)
> - Compared to EC2 t2.small ($17/month) + manual management, ECS+RDS costs more but gives you managed backups, auto-scaling, zero downtime deploys, and no ops overhead

---

## EC2 Docker Compose vs AWS Native

| Feature | EC2 + Docker Compose | ECR + ECS + RDS |
|---|---|---|
| Setup time | 1 hour | 3–4 hours |
| Monthly cost | ~$17 (t2.small) | ~$80–110 |
| Server management | You patch, monitor, restart | AWS manages it |
| Database backups | Manual | Automated (7-day default) |
| High availability | No (single instance) | Yes (Multi-AZ RDS + ECS across AZs) |
| Auto-scaling | No | Yes (ECS Auto Scaling) |
| Deployment | docker-compose + restart | Rolling update, zero downtime |
| Secrets | `.env` file on server | Secrets Manager (encrypted, audited) |
| Logs | Lost on container restart | CloudWatch (permanent, searchable) |
| HTTPS | Manual (certbot) | ALB + ACM (free SSL cert) |
| Image storage | Docker Hub (public) | ECR (private, same AWS account) |

---

## Troubleshooting

### Issue 1: ECS task keeps stopping immediately

**Check task logs:**
```bash
aws logs get-log-events \
  --log-group-name /ecs/customer-backend \
  --log-stream-name backend/backend/<TASK_ID>
```

**Common causes:**
- Wrong ECR image URI in task definition — verify the image exists: `aws ecr list-images --repository-name customer-api`
- DB connection fails — check `DB_HOST` env var matches RDS endpoint exactly
- Secret ARN wrong in task definition — verify: `aws secretsmanager get-secret-value --secret-id customer-app/db-password`

---

### Issue 2: ALB health check failing (service stuck)

**Check target group health:**
```bash
aws elbv2 describe-target-health \
  --target-group-arn $TG_ARN
```

**Common causes:**
- Frontend container not listening on port 80 — check Dockerfile `EXPOSE 80` and nginx config
- Security group blocking ALB → frontend — verify frontend SG allows port 80 from ALB SG
- Health check path wrong — Nginx must return 200 on `/`

---

### Issue 3: Frontend can't reach backend (`502 Bad Gateway`)

**Cause:** Nginx `proxy_pass` hostname not resolving.

**Check:**
- Cloud Map namespace `app.local` exists
- Backend ECS service has `serviceRegistries` configured
- Backend service is `ACTIVE` with `runningCount >= 1`
- Frontend SG allows outbound to backend SG on port 5000

```bash
# Check Cloud Map service instances
aws servicediscovery list-instances \
  --service-id $DISCOVERY_SERVICE_ID
```

---

### Issue 4: RDS connection refused from backend ECS task

**Check:**
- RDS SG inbound rule allows port 3306 from backend SG
- RDS endpoint in task definition matches actual RDS endpoint: `aws rds describe-db-instances --db-instance-identifier customer-mysql --query 'DBInstances[0].Endpoint.Address'`
- RDS is in `available` state: `aws rds describe-db-instances --db-instance-identifier customer-mysql --query 'DBInstances[0].DBInstanceStatus'`
- Backend ECS tasks are in private subnets (same VPC as RDS)

---

### Issue 5: ECS task can't pull image from ECR (`CannotPullContainerError`)

**Cause:** Private subnet tasks can't reach ECR without NAT Gateway or VPC endpoints.

**Fix option A:** Confirm NAT Gateway is in public subnet with Elastic IP and private route table routes `0.0.0.0/0` to NAT GW.

**Fix option B:** Create VPC endpoints for ECR (cheaper than NAT GW):
```bash
# ECR API endpoint
aws ec2 create-vpc-endpoint \
  --vpc-id $VPC_ID \
  --service-name com.amazonaws.${AWS_REGION}.ecr.api \
  --vpc-endpoint-type Interface \
  --subnet-ids $PRIV_SUBNET_1 $PRIV_SUBNET_2 \
  --security-group-ids $BACKEND_SG

# ECR Docker endpoint
aws ec2 create-vpc-endpoint \
  --vpc-id $VPC_ID \
  --service-name com.amazonaws.${AWS_REGION}.ecr.dkr \
  --vpc-endpoint-type Interface \
  --subnet-ids $PRIV_SUBNET_1 $PRIV_SUBNET_2 \
  --security-group-ids $BACKEND_SG

# S3 gateway endpoint (ECR uses S3 for image layers)
aws ec2 create-vpc-endpoint \
  --vpc-id $VPC_ID \
  --service-name com.amazonaws.${AWS_REGION}.s3 \
  --vpc-endpoint-type Gateway \
  --route-table-ids $PRIV_RT
```

---

### Issue 6: CD workflow fails — `aws: command not found`

The GitHub Actions runner already has AWS CLI v2 installed. If it fails, add this step:

```yaml
- name: Install AWS CLI
  run: |
    curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
    unzip awscliv2.zip
    sudo ./aws/install --update
```

---

### Issue 7: Secrets Manager value not injected into container

**Check:** Task definition `secrets` block uses the full ARN plus the JSON key suffix:

```json
"secrets": [
  {
    "name": "DB_PASSWORD",
    "valueFrom": "arn:aws:secretsmanager:REGION:ACCOUNT:secret:customer-app/db-password:DB_PASSWORD::"
  }
]
```

The format is `ARN:JSON_KEY::` (two trailing colons). If the secret is a plain string (not JSON), use just the ARN without a key suffix.

---

*Generated: 2026-06-04 | Stack: ECR + ECS Fargate + RDS MySQL 8.0 + ALB + Cloud Map + Secrets Manager*
