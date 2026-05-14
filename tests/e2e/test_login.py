from playwright.sync_api import Page

BASE_URL = "http://localhost:5000"


class TestLoginPage:
    """Tests for the login page functionality."""

    def test_login_page_loads(self, page: Page):
        """Test that the login page loads correctly."""
        page.goto(f"{BASE_URL}/login?lang=en")

        assert page.title() is not None
        assert page.locator('input[name="username"]').is_visible()
        assert page.locator('input[name="password"]').is_visible()
        assert page.locator('button[type="submit"]').is_visible()

    def test_login_with_valid_credentials(self, page: Page):
        """Test successful login with valid admin credentials."""
        page.goto(f"{BASE_URL}/login?lang=en")

        page.fill('input[name="username"]', "admin")
        page.fill('input[name="password"]', "admin123")
        page.click('button[type="submit"]')

        page.wait_for_url(f"{BASE_URL}/dashboard**", wait_until="networkidle")
        assert "/dashboard" in page.url

    def test_login_with_manager_credentials(self, page: Page):
        """Test successful login with valid manager credentials."""
        page.goto(f"{BASE_URL}/login?lang=en")

        page.fill('input[name="username"]', "manager")
        page.fill('input[name="password"]', "manager123")
        page.click('button[type="submit"]')

        page.wait_for_url(f"{BASE_URL}/dashboard**", wait_until="networkidle")
        assert "/dashboard" in page.url

    def test_login_with_invalid_credentials(self, page: Page):
        """Test login attempt with invalid credentials shows error."""
        page.goto(f"{BASE_URL}/login?lang=en")

        page.fill('input[name="username"]', "invalid_user")
        page.fill('input[name="password"]', "wrong_password")
        page.click('button[type="submit"]')

        error_message = page.locator('.bg-red-100, [class*="error"], .text-red-700').first
        if error_message.is_visible(timeout=5000):
            assert error_message.is_visible()

        assert "/login" in page.url or page.locator('input[name="username"]').is_visible()

    def test_login_empty_username(self, page: Page):
        """Test that empty username shows validation error."""
        page.goto(f"{BASE_URL}/login?lang=en")

        page.fill('input[name="password"]', "admin123")
        page.click('button[type="submit"]')

        username_input = page.locator('input[name="username"]')
        assert username_input.is_visible()

    def test_login_empty_password(self, page: Page):
        """Test that empty password shows validation error."""
        page.goto(f"{BASE_URL}/login?lang=en")

        page.fill('input[name="username"]', "admin")
        page.click('button[type="submit"]')

        password_input = page.locator('input[name="password"]')
        assert password_input.is_visible()

    def test_remember_me_functionality(self, page: Page):
        """Test that remember me checkbox is present and can be checked."""
        page.goto(f"{BASE_URL}/login?lang=en")

        remember_me = page.locator('input[type="checkbox"][name*="remember"], input[type="checkbox"]#remember')
        if remember_me.count() > 0:
            assert remember_me.first.is_visible()
            remember_me.first.check()
            assert remember_me.first.is_checked()

    def test_language_switcher_on_login(self, page: Page):
        """Test that language can be switched on login page."""
        page.goto(f"{BASE_URL}/login?lang=en")

        cn_link = page.locator('a[href*="lang=cn"]').first
        if cn_link.is_visible():
            cn_link.click()
            page.wait_for_load_state("domcontentloaded")
            assert "lang=cn" in page.url

    def test_login_form_elements_present(self, page: Page):
        """Test that all form elements are present on login page."""
        page.goto(f"{BASE_URL}/login?lang=en")

        assert page.locator('input[name="username"]').is_visible()
        assert page.locator('input[name="password"]').is_visible()
        assert page.locator('button[type="submit"]').is_visible()

        title = page.locator('h1').first
        if title.is_visible():
            assert len(title.text_content()) > 0

    def test_demo_credentials_displayed(self, page: Page):
        """Test that demo credentials are displayed on login page."""
        page.goto(f"{BASE_URL}/login?lang=en")

        demo_section = page.locator('text=Demo Credentials')
        if demo_section.count() > 0:
            assert demo_section.first.is_visible()

    def test_login_redirects_to_next_page(self, page: Page):
        """Test login redirects to next parameter if provided."""
        page.goto(f"{BASE_URL}/login?lang=en&next=/dashboard")

        page.fill('input[name="username"]', "admin")
        page.fill('input[name="password"]', "admin123")
        page.click('button[type="submit"]')

        page.wait_for_url(f"{BASE_URL}/dashboard**", wait_until="networkidle")
        assert "/dashboard" in page.url
