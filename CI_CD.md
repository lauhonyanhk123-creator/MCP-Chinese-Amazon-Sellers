# CI/CD Pipeline Documentation

## Overview

This project uses GitHub Actions for continuous integration and deployment. The CI/CD pipeline consists of multiple workflows that run at different stages of development.

## Pipeline Status

| Workflow | Status | Description |
|----------|--------|-------------|
| Quick Check | ![Quick Check](https://github.com/YOUR_ORG/YOUR_REPO/actions/workflows/quick-check.yml/badge.svg) | Fast smoke tests on every push |
| CI Tests | ![CI Tests](https://github.com/YOUR_ORG/YOUR_REPO/actions/workflows/ci.yml/badge.svg) | Full test suite with coverage |
| Code Quality | ![Code Quality](https://github.com/YOUR_ORG/YOUR_REPO/actions/workflows/quality.yml/badge.svg) | Linting, formatting, and security |
| E2E Tests | ![E2E Tests](https://github.com/YOUR_ORG/YOUR_REPO/actions/workflows/e2e.yml/badge.svg) | Playwright end-to-end tests |

## Workflows

### 1. Quick Check (`quick-check.yml`)
- **Trigger**: Every push to main, master, or develop branches
- **Purpose**: Fast smoke tests to catch critical issues quickly
- **Duration**: < 2 minutes
- **Tools**: pytest, ruff

### 2. CI Tests (`ci.yml`)
- **Trigger**: Push and pull requests to main, master, or develop branches
- **Purpose**: Comprehensive test suite with coverage reporting
- **Python Versions**: 3.10, 3.11, 3.12
- **Coverage Threshold**: 70%
- **Tools**: pytest, pytest-cov, pytest-asyncio
- **Artifacts**: Coverage reports, test results

### 3. Code Quality (`quality.yml`)
- **Trigger**: Push and pull requests
- **Purpose**: Code quality enforcement
- **Tools**:
  - Ruff: Fast Python linter
  - Black: Code formatter
  - isort: Import sorter
  - Bandit: Security scanner

### 4. E2E Tests (`e2e.yml`)
- **Trigger**: Weekly schedule (Sundays 2 AM UTC) or manual dispatch
- **Purpose**: End-to-end browser testing with Playwright
- **Features**: Parallel test sharding, HTML reports
- **Timeout**: 30 minutes

## Adding Badges to Your README

Replace `YOUR_ORG/YOUR_REPO` with your actual GitHub organization and repository name:

```markdown
[![Quick Check](https://github.com/YOUR_ORG/YOUR_REPO/actions/workflows/quick-check.yml/badge.svg)](https://github.com/YOUR_ORG/YOUR_REPO/actions/workflows/quick-check.yml)
[![CI Tests](https://github.com/YOUR_ORG/YOUR_REPO/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_ORG/YOUR_REPO/actions/workflows/ci.yml)
[![Code Quality](https://github.com/YOUR_ORG/YOUR_REPO/actions/workflows/quality.yml/badge.svg)](https://github.com/YOUR_ORG/YOUR_REPO/actions/workflows/quality.yml)
[![E2E Tests](https://github.com/YOUR_ORG/YOUR_REPO/actions/workflows/e2e.yml/badge.svg)](https://github.com/YOUR_ORG/YOUR_REPO/actions/workflows/e2e.yml)
```

## Local Development

To run the same checks locally:

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
pytest test_server.py test_api.py test_routes.py -v --cov=.

# Run linting
ruff check .
black --check .
isort --check-only .

# Run security scan
bandit -r .

# Run E2E tests (requires server running)
playwright test
```

## Secrets Required

The following secrets should be configured in your GitHub repository:

- `CODECOV_TOKEN`: For uploading coverage reports to Codecov (optional)
- `PLAYWRIGHT_PASSWORD`: For Playwright authentication (optional)

## Troubleshooting

### Pipeline Fails on Coverage
- Ensure test coverage is above 70%
- Run `pytest --cov=. --cov-report=html` locally to check coverage

### Linting Errors
- Run `ruff check . --fix` to auto-fix many issues
- Run `black .` to auto-format code
- Run `isort .` to fix import ordering

### E2E Tests Timeout
- Increase the timeout in `e2e.yml`
- Check if the Flask server starts correctly
- Verify network connectivity
