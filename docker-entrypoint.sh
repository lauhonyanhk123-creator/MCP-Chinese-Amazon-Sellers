#!/bin/bash
# =============================================================================
# Docker Entrypoint Script - Initialize and Start Services
# =============================================================================

set -e

# Configuration
REDIS_HOST=${REDIS_HOST:-redis}
REDIS_PORT=${REDIS_PORT:-6379}
DB_PATH=${DB_PATH:-/app/seller_data.db}
WAIT_TIMEOUT=${WAIT_TIMEOUT:-30}
WAIT_INTERVAL=${WAIT_INTERVAL:-2}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

wait_for_redis() {
    log_info "Waiting for Redis at ${REDIS_HOST}:${REDIS_PORT}..."

    local elapsed=0
    while [ $elapsed -lt $WAIT_TIMEOUT ]; do
        if redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping > /dev/null 2>&1; then
            log_info "Redis is ready!"
            return 0
        fi

        sleep $WAIT_INTERVAL
        elapsed=$((elapsed + WAIT_INTERVAL))
        echo -n "."
    done

    log_error "Redis connection timeout after ${WAIT_TIMEOUT}s"
    return 1
}

init_database() {
    log_info "Initializing database..."

    if [ ! -f "$DB_PATH" ]; then
        log_info "Creating new database at $DB_PATH"

        python3 -c "
import sys
sys.path.insert(0, '/app')
from database import init_db
init_db()
print('Database initialized successfully')
" || log_warn "Database initialization script not found, will be created on first access"
    else
        log_info "Database already exists at $DB_PATH"
    fi
}

check_dependencies() {
    log_info "Checking dependencies..."

    if command -v python3 > /dev/null 2>&1; then
        log_info "Python3: $(python3 --version)"
    else
        log_error "Python3 not found!"
        return 1
    fi

    if command -v pip > /dev/null 2>&1; then
        log_info "pip: $(pip --version | cut -d' ' -f1-2)"
    fi

    return 0
}

create_directories() {
    log_info "Creating necessary directories..."

    mkdir -p /app/logs /app/data /app/uploads 2>/dev/null || true

    if [ -d /app ]; then
        chmod 755 /app 2>/dev/null || true
    fi
}

# =============================================================================
# Main Execution
# =============================================================================

log_info "========================================"
log_info "Cross-Border Seller MCP Server"
log_info "Starting container initialization..."
log_info "========================================"

# Run initialization
create_directories
check_dependencies

# Only wait for Redis if using Celery/background tasks
if [ "${SKIP_REDIS_WAIT:-false}" != "true" ]; then
    wait_for_redis || log_warn "Redis not available, some features may not work"
fi

init_database

# Run database migrations if exists
if [ -f /app/migrations/run.py ]; then
    log_info "Running database migrations..."
    python /app/migrations/run.py || log_warn "Migration script failed or not configured"
fi

# Apply license if provided
if [ -n "${LICENSE_KEY}" ]; then
    log_info "Applying license key..."
    python3 -c "
import sys
sys.path.insert(0, '/app')
from license_manager import get_license_manager
lm = get_license_manager()
result = lm.activate_license('${LICENSE_KEY}')
print(f'License activation: {result.get(\"status\", \"unknown\")}')
" 2>/dev/null || true
fi

log_info "========================================"
log_info "Initialization complete!"
log_info "========================================"

# Execute the main command
exec "$@"
