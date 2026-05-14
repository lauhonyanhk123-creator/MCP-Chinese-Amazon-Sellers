import os

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

BASE_URL = os.environ.get("BASE_URL", "http://localhost:5000")


@pytest.fixture(scope="session")
def browser():
    """Launch a browser instance for the test session."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture(scope="session")
def browser_context_args(browser: Browser):
    """Return default browser context arguments."""
    return {
        "viewport": {"width": 1280, "height": 720},
        "locale": "en-US",
        "permissions": [],
    }


@pytest.fixture(scope="function")
def context(browser: Browser, browser_context_args):
    """Create a new browser context for each test."""
    context = browser.new_context(**browser_context_args)
    yield context
    context.close()


@pytest.fixture(scope="function")
def page(context: BrowserContext):
    """Create a new page for each test."""
    page = context.new_page()
    yield page
    page.close()


@pytest.fixture(scope="function")
def authenticated_page(context: BrowserContext, page: Page):
    """Create an authenticated page by logging in with demo credentials."""
    page.goto(f"{BASE_URL}/login?lang=en")
    page.fill('input[name="username"]', "admin")
    page.fill('input[name="password"]', "admin123")
    page.click('button[type="submit"]')
    page.wait_for_url(f"{BASE_URL}/dashboard**", wait_until="networkidle")
    yield page


@pytest.fixture(scope="function")
def screenshot_on_failure(request, page: Page):
    """Take a screenshot when a test fails."""
    yield
    if request.node.rep_call.failed if hasattr(request.node, 'rep_call') else request.node.rep_setup_failed if hasattr(request.node, 'rep_setup_failed') else False:
        screenshot_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "screenshots")
        os.makedirs(screenshot_dir, exist_ok=True)
        screenshot_path = os.path.join(screenshot_dir, f"{request.node.name}.png")
        try:
            page.screenshot(path=screenshot_path, full_page=True)
        except Exception as e:
            print(f"Failed to take screenshot: {e}")


def pytest_runtest_makereport(item, call):
    """Hook to capture test results for screenshot-on-failure."""
    if hasattr(call, 'excinfo') and call.excinfo is not None:
        if not hasattr(item, 'rep_call'):
            item.rep_call = type('obj', (object,), {'failed': False})()
        item.rep_call.failed = True


@pytest.fixture(scope="function")
def mobile_context(browser: Browser):
    """Create a mobile browser context."""
    mobile_context = browser.new_context(
        viewport={"width": 375, "height": 667},
        locale="en-US",
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15"
    )
    yield mobile_context
    mobile_context.close()


@pytest.fixture(scope="function")
def mobile_page(mobile_context):
    """Create a new mobile page for each test."""
    page = mobile_context.new_page()
    yield page
    page.close()


def navigate_to(page: Page, path: str, wait_until: str = "domcontentloaded"):
    """Helper function to navigate to a URL."""
    url = f"{BASE_URL}{path}" if path.startswith("/") else f"{BASE_URL}/{path}"
    page.goto(url, wait_until=wait_until)
    return page


def wait_for_element(page: Page, selector: str, timeout: int = 5000):
    """Helper function to wait for an element."""
    return page.wait_for_selector(selector, timeout=timeout)


def get_error_message(page: Page):
    """Helper function to get error messages from the page."""
    error_elements = page.query_selector_all('[class*="error"], .bg-red-100, [class*="alert"]')
    for elem in error_elements:
        if elem.is_visible():
            return elem.text_content()
    return None
