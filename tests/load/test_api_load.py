"""
Load Testing Suite for Cross-Border Seller Web Application API.

Tests concurrent API requests, rate limiting behavior, and multiple users simulation.
Run with: pytest tests/load/test_api_load.py -v
"""

import asyncio
import concurrent.futures
import random
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from statistics import mean, median, stdev
import threading
import httpx

import pytest


BASE_URL = "http://localhost:5000"
TIMEOUT = 30.0


@dataclass
class RequestResult:
    """Stores the result of a single request."""
    endpoint: str
    status_code: int
    response_time_ms: float
    success: bool
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class LoadTestResults:
    """Aggregated results from load testing."""
    total_requests: int
    successful_requests: int
    failed_requests: int
    response_times: List[float]
    status_codes: Dict[int, int]
    duration_seconds: float

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return (self.successful_requests / self.total_requests) * 100

    @property
    def avg_response_time(self) -> float:
        return mean(self.response_times) if self.response_times else 0.0

    @property
    def median_response_time(self) -> float:
        return median(self.response_times) if self.response_times else 0.0

    @property
    def p95_response_time(self) -> float:
        if not self.response_times:
            return 0.0
        sorted_times = sorted(self.response_times)
        index = int(len(sorted_times) * 0.95)
        return sorted_times[min(index, len(sorted_times) - 1)]

    @property
    def p99_response_time(self) -> float:
        if not self.response_times:
            return 0.0
        sorted_times = sorted(self.response_times)
        index = int(len(sorted_times) * 0.99)
        return sorted_times[min(index, len(sorted_times) - 1)]

    @property
    def max_response_time(self) -> float:
        return max(self.response_times) if self.response_times else 0.0

    @property
    def min_response_time(self) -> float:
        return min(self.response_times) if self.response_times else 0.0

    @property
    def requests_per_second(self) -> float:
        if self.duration_seconds == 0:
            return 0.0
        return self.total_requests / self.duration_seconds


class HTTPClient:
    """Thread-safe HTTP client wrapper."""

    def __init__(self, base_url: str, timeout: float = 30.0):
        self.base_url = base_url
        self.timeout = timeout
        self._lock = threading.Lock()

    def get(self, endpoint: str) -> RequestResult:
        """Make a GET request and measure response time."""
        url = f"{self.base_url}{endpoint}"
        start_time = time.time()

        try:
            with self._lock:
                response = httpx.get(url, timeout=self.timeout)
            response_time = (time.time() - start_time) * 1000

            return RequestResult(
                endpoint=endpoint,
                status_code=response.status_code,
                response_time_ms=response_time,
                success=response.status_code < 400,
            )
        except httpx.TimeoutException as e:
            response_time = (time.time() - start_time) * 1000
            return RequestResult(
                endpoint=endpoint,
                status_code=0,
                response_time_ms=response_time,
                success=False,
                error=f"Timeout: {str(e)}"
            )
        except httpx.HTTPStatusError as e:
            response_time = (time.time() - start_time) * 1000
            return RequestResult(
                endpoint=endpoint,
                status_code=e.response.status_code,
                response_time_ms=response_time,
                success=False,
                error=f"HTTP {e.response.status_code}"
            )
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return RequestResult(
                endpoint=endpoint,
                status_code=0,
                response_time_ms=response_time,
                success=False,
                error=str(e)
            )


def run_concurrent_requests(
    client: HTTPClient,
    endpoint: str,
    num_requests: int,
    max_workers: int = 10
) -> LoadTestResults:
    """Run concurrent requests to an endpoint."""
    results: List[RequestResult] = []
    start_time = time.time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(client.get, endpoint) for _ in range(num_requests)]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())

    duration = time.time() - start_time

    return LoadTestResults(
        total_requests=len(results),
        successful_requests=sum(1 for r in results if r.success),
        failed_requests=sum(1 for r in results if not r.success),
        response_times=[r.response_time_ms for r in results],
        status_codes={r.status_code: results.count(r) for r in results},
        duration_seconds=duration
    )


