"""
Locust Load Testing Configuration for Cross-Border Seller Web Application.

Usage:
    locust -f locustfile.py --host=http://localhost:5000

Load Test Scenarios:
    - Light load:  10 concurrent users
    - Medium load: 50 concurrent users
    - Heavy load: 100 concurrent users
"""

import random
import time
from locust import HttpUser, task, between, events, stats
from locust.runners import MasterRunner, WorkerRunner


class WebUser(HttpUser):
    """
    Simulates a typical web user browsing the application.
    """
    wait_time = between(1, 3)

    def on_start(self):
        """Called when a simulated user starts."""
        self.username = f"loadtest_user_{random.randint(1000, 9999)}"

    @task(10)
    def view_homepage(self):
        """Browse the homepage - most common action."""
        self.client.get("/", name="Homepage")

    @task(5)
    def view_dashboard(self):
        """View the main dashboard."""
        self.client.get("/dashboard", name="Dashboard")

    @task(3)
    def view_inventory(self):
        """Browse the inventory page."""
        self.client.get("/inventory", name="Inventory")

    @task(3)
    def view_analytics(self):
        """View analytics page."""
        self.client.get("/analytics", name="Analytics")

    @task(2)
    def view_competitor(self):
        """View competitor analysis page."""
        self.client.get("/competitor", name="Competitor Analysis")

    @task(2)
    def view_reviews(self):
        """View product reviews page."""
        self.client.get("/reviews", name="Reviews")


class DashboardUser(HttpUser):
    """
    Simulates a user focused on dashboard operations.
    """
    wait_time = between(2, 5)

    @task(15)
    def load_dashboard(self):
        """Load dashboard page."""
        self.client.get("/dashboard", name="Dashboard Load")

    @task(10)
    def check_api_analytics_summary(self):
        """Check analytics summary via API."""
        self.client.get("/api/analytics/summary", name="API: Analytics Summary")

    @task(8)
    def check_api_health(self):
        """Check API health status."""
        self.client.get("/api/health", name="API: Health Check")

    @task(5)
    def check_inventory_health(self):
        """Check inventory health metrics."""
        self.client.get("/api/inventory/health", name="API: Inventory Health")

    @task(3)
    def load_full_dashboard(self):
        """Load full dashboard view."""
        self.client.get("/dashboard-full", name="Full Dashboard")


