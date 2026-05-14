"""
Load Testing Documentation
==========================

This document describes how to run load tests for the Cross-Border Seller
web application using Locust.

Prerequisites
------------
1. Install dependencies:
   pip install -r requirements.txt

2. Ensure the web application is running:
   python web_app.py
   (or your application's entry point on http://localhost:5000)


Running Locust Tests
--------------------

Basic Usage:
    locust -f locustfile.py --host=http://localhost:5000

Headless Mode (no web UI):
    locust -f locustfile.py --host=http://localhost:5000 \
           --headless -u 100 -r 10 -t 60s

Parameters:
    -f, --locustfile    Locust file path
    --host              Target host URL
    -u, --users         Peak number of concurrent users
    -r, --spawn-rate    Users to spawn per second
    -t, --run-time      Run time (e.g., "5m", "1h", "60s")
    --headless          Run without web UI
    --html FILE         Generate HTML report
    --csv FILE          Generate CSV stats

Load Test Scenarios
------------------

1. Light Load (10 concurrent users)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
   locust -f locustfile.py --host=http://localhost:5000 \
          --headless -u 10 -r 2 -t 2m

   Scenario: Normal day-to-day usage
   - 10 concurrent users
   - Gradual spawn rate of 2 users/second
   - Duration: 2 minutes

2. Medium Load (50 concurrent users)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
   locust -f locustfile.py --host=http://localhost:5000 \
          --headless -u 50 -r 5 -t 5m

   Scenario: Peak business hours
   - 50 concurrent users
   - Spawn rate of 5 users/second
   - Duration: 5 minutes

3. Heavy Load (100 concurrent users)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
   locust -f locustfile.py --host=http://localhost:5000 \
          --headless -u 100 -r 10 -t 10m

   Scenario: Flash sale or high traffic event
   - 100 concurrent users
   - Spawn rate of 10 users/second
   - Duration: 10 minutes


Generating Reports
-----------------

HTML Report:
    locust -f locustfile.py --host=http://localhost:5000 \
           --headless -u 50 -r 5 -t 60s --html report.html

CSV Report:
    locust -f locustfile.py --host=http://localhost:5000 \
           --headless -u 50 -r 5 -t 60s --csv stats

This generates:
    - stats.csv          Overall statistics
    - stats_history.csv   Statistics over time


Running with Distributed Mode
----------------------------

For distributed testing across multiple machines:

1. Start Master:
    locust -f locustfile.py --master

2. Start Workers (on other machines):
    locust -f locustfile.py --worker \
           --master-host=<master-ip>

3. Run test:
    locust -f locustfile.py --host=http://localhost:5000 \
           -u 500 -r 50 -t 10m --expect-workers 4


Pytest-based Load Tests
------------------------

Run pytest-based load tests:
    pytest tests/load/test_api_load.py -v

Run specific test:
    pytest tests/load/test_api_load.py::TestHealthEndpoint -v

Run with output:
    pytest tests/load/test_api_load.py -v -s


Interpreting Results
-------------------

Key Metrics:
- RPS (Requests Per Second): Throughput capacity
- 95th/99th Percentile: Expected response time for most users
- Failure Rate: Percentage of failed requests
- Average Response Time: Mean response time

Thresholds:
- Success Rate: >= 95% for light load, >= 85% for heavy load
- P95 Response Time: < 500ms for API endpoints
- P99 Response Time: < 2000ms for page loads

Failure Indicators:
- HTTP 429: Rate limiting triggered
- HTTP 500+: Server errors
- High timeout rate: System overloaded


User Classes (TaskSets)
------------------------

The locustfile.py includes these user classes:

1. WebUser
   - Simulates typical web browsing
   - Homepage, dashboard, inventory, analytics
   - Weight: 5

2. DashboardUser
   - Focused on dashboard operations
   - Dashboard loads, analytics, health checks
   - Weight: 3

3. APIUser
   - API client simulation
   - All /api/* endpoints
   - Weight: 5

4. HeavyAPIUser
   - Stress testing with rapid API calls
   - Rate limiting tests
   - Weight: 2

5. APIPerformanceUser
   - Response time measurement
   - Performance benchmarking
   - Weight: 1
"""