def run_mixed_requests(
    client: HTTPClient,
    endpoints: List[str],
    num_requests: int,
    max_workers: int = 10
) -> LoadTestResults:
    """Run concurrent requests to multiple endpoints."""
    results: List[RequestResult] = []
    start_time = time.time()

    def get_random_endpoint():
        return random.choice(endpoints)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(client.get, get_random_endpoint()) for _ in range(num_requests)]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())

    duration = time.time() - start_time

    return LoadTestResults(
        total_requests=len(results),
        successful_requests=sum(1 for r in results if r.success),
        failed_requests=sum(1 for r in results if not r.success),
        response_times=[r.response_time_ms for r in results],
        status_codes={r.status_code: sum(1 for res in results if res.status_code == r.status_code) for r in results},
        duration_seconds=duration
    )


def simulate_user_sessions(
    client: HTTPClient,
    endpoints: List[str],
    num_users: int,
    requests_per_user: int,
    delay_range: tuple = (0.1, 0.5)
) -> LoadTestResults:
    """Simulate multiple users making sequential requests."""
    results: List[RequestResult] = []
    start_time = time.time()
    lock = threading.Lock()

    def user_session(user_id: int):
        for _ in range(requests_per_user):
            endpoint = random.choice(endpoints)
            result = client.get(endpoint)
            with lock:
                results.append(result)
            time.sleep(random.uniform(*delay_range))

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_users) as executor:
        futures = [executor.submit(user_session, i) for i in range(num_users)]
        concurrent.futures.wait(futures)

    duration = time.time() - start_time

    return LoadTestResults(
        total_requests=len(results),
        successful_requests=sum(1 for r in results if r.success),
        failed_requests=sum(1 for r in results if not r.success),
        response_times=[r.response_time_ms for r in results],
        status_codes={r.status_code: sum(1 for res in results if res.status_code == r.status_code) for r in results},
        duration_seconds=duration
    )


class TestHealthEndpoint:
    """Tests for the /api/health endpoint."""

    def test_health_endpoint_basic(self):
        """Test that health endpoint responds successfully."""
        client = HTTPClient(BASE_URL, TIMEOUT)
        result = client.get("/api/health")

        assert result.success, f"Health check failed: {result.error}"
        assert result.status_code == 200, f"Expected 200, got {result.status_code}"
        assert result.response_time_ms < 1000, f"Response too slow: {result.response_time_ms}ms"

    def test_health_endpoint_concurrent(self):
        """Test concurrent health check requests."""
        client = HTTPClient(BASE_URL, TIMEOUT)
        results = run_concurrent_requests(client, "/api/health", num_requests=50, max_workers=10)

        print(f"\n--- Health Endpoint Concurrent Test ---")
        print(f"Total requests: {results.total_requests}")
        print(f"Success rate: {results.success_rate:.1f}%")
        print(f"Avg response time: {results.avg_response_time:.2f}ms")
        print(f"P95 response time: {results.p95_response_time:.2f}ms")

        assert results.success_rate >= 95.0, f"Success rate too low: {results.success_rate:.1f}%"
        assert results.p95_response_time < 500, f"P95 too slow: {results.p95_response_time:.2f}ms"


class TestAPIEndpoints:
    """Tests for various API endpoints."""

    API_ENDPOINTS = [
        "/api/health",
        "/api/tools",
        "/api/analytics/summary",
        "/api/inventory/health",
        "/api/competitor/alerts",
        "/api/tasks",
    ]

    @pytest.mark.parametrize("endpoint", API_ENDPOINTS)
    def test_each_endpoint(self, endpoint):
        """Test each API endpoint individually."""
        client = HTTPClient(BASE_URL, TIMEOUT)
        result = client.get(endpoint)

        assert result.success, f"{endpoint} failed: {result.error}"
        assert result.status_code == 200, f"{endpoint} returned {result.status_code}"

    def test_all_endpoints_mixed(self):
        """Test all API endpoints with mixed requests."""
        client = HTTPClient(BASE_URL, TIMEOUT)
        results = run_mixed_requests(
            client,
            endpoints=self.API_ENDPOINTS,
            num_requests=100,
            max_workers=20
        )

        print(f"\n--- Mixed API Endpoints Test ---")
        print(f"Total requests: {results.total_requests}")
        print(f"Success rate: {results.success_rate:.1f}%")
        print(f"Avg response time: {results.avg_response_time:.2f}ms")
        print(f"P95 response time: {results.p95_response_time:.2f}ms")
        print(f"Requests/sec: {results.requests_per_second:.2f}")

        assert results.success_rate >= 90.0, f"Success rate too low: {results.success_rate:.1f}%"


