# Cross-Border Seller MCP Server - Deployment Guide

## Table of Contents

- [Quick Start](#quick-start)
- [Prerequisites](#prerequisites)
- [Local Development with Docker](#local-development-with-docker)
- [Production Deployment](#production-deployment)
- [Cloud Platform Deployment](#cloud-platform-deployment)
- [Configuration Reference](#configuration-reference)
- [Monitoring & Logging](#monitoring--logging)
- [Backup & Recovery](#backup--recovery)
- [Troubleshooting](#troubleshooting)

---

## Quick Start

### 1. Clone and Configure

```bash
git clone <repository-url>
cd crossborder_seller_mcp

# Copy environment template
cp .env.docker .env

# Edit .env with your configuration
nano .env
```

### 2. Start with Docker Compose

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Check service status
docker-compose ps
```

### 3. Access the Application

- **Web UI**: http://localhost:5000
- **Health Check**: http://localhost:5000/health
- **Demo Credentials**: admin/admin123, manager/manager123, viewer/viewer123

---

## Prerequisites

### Required Software

| Software | Version | Purpose |
|----------|---------|---------|
| Docker | 24.0+ | Container runtime |
| Docker Compose | 2.20+ | Service orchestration |
| Git | 2.0+ | Version control |

### Optional Software

| Software | Purpose |
|----------|---------|
| Docker Desktop | GUI for Docker management |
| Portainer | Web-based container management |
| Traefik | Advanced reverse proxy |

---

## Local Development with Docker

### Development Mode

```bash
# Start all services
docker-compose up -d

# Start with hot-reload (if supported)
docker-compose up

# Start specific services
docker-compose up -d web redis

# Scale workers for load testing
docker-compose up -d --scale worker=3
```

### Environment Variables

Copy `.env.docker` to `.env` and configure:

```bash
# Application
SECRET_KEY=your-secure-secret-key
APP_PORT=5000

# Database (SQLite default, PostgreSQL recommended for production)
DATABASE_URL=sqlite:///app/seller_data.db

# Redis
REDIS_URL=redis://redis:6379/0

# API Credentials (add your keys)
ALIBABA_APP_KEY=your_key
ALAZON_CLIENT_ID=your_id
```

### Accessing Services

| Service | URL | Credentials |
|---------|-----|-------------|
| Web App | http://localhost:5000 | admin/admin123 |
| Redis | localhost:6379 | - |
| Health Check | http://localhost:5000/health | - |

### Running Tests

```bash
# Run all tests
docker-compose exec web pytest tests/

# Run with coverage
docker-compose exec web pytest tests/ --cov=. --cov-report=html

# Run E2E tests
docker-compose exec web playwright test
```

---

## Production Deployment

### 1. Server Requirements

| Resource | Minimum | Recommended |
|----------|---------|------------|
| CPU | 2 cores | 4+ cores |
| RAM | 2 GB | 4+ GB |
| Disk | 20 GB | 50+ GB SSD |
| OS | Ubuntu 22.04 LTS | Ubuntu 22.04 LTS |

### 2. Server Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh

# Add current user to docker group
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verify installation
docker --version
docker-compose --version
```

### 3. Firewall Configuration

```bash
# Allow HTTP/HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Allow SSH
sudo ufw allow 22/tcp

# Enable firewall
sudo ufw enable
```

### 4. Deploy Application

```bash
# Clone repository
git clone <repository-url> /opt/crossborder-seller
cd /opt/crossborder-seller

# Create production environment
cp .env.docker .env
nano .env  # Configure all settings

# Create data directories
sudo mkdir -p /opt/crossborder-seller/data
sudo chown -R $USER:$USER /opt/crossborder-seller

# Start services
docker-compose -f docker-compose.yml up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f web
```

### 5. Reverse Proxy (Nginx + SSL)

```bash
# Install Nginx
sudo apt install nginx -y

# Copy configuration
sudo cp nginx.conf /etc/nginx/sites-available/crossborder
sudo ln -s /etc/nginx/sites-available/crossborder /etc/nginx/sites-enabled/

# Test and reload
sudo nginx -t
sudo systemctl reload nginx

# Install SSL (Let's Encrypt)
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d yourdomain.com
```

### 6. Systemd Service (Optional)

Create `/etc/systemd/system/crossborder.service`:

```ini
[Unit]
Description=Cross-Border Seller MCP Server
Requires=docker-compose.service
After=network-online.target docker.socket

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/crossborder-seller
ExecStart=/usr/local/bin/docker-compose up -d
ExecStop=/usr/local/bin/docker-compose down
TimeoutStartSec=0
User=root

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable crossborder
sudo systemctl start crossborder
sudo systemctl status crossborder
```

### 7. Update Procedure

```bash
cd /opt/crossborder-seller

# Pull latest changes
git pull origin main

# Rebuild and restart
docker-compose build web worker
docker-compose up -d

# View logs
docker-compose logs -f
```

---

## Cloud Platform Deployment

### AWS (Elastic Container Service)

#### 1. ECR Repository

```bash
# Create ECR repository
aws ecr create-repository --repository-name crossborder-seller

# Login to ECR
aws ecr get-login-password | docker login --username AWS --password-stdin <account>.dkr.ecr.<region>.amazonaws.com

# Build and push image
docker build -t crossborder-seller .
docker tag crossborder-seller:latest <account>.dkr.ecr.<region>.amazonaws.com/crossborder-seller:latest
docker push <account>.dkr.ecr.<region>.amazonaws.com/crossborder-seller:latest
```

#### 2. ECS Task Definition

```json
{
  "family": "crossborder-seller",
  "containerDefinitions": [
    {
      "name": "web",
      "image": "<account>.dkr.ecr.<region>.amazonaws.com/crossborder-seller:latest",
      "portMappings": [{"containerPort": 5000}],
      "environment": [],
      "essential": true,
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/crossborder-seller",
          "awslogs-region": "<region>",
          "awslogs-stream-prefix": "web"
        }
      }
    }
  ]
}
```

#### 3. ECS Service

```bash
# Register task definition
aws ecs register-task-definition --cli-input-json file://task-definition.json

# Create service
aws ecs create-service \
  --cluster crossborder-cluster \
  --service-name crossborder-web \
  --task-definition crossborder-seller \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx]}"
```

### Google Cloud Platform (Cloud Run)

```bash
# Build image
docker build -t gcr.io/<project>/crossborder-seller:latest .

# Push to Container Registry
docker push gcr.io/<project>/crossborder-seller:latest

# Deploy to Cloud Run
gcloud run deploy crossborder-seller \
  --image gcr.io/<project>/crossborder-seller:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --port 5000 \
  --memory 1Gi \
  --cpu 2
```

### Azure (Container Instances)

```bash
# Create Azure Container Registry
az acr create --resource-group myResourceGroup --name crossborderseller --sku Basic

# Login and push
az acr login --name crossborderseller
docker tag crossborder-seller crossborderseller.azurecr.io/crossborder-seller:latest
docker push crossborderseller.azurecr.io/crossborder-seller:latest

# Deploy
az container create \
  --resource-group myResourceGroup \
  --name crossborder-web \
  --image crossborderseller.azurecr.io/crossborder-seller:latest \
  --dns-name-label crossborder-demo \
  --ports 5000 \
  --environment-variables SECRET_KEY=xxx
```

---

## Configuration Reference

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | - | Flask secret key (required) |
| `DATABASE_URL` | sqlite:// | Database connection URL |
| `REDIS_URL` | redis://redis:6379/0 | Redis connection URL |
| `APP_PORT` | 5000 | Application port |
| `LICENSE_KEY` | - | License activation key |
| `ALIBABA_APP_KEY` | - | 1688 API key |
| `AMAZON_CLIENT_ID` | - | Amazon SP-API client ID |

### Docker Compose Profiles

```bash
# Default services (web + redis + worker)
docker-compose up -d

# Include scheduler (Celery Beat)
docker-compose --profile scheduler up -d

# Include PostgreSQL (production)
docker-compose --profile production up -d

# All services
docker-compose --profile scheduler --profile production up -d
```

### Resource Limits

Default limits in docker-compose.yml:

| Service | CPU Limit | Memory Limit |
|---------|-----------|--------------|
| web | 2 cores | 1 GB |
| worker | 1 core | 512 MB |
| redis | 0.5 cores | 256 MB |

---

## Monitoring & Logging

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f web
docker-compose logs -f worker

# Last 100 lines
docker-compose logs --tail=100

# Logs with timestamps
docker-compose logs -t
```

### Docker Stats

```bash
# Real-time resource usage
docker stats

# Specific containers
docker stats crossborder-web crossborder-worker
```

### Health Checks

```bash
# Check service health
curl http://localhost:5000/health

# Expected response:
{
  "status": "healthy",
  "service": "crossborder-seller",
  "checks": {
    "database": "ok",
    "redis": "ok"
  }
}
```

### Monitoring Tools

#### Prometheus Metrics (Future)

```yaml
# Add to docker-compose.yml
metrics:
  image: prom/prometheus:latest
  ports:
    - "9090:9090"
  volumes:
    - ./prometheus.yml:/etc/prometheus/prometheus.yml
```

#### Grafana Dashboard

```bash
docker-compose -f docker-compose.monitoring.yml up -d
```

---

## Backup & Recovery

### Database Backup

```bash
# SQLite backup
docker-compose exec web tar -czf /tmp/backup.tar.gz /app/*.db

# Copy backup to host
docker cp crossborder-web:/tmp/backup.tar.gz ./backups/

# PostgreSQL backup
docker-compose exec postgres pg_dump -U crossborder crossborder > backup.sql
```

### Automated Backups (Cron)

```bash
# Edit crontab
crontab -e

# Add backup job (daily at 2 AM)
0 2 * * * docker exec crossborder-web tar -czf /tmp/backup.tar.gz /app/*.db && docker cp crossborder-web:/tmp/backup.tar.gz /opt/backups/$(date +\%Y\%m\%d).tar.gz
```

### Restore from Backup

```bash
# Stop services
docker-compose down

# Restore SQLite
docker cp ./backups/backup.tar.gz crossborder-web:/tmp/
docker-compose exec web tar -xzf /tmp/backup.tar.gz -C /

# Start services
docker-compose up -d
```

---

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker-compose logs web

# Common issues:
# 1. Port already in use
docker-compose down
# Kill any process on the port
sudo lsof -ti:5000 | xargs kill -9

# 2. Missing environment variables
cp .env.docker .env

# 3. Docker build cache issues
docker-compose build --no-cache
```

### Health Check Fails

```bash
# Test endpoint manually
curl http://localhost:5000/health

# Check database connectivity
docker-compose exec web python -c "from database import get_db_connection; print('DB OK')"

# Check Redis connectivity
docker-compose exec web python -c "import redis; r = redis.from_url('redis://redis:6379'); print(r.ping())"
```

### Performance Issues

```bash
# Check resource usage
docker stats

# Increase worker count
docker-compose up -d --scale worker=4

# Clear Redis cache
docker-compose exec redis redis-cli FLUSHALL
```

### Database Migration Issues

```bash
# Check migrations folder
ls -la migrations/

# Run migrations manually
docker-compose exec web python migrations/run.py

# Reset database (WARNING: data loss)
docker-compose exec web rm /app/*.db
docker-compose restart web
```

### SSL Certificate Issues

```bash
# Renew Let's Encrypt
sudo certbot renew

# Check Nginx config
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx
```

---

## Security Checklist

- [ ] Change default SECRET_KEY
- [ ] Use strong passwords for PostgreSQL
- [ ] Enable SSL/TLS
- [ ] Configure firewall rules
- [ ] Regular backups
- [ ] Update Docker images regularly
- [ ] Use non-root user in containers
- [ ] Enable audit logging
- [ ] Review access logs regularly

---

## Support

For issues and deployment questions:
- GitHub Issues: https://github.com/your-repo/issues
- Documentation: https://docs.yourdomain.com
