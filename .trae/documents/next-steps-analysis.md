# Comprehensive Testing Plan

## Summary

Add comprehensive testing infrastructure to ensure reliability and enable confident deployments:
- Pytest for API endpoint testing
- Playwright for E2E browser testing
- Load testing with Locust
- GitHub Actions CI/CD pipeline
- API contract validation

## Current State Analysis

### Existing Tests
- `test_server.py` - Unit tests for 19 MCP tools (mock data)
- `test_routes.py` - Basic route smoke tests
- `test_api.py` - Basic API tests

### Testing Gaps
- No pytest framework
- No E2E browser tests
- No load/performance tests
- No CI/CD pipeline
- No API contract validation
- No test coverage reporting

---

## Proposed Changes

### 1. Add Pytest Framework
**Files to Create:**
- `/workspace/tests/conftest.py` - Pytest fixtures and configuration
- `/workspace/tests/test_api_endpoints.py` - API endpoint tests
- `/workspace/tests/test_web_pages.py` - Web page render tests
- `/workspace/tests/test_auth.py` - Authentication tests
- `/workspace/tests/test_notifications.py` - Notification tests

**Files to Modify:**
- `/workspace/requirements.txt` - Add pytest dependencies
- `/workspace/pytest.ini` - Pytest configuration

**Why:**
- Standard Python testing framework
- Better assertions and fixtures
- Test discovery and organization
- Coverage reporting

---

### 2. Add Playwright E2E Tests
**Files to Create:**
- `/workspace/tests/e2e/conftest.py` - Playwright configuration
- `/workspace/tests/e2e/test_login.py` - Login flow tests
- `/workspace/tests/e2e/test_dashboard.py` - Dashboard tests
- `/workspace/tests/e2e/test_navigation.py` - Navigation tests
- `/workspace/playwright.config.js` - Playwright config

**Files to Modify:**
- `/workspace/requirements.txt` - Add playwright dependency
- `/workspace/package.json` (create if needed) - Playwright CLI

**Why:**
- Real browser testing
- Catches UI regressions
- Tests actual user flows
- Mobile responsiveness testing

---

### 3. Add Load Testing with Locust
**Files to Create:**
- `/workspace/locustfile.py` - Load test scenarios
- `/workspace/tests/load/test_api_load.py` - API load tests

**Files to Modify:**
- `/workspace/requirements.txt` - Add locust dependency

**Why:**
- Identifies performance bottlenecks
- Validates scalability
- Tests concurrent user scenarios
- Prevents production issues

---

### 4. Add GitHub Actions CI/CD
**Files to Create:**
- `/workspace/.github/workflows/ci.yml` - Main CI workflow
- `/workspace/.github/workflows/quality.yml` - Code quality checks
- `/workspace/.github/workflows/e2e.yml` - E2E test workflow

**Files to Modify:**
- `/workspace/requirements.txt` - Add CI dependencies (coverage)

**Why:**
- Automated testing on every commit
- Catches issues before merge
- Enforces code quality standards
- Faster feedback loop

---

### 5. Add API Contract Testing
**Files to Create:**
- `/workspace/tests/contracts/test_api_contracts.py` - API schema validation
- `/workspace/tests/contracts/schemas/` - OpenAPI schemas

**Files to Modify:**
- `/workspace/web_app.py` - Add OpenAPI schema generation

**Why:**
- Validates API responses match contracts
- Catches breaking changes early
- Documents API behavior
- Enables contract testing

---

## Task List

### Phase 1: Pytest Setup
- [ ] Create `tests/conftest.py` with Flask test client fixtures
- [ ] Create `tests/test_api_endpoints.py` with API tests
- [ ] Create `tests/test_web_pages.py` with page render tests
- [ ] Add pytest to `requirements.txt`
- [ ] Create `pytest.ini` configuration
- [ ] Run tests and verify

### Phase 2: Playwright Setup
- [ ] Install Playwright (`pip install playwright && playwright install chromium`)
- [ ] Create `tests/e2e/conftest.py` with browser fixtures
- [ ] Create `tests/e2e/test_login.py`
- [ ] Create `tests/e2e/test_dashboard.py`
- [ ] Create `tests/e2e/test_navigation.py`
- [ ] Create `playwright.config.js`
- [ ] Run E2E tests and verify

### Phase 3: Load Testing Setup
- [ ] Create `locustfile.py` with common scenarios
- [ ] Add locust to `requirements.txt`
- [ ] Document load testing commands
- [ ] Test with sample load

### Phase 4: CI/CD Pipeline
- [ ] Create `.github/workflows/ci.yml`
- [ ] Create `.github/workflows/quality.yml`
- [ ] Create `.github/workflows/e2e.yml` (optional, slower)
- [ ] Test workflow locally if possible
- [ ] Verify GitHub Actions run on push

### Phase 5: API Contract Testing
- [ ] Create OpenAPI schema for main endpoints
- [ ] Create `tests/contracts/test_api_contracts.py`
- [ ] Add contract tests to CI pipeline
- [ ] Verify contract validation works

---

## Dependencies to Add

```
# requirements.txt additions
pytest>=7.4.0
pytest-cov>=4.1.0
pytest-flask>=1.3.0
playwright>=1.40.0
locust>=2.18.0
httpx>=0.25.0  # For async API testing
```

---

## Verification Steps

1. **Pytest Tests:**
   ```bash
   pytest tests/ -v --cov=web_app --cov-report=html
   ```
   Expected: All tests pass, coverage report generated

2. **Playwright E2E Tests:**
   ```bash
   pytest tests/e2e/ -v --headed
   ```
   Expected: Browser opens, tests run, screenshots on failure

3. **Load Tests:**
   ```bash
   locust -f locustfile.py --headless -u 100 -r 10 --run-time 60s
   ```
   Expected: Load simulation runs, statistics reported

4. **CI Pipeline:**
   - Push to GitHub
   - Check Actions tab
   - Verify all checks pass

---

## Files Summary

| File | Action | Purpose |
|------|--------|---------|
| `tests/conftest.py` | Create | Pytest fixtures |
| `tests/test_api_endpoints.py` | Create | API tests |
| `tests/test_web_pages.py` | Create | Page tests |
| `tests/test_auth.py` | Create | Auth tests |
| `tests/e2e/conftest.py` | Create | Playwright config |
| `tests/e2e/test_login.py` | Create | Login E2E |
| `tests/e2e/test_dashboard.py` | Create | Dashboard E2E |
| `tests/e2e/test_navigation.py` | Create | Navigation E2E |
| `locustfile.py` | Create | Load tests |
| `pytest.ini` | Create | Pytest config |
| `playwright.config.js` | Create | Playwright config |
| `requirements.txt` | Modify | Add test deps |
| `.github/workflows/ci.yml` | Create | Main CI |
| `.github/workflows/quality.yml` | Create | Code quality |
| `.github/workflows/e2e.yml` | Create | E2E CI |

---

## Assumptions & Decisions

1. **Testing Scope:** Focus on critical user paths (login, dashboard, main features)
2. **Browser:** Use Chromium for Playwright (best support)
3. **CI Platform:** GitHub Actions (free, integrated)
4. **Test Environment:** Use Flask test client for fast tests, Playwright for real browser
5. **Load Testing:** Use Locust (Python-based, easy to maintain)