class TestRateLimiting:
    """Tests for rate limiting behavior."""

    def test_rapid_requests_rate_limiting(self):
        """Test behavior under rapid requests (may hit rate limits)."""
        client = HTTPClient(BASE_URL, TIMEOUT)
        results = run_concurrent_requests(client, "/api/health", num_requests=200, max_workers=50)

        print(f"\n--- Rate Limiting Test ---")
        print(f"Total requests: {results.total_requests}")
        print(f"Status codes: {results.status_codes}")
        print(f"Success rate: {results.success_rate:.1f}%")
        print(f"429 (rate limited) responses: {results.status_codes.get(429, 0)}")

        rate_limited = results.status_codes.get(429, 0)
        assert rate_limited > 0, "Expected some rate limiting at high volume"

    def test_sustained_load(self):
        """Test sustained load over time."""
        client = HTTPClient(BASE_URL, TIMEOUT)
        endpoints = ["/api/health", "/api/tools", "/api/analytics/summary"]

        results = run_mixed_requests(
            client,
            endpoints=endpoints,
            num_requests=500,
            max_workers=25
        )

        print(f"\n--- Sustained Load Test ---")
        print(f"Duration: {results.duration_seconds:.2f}s")
        print(f"Total requests: {results.total_requests}")
        print(f"Success rate: {results.success_rate:.1f}%")
        print(f"Avg response time: {results.avg_response_time:.2f}ms")
        print(f"P95 response time: {results.p95_response_time:.2f}ms")
        print(f"Requests/sec: {results.requests_per_second:.2f}")

        assert results.success_rate >= 85.0, f"Success rate too low under sustained load: {results.success_rate:.1f}%"


class TestMultipleUsers:
    """Tests simulating multiple concurrent users."""

    def test_light_load_10_users(self):
        """Light load: 10 concurrent users."""
        client = HTTPClient(BASE_URL, TIMEOUT)
        endpoints = [
            "/", "/dashboard", "/inventory",
            "/api/health", "/api/tools", "/api/analytics/summary"
        ]

        results = simulate_user_sessions(
            client,
            endpoints=endpoints,
            num_users=10,
            requests_per_user=20,
            delay_range=(0.5, 1.5)
        )

        print(f"\n--- Light Load Test (10 users) ---")
        print(f"Total requests: {results.total_requests}")
        print(f"Success rate: {results.success_rate:.1f}%")
        print(f"Avg response time: {results.avg_response_time:.2f}ms")
        print(f"P95 response time: {results.p95_response_time:.2f}ms")
        print(f"Duration: {results.duration_seconds:.2f}s")

        assert results.success_rate >= 95.0, f"Light load success rate too low: {results.success_rate:.1f}%"

    def test_medium_load_50_users(self):
        """Medium load: 50 concurrent users."""
        client = HTTPClient(BASE_URL, TIMEOUT)
        endpoints = [
            "/", "/dashboard", "/inventory", "/analytics",
            "/api/health", "/api/tools", "/api/analytics/summary",
            "/api/inventory/health", "/api/competitor/alerts"
        ]

        results = simulate_user_sessions(
            client,
            endpoints=endpoints,
            num_users=50,
            requests_per_user=15,
            delay_range=(0.2, 0.8)
        )

        print(f"\n--- Medium Load Test (50 users) ---")
        print(f"Total requests: {results.total_requests}")
        print(f"Success rate: {results.success_rate:.1f}%")
        print(f"Avg response time: {results.avg_response_time:.2f}ms")
        print(f"P95 response time: {results.p95_response_time:.2f}ms")
        print(f"Requests/sec: {results.requests_per_second:.2f}")
        print(f"Duration: {results.duration_seconds:.2f}s")

        assert results.success_rate >= 90.0, f"Medium load success rate too low: {results.success_rate:.1f}%"
        assert results.p95_response_time < 2000, f"P95 too slow for medium load: {results.p95_response_time:.2f}ms"

    def test_heavy_load_100_users(self):
        """Heavy load: 100 concurrent users."""
        client = HTTPClient(BASE_URL, TIMEOUT)
        endpoints = [
            "/", "/dashboard", "/inventory", "/analytics",
            "/api/health", "/api/tools", "/api/analytics/summary",
            "/api/inventory/health", "/api/competitor/alerts", "/api/tasks"
        ]

        results = simulate_user_sessions(
            client,
            endpoints=endpoints,
            num_users=100,
            requests_per_user=10,
            delay_range=(0.1, 0.5)
        )

        print(f"\n--- Heavy Load Test (100 users) ---")
        print(f"Total requests: {results.total_requests}")
        print(f"Success rate: {results.success_rate:.1f}%")
        print(f"Avg response time: {results.avg_response_time:.2f}ms")
        print(f"P95 response time: {results.p95_response_time:.2f}ms")
        print(f"P99 response time: {results.p99_response_time:.2f}ms")
        print(f"Max response time: {results.max_response_time:.2f}ms")
        print(f"Requests/sec: {results.requests_per_second:.2f}")
        print(f"Duration: {results.duration_seconds:.2f}s")

        assert results.success_rate >= 80.0, f"Heavy load success rate too low: {results.success_rate:.1f}%"


