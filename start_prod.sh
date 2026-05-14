#!/bin/bash

# Production start script for Cross-Border Seller Web UI
# Usage: ./start_prod.sh

# Configuration
PORT=${PORT:-5000}
WORKERS=${WORKERS:-4}
APP=${APP:-web_app:app}

echo "============================================================"
echo "🚀 Starting Cross-Border Seller Web UI (Production)"
echo "============================================================"
echo ""
echo "Configuration:"
echo "  - Port: $PORT"
echo "  - Workers: $WORKERS"
echo "  - App: $APP"
echo ""

# Check if gunicorn is installed
if ! command -v gunicorn &> /dev/null; then
    echo "❌ Gunicorn not found. Installing..."
    pip install gunicorn
fi

# Start the server
echo "Starting server..."
exec gunicorn \
    --workers $WORKERS \
    --bind 0.0.0.0:$PORT \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    $APP
