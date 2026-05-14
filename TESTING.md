# Playwright E2E Testing Setup

## Overview

This directory contains end-to-end (E2E) tests for the web application using Playwright with Python API.

## Prerequisites

1. Python 3.8+
2. pip for installing Python dependencies
3. The web server running on localhost:5000 (or configured BASE_URL)

## Installation

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Playwright Browsers

Playwright requires browser binaries to be installed. Run:

```bash
playwright install
```

Or for specific browsers:

```bash
playwright install chromium
playwright install firefox
playwright install webkit
```

### 3. Verify Installation

```bash
playwright --version
```

## Running Tests

### Run All Tests

```bash
pytest tests/e2e/
```

### Run Specific Test File

```bash
pytest tests/e2e/test_login.py
pytest tests/e2e/test_dashboard.py
pytest tests/e2e/test_navigation.py
```

### Run with Verbose Output

```bash
pytest tests/e2e/ -v
pytest tests/e2e/ -v -s  # With print statements
```

### Run Tests Against Different Base URL

```bash
BASE_URL=http://localhost:5000 pytest tests/e2e/
```

### Run with Coverage

```bash
pytest tests/e2e/ --cov=. --cov-report=html
```

## Test Structure

### fixtures (conftest.py)

- `browser`: Session-scoped Chromium browser instance
- `context`: Function-scoped browser context with viewport configuration
- `page`: Function-scoped page for each test
- `authenticated_page`: Pre-authenticated page with admin credentials
- `mobile_context`: Mobile browser context (375x667 viewport)
- `mobile_page`: Mobile-optimized page for testing
- `screenshot_on_failure`: Automatic screenshot capture on test failure

### Test Files

1. **test_login.py**: Login page functionality tests
   - Login page loads correctly
   - Valid credentials authentication
   - Invalid credentials error handling
   - Form validation
   - Language switching

2. **test_dashboard.py**: Dashboard functionality tests
   - Dashboard loads after login
   - Metrics cards visibility
   - Navigation menu presence
   - Quick actions section
   - User info display

3. **test_navigation.py**: Navigation and menu tests
   - All navigation links clickable
   - Pages load without errors
   - Mobile menu toggle
   - Language switcher functionality
   - Browser back/forward navigation

## Configuration

### playwright.config.js

The Playwright configuration file (for reference) includes:

- **Browser support**: Chromium, Firefox, WebKit, Mobile Chrome, Mobile Safari
- **Timeouts**: 5s for actions, 30s for navigation
- **Screenshots**: Automatic on failure
- **Video**: Retained on failure
- **Trace**: First retry trace collection
- **Reporter**: HTML report and list output

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| BASE_URL | http://localhost:5000 | Application base URL |
| CI | - | Set to enable CI mode (headless, retries) |

## Demo Credentials

The application includes demo accounts for testing:

| Role | Username | Password |
|------|----------|----------|
| Admin | admin | admin123 |
| Manager | manager | manager123 |
| Viewer | viewer | viewer123 |

## Troubleshooting

### Server Not Running

If tests fail with connection errors, ensure the server is running:

```bash
python server.py
```

Or start it in the background:

```bash
nohup python server.py &
```

### Browser Installation Issues

If you encounter browser installation issues:

```bash
# Install with dependencies
playwright install --with-deps chromium

# Or install all browsers
playwright install --with-deps
```

### Debug Mode

To run tests in headed mode (visible browser):

```python
# Modify conftest.py to set headless=False
browser = p.chromium.launch(headless=False)
```

Or set via environment:

```bash
HEADLESS=false pytest tests/e2e/
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: E2E Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          playwright install chromium
      - name: Start server
        run: python server.py &
      - name: Wait for server
        run: sleep 5
      - name: Run tests
        env:
          CI: true
        run: pytest tests/e2e/
```

## Viewing Test Reports

After running tests:

```bash
# Open HTML report
open playwright-report/index.html

# View in terminal
cat test-results/...
```

## Common Test Commands

```bash
# Run specific test
pytest tests/e2e/test_login.py::TestLoginPage::test_login_with_valid_credentials

# Run tests matching pattern
pytest tests/e2e/ -k "login"

# Run tests by marker
pytest tests/e2e/ -m "smoke"

# Stop on first failure
pytest tests/e2e/ -x

# Run in parallel
pytest tests/e2e/ -n auto
```