class TestPerformanceMetrics:
    """Tests for performance metrics and thresholds."""

    def test_response_time_thresholds(self):
        """Test that response times meet defined thresholds."""
        client = HTTPClient(BASE_URL, TIMEOUT)
        endpoints = ["/api/health", "/api/tools", "/api/analytics/summary"]

        results = run_mixed_requests(client, endpoints, num_requests=100, max_workers=20)

        print(f"\n--- Performance Thresholds ---")
        print(f"Min response time: {results.min_response_time:.2f}ms")
        print(f"Avg response time: {results.avg_response_time:.2f}ms")
        print(f"Median response time: {results.median_response_time:.2f}ms")
        print(f"P95 response time: {results.p95_response_time:.2f}ms")
        print(f"P99 response time: {results.p99_response_time:.2f}ms")
        print(f"Max response time: {results.max_response_time:.2f}ms")

        assert results.avg_response_time < 500, f"Average response time exceeds 500ms: {results.avg_response_time:.2f}ms"
        assert results.p95_response_time < 1000, f"P95 response time exceeds 1000ms: {results.p95_response_time:.2f}ms"

    def test_throughput(self):
        """Test system throughput."""
        client = HTTPClient(BASE_URL, TIMEOUT)
        endpoints = ["/api/health", "/api/tools"]

        results = run_mixed_requests(client, endpoints, num_requests=200, max_workers=50)

        print(f"\n--- Throughput Test ---")
        print(f"Duration: {results.duration_seconds:.2f}s")
        print(f"Total requests: {results.total_requests}")
        print(f"Requests/sec: {results.requests_per_second:.2f}")

        assert results.requests_per_second > 10, f"Throughput too low: {results.requests_per_second:.2f} req/s"


class TestErrorHandling:
    """Tests for error handling and edge cases."""

    def test_invalid_endpoint(self):
        """Test handling of invalid endpoints."""
        client = HTTPClient(BASE_URL, TIMEOUT)
        result = client.get("/api/nonexistent/endpoint/12345")

        assert not result.success, "Invalid endpoint should return error"
        assert result.status_code == 404, f"Expected 404, got {result.status_code}"

    def test_invalid_sku(self):
        """Test handling of invalid SKU requests."""
        client = HTTPClient(BASE_URL, TIMEOUT)
        result = client.get("/api/inventory/reorder/INVALID-SKU-999")

        assert result.status_code in [200, 400, 404], f"Unexpected status: {result.status_code}"

    def test_sequential_vs_concurrent(self):
        """Compare sequential vs concurrent request performance."""
        client = HTTPClient(BASE_URL, TIMEOUT)
        endpoint = "/api/health"

        start = time.time()
        for _ in range(20):
            client.get(endpoint)
        sequential_time = time.time() - start

        results = run_concurrent_requests(client, endpoint, num_requests=20, max_workers=5)
        concurrent_time = results.duration_seconds

        print(f"\n--- Sequential vs Concurrent ---")
        print(f"Sequential time: {sequential_time:.2f}s")
        print(f"Concurrent time: {concurrent_time:.2f}s")
        print(f"Speedup: {sequential_time / concurrent_time:.2f}x")

        assert concurrent_time < sequential_time, "Concurrent should be faster than sequential"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