class APIUser(HttpUser):
    """
    Simulates API client making programmatic requests.
    """
    wait_time = between(0.5, 2)

    @task(20)
    def api_health_check(self):
        """Check API health - most frequent API call."""
        with self.client.get("/api/health", name="API Health", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 429:
                response.failure("Rate limited")
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(15)
    def api_get_tools(self):
        """Get available API tools."""
        self.client.get("/api/tools", name="API: Get Tools")

    @task(10)
    def api_analytics_summary(self):
        """Get analytics summary."""
        self.client.get("/api/analytics/summary", name="API: Analytics Summary")

    @task(10)
    def api_inventory_health(self):
        """Get inventory health status."""
        self.client.get("/api/inventory/health", name="API: Inventory Health")

    @task(8)
    def api_analytics_forecast(self):
        """Get analytics forecast."""
        self.client.get("/api/analytics/forecast", name="API: Analytics Forecast")

    @task(5)
    def api_competitor_alerts(self):
        """Get competitor alerts."""
        self.client.get("/api/competitor/alerts", name="API: Competitor Alerts")

    @task(5)
    def api_tasks_list(self):
        """List background tasks."""
        self.client.get("/api/tasks", name="API: List Tasks")

    @task(3)
    def api_history_sales(self):
        """Get sales history data."""
        self.client.get("/api/history/sales", name="API: Sales History")

    @task(3)
    def api_trends_revenue(self):
        """Get revenue trends."""
        self.client.get("/api/trends/revenue", name="API: Revenue Trends")


class HeavyAPIUser(HttpUser):
    """
    Simulates intensive API usage for stress testing.
    """
    wait_time = between(0.1, 0.5)

    @task(30)
    def rapid_health_checks(self):
        """Rapid health check calls for rate limiting tests."""
        self.client.get("/api/health", name="Rapid: Health Check")

    @task(20)
    def rapid_tools_list(self):
        """Rapid API tools listing."""
        self.client.get("/api/tools", name="Rapid: Tools List")

    @task(15)
    def rapid_analytics_summary(self):
        """Rapid analytics queries."""
        self.client.get("/api/analytics/summary", name="Rapid: Analytics")

    @task(10)
    def rapid_inventory_health(self):
        """Rapid inventory health checks."""
        self.client.get("/api/inventory/health", name="Rapid: Inventory Health")

    @task(10)
    def rapid_tasks_check(self):
        """Rapid task status checks."""
        self.client.get("/api/tasks", name="Rapid: Tasks Check")

    @task(5)
    def mixed_api_calls(self):
        """Mix of various API endpoints."""
        endpoints = [
            "/api/competitor/alerts",
            "/api/analytics/forecast",
            "/api/inventory/forecast",
        ]
        endpoint = random.choice(endpoints)
        self.client.get(endpoint, name=f"Rapid: {endpoint.split('/')[-1]}")


class APIPerformanceUser(HttpUser):
    """
    Dedicated user for measuring API response times.
    """
    wait_time = between(0.5, 1)

    def on_start(self):
        self.start_time = time.time()
        self.request_count = 0

    @task
    def measure_api_response_time(self):
        """Measure response time for API endpoints."""
        endpoints = [
            "/api/health",
            "/api/tools",
            "/api/analytics/summary",
            "/api/inventory/health",
            "/api/competitor/alerts",
        ]

        endpoint = random.choice(endpoints)
        start = time.time()
        with self.client.get(endpoint, name=f"Perf: {endpoint}") as response:
            elapsed = (time.time() - start) * 1000
            self.request_count += 1

            if elapsed > 1000:
                response.failure(f"Slow response: {elapsed:.2f}ms")
            elif response.status_code == 429:
                response.failure("Rate limited")
            elif response.status_code >= 500:
                response.failure(f"Server error: {response.status_code}")

    @task
    def measure_page_load_time(self):
        """Measure page load times."""
        pages = ["/", "/dashboard", "/inventory", "/analytics"]
        page = random.choice(pages)

        start = time.time()
        with self.client.get(page, name=f"Perf: {page} Page") as response:
            elapsed = (time.time() - start) * 1000

            if elapsed > 3000:
                response.failure(f"Slow page load: {elapsed:.2f}ms")


def print_stats_handler(request_type, name, response_time, response_length, exception, **kwargs):
    """Custom handler to log slow requests."""
    if response_time and response_time > 2000:
        print(f"SLOW REQUEST: {name} took {response_time:.2f}ms")


def on_request_success(request_type, name, response_time, response_length, **kwargs):
    """Track successful requests for metrics."""
    if response_time:
        stats.global_stats.log_request(request_type, name, response_time, response_length)


def on_request_failure(request_type, name, response_time, response_length, exception, **kwargs):
    """Track failed requests for metrics."""
    if response_time:
        stats.global_stats.log_request(request_type, name, response_time, response_length or 0)


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """Log all requests for debugging."""
    if exception:
        print(f"REQUEST FAILED: {name} - {str(exception)}")


@events.quitting.add_listener
def on_quitting(environment, **kwargs):
    """Print summary when test completes."""
    print("\n" + "="*60)
    print("LOAD TEST COMPLETE - SUMMARY")
    print("="*60)

    if environment.stats.total.fail_ratio > 0.1:
        print(f"⚠️  WARNING: High failure rate: {environment.stats.total.fail_ratio:.1%}")
    else:
        print(f"✓  Failure rate: {environment.stats.total.fail_ratio:.1%}")

    avg_response = environment.stats.total.avg_response_time
    if avg_response > 1000:
        print(f"⚠️  WARNING: High average response time: {avg_response:.2f}ms")
    else:
        print(f"✓  Average response time: {avg_response:.2f}ms")

    print(f"Total requests: {environment.stats.total.num_requests}")
    print(f"Total failures: {environment.stats.total.num_failures}")
    print("="*60)


stats.PERCENTILES_TO_CHART = [0.50, 0.75, 0.90, 0.95, 0.98, 0.99, 1.0]
