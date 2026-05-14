# Plan: Containerization & Production Deployment

## Summary

Containerize the Cross-Border Seller MCP Server with Docker, Docker Compose orchestration for all services (Flask, Celery, Redis), and production deployment guides.

## Current State Analysis

**What exists:**
- Flask web application (web_app.py) with 79 routes
- MCP server (server.py) with 19 tools
- Celery background tasks with Redis broker
- PostgreSQL/SQLite database options
- Gunicorn production WSGI server
- GitHub Actions CI/CD pipelines
- Existing `start_prod.sh` shell script

**What's missing:**
- Docker containerization
- Docker Compose orchestration
- Multi-service deployment (web + worker + redis)
- Production deployment documentation
- Environment variable management for containers
- Health checks and monitoring
- Nginx reverse proxy configuration

## Proposed Changes

### 1. Create Dockerfile for Flask/MCP Application
**File:** `/workspace/Dockerfile`

**What:**
- Multi-stage build (builder + production)
- Python 3.12 slim base image
- Non-root user for security
- Gunicorn as production server
- Health check endpoint
- Install all dependencies from requirements.txt

**Why:**
- Standard containerization for production
- Multi-stage reduces image size from ~1.2GB to ~200MB

### 2. Create Dockerfile for Celery Worker
**File:** `/workspace/Dockerfile.worker`

**What:**
- Same base as main Dockerfile
- Entrypoint for Celery worker process
- CMD: `celery -A celery_app worker --loglevel=info`

**Why:**
- Separate container for background tasks
- Independent scaling
- Clean separation of concerns

### 3. Create Docker Compose Configuration
**File:** `/workspace/docker-compose.yml`

**What:**
- `web` service: Flask app with Gunicorn
- `worker` service: Celery worker
- `redis` service: Message broker
- `postgres` service: Production database (optional)
- Volumes for data persistence
- Networks for service communication
- Environment configuration

**Why:**
- Single command to run entire stack
- Development and production profiles
- Easy local testing

### 4. Create Production Nginx Configuration
**File:** `/workspace/nginx.conf`

**What:**
- Reverse proxy to Flask/Gunicorn
- Static file caching
- Gzip compression
- Security headers
- Rate limiting at nginx level
- WebSocket support for future

**Why:**
- Production-grade front-end proxy
- Offload SSL termination (can add certbot)
- Better static file handling

### 5. Create Environment Configuration
**File:** `/workspace/.env.docker`

**What:**
- Production-ready environment variables
- Redis connection settings
- Database URL for Postgres
- Secret key configuration
- Notification service placeholders

**Why:**
- Template for production deployment
- Document all required environment variables

### 6. Create Docker Entry Point Script
**File:** `/workspace/docker-entrypoint.sh`

**What:**
- Database initialization
- Wait for Redis/health checks
- Run migrations if needed
- Start services based on command

**Why:**
- Proper startup sequencing
- Graceful handling of dependencies

### 7. Create .dockerignore File
**File:** `/workspace/.dockerignore`

**What:**
- Exclude development files
- Exclude git, tests, docs
- Exclude __pycache__, .pytest_cache
- Only include production code

**Why:**
- Smaller image size
- Faster builds
- Security: don't include sensitive configs

### 8. Create Deployment Guide Documentation
**File:** `/workspace/DEPLOYMENT.md`

**What:**
- Docker installation guide
- Local development with Docker Compose
- Production deployment steps
- AWS/GCP/Azure deployment guides
- Docker Swarm or Kubernetes overview
- Monitoring and logging
- Backup strategies
- Troubleshooting common issues

**Why:**
- Comprehensive deployment documentation
- Reduce deployment friction

## Implementation Steps

### Phase 1: Core Docker Setup
1. Create Dockerfile with multi-stage build
2. Create .dockerignore
3. Create docker-entrypoint.sh
4. Test local Docker build

### Phase 2: Orchestration
5. Create docker-compose.yml with all services
6. Create Dockerfile.worker for Celery
7. Create .env.docker template
8. Test full stack with docker-compose up

### Phase 3: Production Ready
9. Create nginx.conf for reverse proxy
10. Create DEPLOYMENT.md documentation
11. Add health check endpoints to web_app.py
12. Test production deployment simulation

## Verification Steps

1. **Build image:** `docker build -t crossborder-seller .`
2. **Run stack:** `docker-compose up -d`
3. **Check health:** `curl http://localhost/health`
4. **View logs:** `docker-compose logs -f`
5. **Run tests:** `docker-compose exec web pytest tests/`
6. **Scale workers:** `docker-compose up -d --scale worker=3`

## Assumptions & Decisions

- **Base image:** python:3.12-slim (Debian-based, widely supported)
- **WSGI server:** Gunicorn with 4 workers (auto-adjusted based on CPU)
- **Broker:** Redis (already in requirements)
- **Database:** SQLite for dev, PostgreSQL recommended for prod
- **Health check:** HTTP endpoint at /health returning JSON status
- **Non-root user:** www-data for security in containers
- **Timezone:** UTC inside containers, configured via environment

## Estimated Impact

- **Image size:** ~200MB (multi-stage build)
- **Build time:** ~3-5 minutes
- **Startup time:** ~10-15 seconds
- **Deployment complexity:** Reduced significantly with Docker Compose
