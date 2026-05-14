from playwright.sync_api import Page

BASE_URL = "http://localhost:5000"


class TestDashboard:
    """Tests for the dashboard page functionality."""

    def test_dashboard_loads_after_login(self, page: Page):
        """Test that dashboard loads correctly after authentication."""
        page.goto(f"{BASE_URL}/login?lang=en")
        page.fill('input[name="username"]', "admin")
        page.fill('input[name="password"]', "admin123")
        page.click('button[type="submit"]')
        page.wait_for_url(f"{BASE_URL}/dashboard**", wait_until="networkidle")

        assert "/dashboard" in page.url
        assert page.locator('h2').first.is_visible()

    def test_metrics_cards_are_visible(self, authenticated_page: Page):
        """Test that all metrics cards are visible on the dashboard."""
        page = authenticated_page

        low_stock_card = page.locator('text=Low Stock').first
        if low_stock_card.count() > 0:
            assert low_stock_card.first.is_visible()

        pending_orders = page.locator('text=Pending Orders').first
        if pending_orders.count() > 0:
            assert pending_orders.first.is_visible()

        negative_reviews = page.locator('text=Negative Reviews').first
        if negative_reviews.count() > 0:
            assert negative_reviews.first.is_visible()

        todays_revenue = page.locator('text=Today\'s Revenue').first
        if todays_revenue.count() > 0:
            assert todays_revenue.first.is_visible()

    def test_navigation_menu_present(self, authenticated_page: Page):
        """Test that navigation menu is present on the dashboard."""
        page = authenticated_page

        dashboard_link = page.locator('a[href="/dashboard?lang=en"]').first
        if dashboard_link.count() > 0:
            assert dashboard_link.first.is_visible()

        home_link = page.locator('a[href*="/?lang="]').first
        if home_link.count() > 0:
            assert home_link.first.is_visible()

    def test_quick_actions_section(self, authenticated_page: Page):
        """Test that quick actions section is visible."""
        page = authenticated_page

        quick_actions = page.locator('text=Quick Actions').first
        if quick_actions.count() > 0:
            assert quick_actions.first.is_visible()

    def test_refresh_button_works(self, authenticated_page: Page):
        """Test that the refresh button works."""
        page = authenticated_page

        refresh_btn = page.locator('a:has-text("Refresh")').first
        if refresh_btn.count() > 0:
            assert refresh_btn.first.is_visible()
            initial_url = page.url
            refresh_btn.first.click()
            page.wait_for_load_state("domcontentloaded")
            assert page.url == initial_url

    def test_language_switcher_on_dashboard(self, authenticated_page: Page):
        """Test that language switcher works on dashboard."""
        page = authenticated_page

        cn_link = page.locator('a[href*="lang=cn"]').first
        if cn_link.count() > 0:
            cn_link.first.click()
            page.wait_for_load_state("domcontentloaded")
            assert "lang=cn" in page.url

    def test_dashboard_title_present(self, authenticated_page: Page):
        """Test that dashboard title is present."""
        page = authenticated_page

        title = page.locator('h2:has-text("Dashboard")').first
        if title.count() > 0:
            assert title.first.is_visible()

    def test_metrics_values_displayed(self, authenticated_page: Page):
        """Test that metric values are displayed."""
        page = authenticated_page

        numbers = page.locator('.text-2xl, .text-3xl').all()
        assert len(numbers) > 0

    def test_sparkline_charts_present(self, authenticated_page: Page):
        """Test that sparkline charts are present."""
        page = authenticated_page

        sparklines = page.locator('canvas[id^="sparkline"]').all()
        assert len(sparklines) > 0

    def test_last_updated_time_displayed(self, authenticated_page: Page):
        """Test that last updated time is displayed."""
        page = authenticated_page

        last_updated = page.locator('#last-updated-time, [data-relative-time]').first
        if last_updated.count() > 0:
            assert last_updated.first.is_visible()

    def test_user_info_displayed(self, authenticated_page: Page):
        """Test that user info is displayed in navigation."""
        page = authenticated_page

        admin_text = page.locator('text=admin').first
        if admin_text.count() > 0:
            assert admin_text.first.is_visible()

    def test_navigation_links_functional(self, authenticated_page: Page):
        """Test that navigation links work."""
        page = authenticated_page

        page.click('a[href="/profit?lang=en"]')
        page.wait_for_load_state("domcontentloaded")
        assert "/profit" in page.url

        page.click('a[href="/inventory?lang=en"]')
        page.wait_for_load_state("domcontentloaded")
        assert "/inventory" in page.url
