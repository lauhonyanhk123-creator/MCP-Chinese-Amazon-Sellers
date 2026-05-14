function drawSparkline(canvasId, data, options = {}) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const width = options.width || 80;
    const height = options.height || 30;
    const color = options.color || '#6366f1';
    const fillColor = options.fillColor || 'rgba(99, 102, 241, 0.1)';

    canvas.width = width;
    canvas.height = height;

    if (!data || data.length === 0) {
        ctx.strokeStyle = '#e5e7eb';
        ctx.lineWidth = 1;
        ctx.setLineDash([3, 3]);
        ctx.beginPath();
        ctx.moveTo(0, height / 2);
        ctx.lineTo(width, height / 2);
        ctx.stroke();
        return;
    }

    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1;

    const padding = 2;
    const chartWidth = width - padding * 2;
    const chartHeight = height - padding * 2;

    const points = data.map((value, index) => ({
        x: padding + (index / (data.length - 1)) * chartWidth,
        y: padding + chartHeight - ((value - min) / range) * chartHeight
    }));

    ctx.beginPath();
    ctx.moveTo(points[0].x, points[0].y);
    for (let i = 1; i < points.length; i++) {
        ctx.lineTo(points[i].x, points[i].y);
    }
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.stroke();

    if (options.fill) {
        ctx.lineTo(points[points.length - 1].x, height);
        ctx.lineTo(points[0].x, height);
        ctx.closePath();
        ctx.fillStyle = fillColor;
        ctx.fill();
    }

    const lastPoint = points[points.length - 1];
    ctx.beginPath();
    ctx.arc(lastPoint.x, lastPoint.y, 2, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();
}

function initSparklines() {
    const sparklineConfigs = [
        { id: 'sparkline-low-stock', data: window.lowStockHistory, color: '#ef4444', higherIsBad: true },
        { id: 'sparkline-revenue', data: window.revenueHistory, color: '#22c55e', higherIsBad: false },
        { id: 'sparkline-reviews', data: window.reviewsHistory, color: '#f97316', higherIsBad: true },
        { id: 'sparkline-orders', data: window.ordersHistory, color: '#3b82f6', higherIsBad: true }
    ];

    sparklineConfigs.forEach(config => {
        if (config.data && Array.isArray(config.data)) {
            drawSparkline(config.id, config.data, {
                color: config.color,
                fill: true,
                width: 80,
                height: 30
            });
        }
    });
}

function showSkeletonLoader(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        element.classList.add('skeleton-loading');
    }
}

function hideSkeletonLoader(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        element.classList.remove('skeleton-loading');
    }
}

function initRelativeTimeUpdater() {
    setInterval(() => {
        const elements = document.querySelectorAll('[data-relative-time]');
        elements.forEach(el => {
            const timestamp = el.getAttribute('data-timestamp');
            if (timestamp) {
                el.textContent = getRelativeTime(timestamp);
            }
        });
    }, 60000);
}

function getRelativeTime(timestamp) {
    const now = new Date();
    const date = new Date(timestamp);
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${diffDays}d ago`;
}

document.addEventListener('DOMContentLoaded', function() {
    initSparklines();
    initRelativeTimeUpdater();
});
