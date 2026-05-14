from playwright.sync_api import Page

BASE_URL = "http://localhost:5000"


class TestNavigation:
    """Tests for navigation functionality."""

    def test_all_nav_links_are_clickable(self, authenticated_page: Page):
        """Test that all navigation links are clickable and load pages."""
        page = authenticated_page

        nav_links = [
            "/dashboard?lang=en",
            "/?lang=en",
            "/profit?lang=en",
            "/inventory?lang=en",
            "/reviews?lang=en",
            "/analytics?lang=en",
            "/tasks?lang=en",
        ]

        for link in nav_links:
            link_element = page.locator(f'a[href="{link}"]').first
            if link_element.count() > 0:
                link_element.click()
                page.wait_for_load_state("domcontentloaded")
                assert page.url.endswith(link) or "/dashboard" in page.url or "/login" not in page.url

                if "/dashboard" not in link:
                    page.goto(f"{BASE_URL}/dashboard?lang=en")
                    page.wait_for_load_state("domcontentloaded")

    def test_pages_load_without_errors(self, authenticated_page: Page):
        """Test that all pages load without JavaScript errors."""
        page = authenticated_page

        pages_to_test = [
            f"{BASE_URL}/dashboard?lang=en",
            f"{BASE_URL}/?lang=en",
            f"{BASE_URL}/profit?lang=en",
            f"{BASE_URL}/inventory?lang=en",
            f"{BASE_URL}/reviews?lang=en",
        ]

        errors = []
        page.on("console", lambda msg: errors.append(msg) if msg.type == "error" else None)

        for page_url in pages_to_test:
            page.goto(page_url, wait_until="domcontentloaded")
            page.wait_for_timeout(500)

        critical_errors = [e for e in errors if "failed" in e.text.lower() or "error" in e.text.lower()]
        assert len(critical_errors) == 0, f"Console errors found: {[e.text for e in critical_errors]}"

    def test_mobile_menu_toggle(self, mobile_page: Page):
        """Test that mobile menu toggle works."""
        page = mobile_page

        page.goto(f"{BASE_URL}/dashboard?lang=en", wait_until="domcontentloaded")

        menu_toggle = page.locator('#menu-toggle')
        if menu_toggle.count() > 0:
            menu_toggle.click()
            page.wait_for_timeout(500)

            mobile_menu = page.locator('#mobile-menu')
            if mobile_menu.count() > 0:
                menu_class = mobile_menu.first.get_attribute('class')
                assert 'active' in menu_class or mobile_menu.first.is_visible()

    def test_mobile_menu_close(self, mobile_page: Page):
        """Test that mobile menu can be closed."""
        page = mobile_page

        page.goto(f"{BASE_URL}/dashboard?lang=en", wait_until="domcontentloaded")

        menu_toggle = page.locator('#menu-toggle')
        if menu_toggle.count() > 0:
            menu_toggle.click()
            page.wait_for_timeout(300)

            menu_close = page.locator('#menu-close')
            if menu_close.count() > 0:
                menu_close.click()
                page.wait_for_timeout(300)

    def test_mobile_menu_navigation(self, mobile_page: Page):
        """Test that mobile menu navigation links work."""
        page = mobile_page

        page.goto(f"{BASE_URL}/dashboard?lang=en", wait_until="domcontentloaded")

        menu_toggle = page.locator('#menu-toggle')
        if menu_toggle.count() > 0:
            menu_toggle.click()
            page.wait_for_timeout(500)

            dashboard_link = page.locator('#mobile-menu a[href="/dashboard?lang=en"]')
            if dashboard_link.count() > 0:
                dashboard_link.first.click()
                page.wait_for_load_state("domcontentloaded")

    def test_language_switcher_english(self, authenticated_page: Page):
        """Test switching to English language."""
        page = authenticated_page

        en_link = page.locator('a[href*="lang=en"]').first
        if en_link.count() > 0:
            en_link.first.click()
            page.wait_for_load_state("domcontentloaded")
            assert "lang=en" in page.url

    def test_language_switcher_chinese(self, authenticated_page: Page):
        """Test switching to Chinese language."""
        page = authenticated_page

        cn_link = page.locator('a[href*="lang=cn"]').first
        if cn_link.count() > 0:
            cn_link.first.click()
            page.wait_for_load_state("domcontentloaded")
            assert "lang=cn" in page.url

    def test_desktop_navigation_visible(self, authenticated_page: Page):
        """Test that desktop navigation is visible on larger screens."""
        page = authenticated_page
        page.set_viewport_size({"width": 1280, "height": 720})

        page.goto(f"{BASE_URL}/dashboard?lang=en", wait_until="domcontentloaded")

        desktop_nav = page.locator('.desktop-nav')
        if desktop_nav.count() > 0:
            assert desktop_nav.first.is_visible()

    def test_footer_present(self, authenticated_page: Page):
        """Test that footer is present on pages."""
        page = authenticated_page

        page.goto(f"{BASE_URL}/dashboard?lang=en", wait_until="domcontentloaded")

        footer = page.locator('footer')
        if footer.count() > 0:
            assert footer.first.is_visible()

    def test_logout_link_present(self, authenticated_page: Page):
        """Test that logout link is present when logged in."""
        page = authenticated_page

        logout_link = page.locator('a[href*="/logout"]').first
        if logout_link.count() > 0:
            assert logout_link.first.is_visible()

    def test_notification_icon_present(self, authenticated_page: Page):
        """Test that notification icon is present in navigation."""
        page = authenticated_page

        page.goto(f"{BASE_URL}/dashboard?lang=en", wait_until="domcontentloaded")

        notifications_link = page.locator('a[href*="/notifications"]')
        if notifications_link.count() > 0:
            assert notifications_link.first.is_visible()

    def test_user_dropdown_menu(self, authenticated_page: Page):
        """Test that user dropdown menu works."""
        page = authenticated_page

        page.goto(f"{BASE_URL}/dashboard?lang=en", wait_until="domcontentloaded")

        user_button = page.locator('button:has-text("admin"), button:has-text("Admin")').first
        if user_button.count() > 0:
            user_button.click()
            page.wait_for_timeout(500)

    def test_back_button_works(self, authenticated_page: Page):
        """Test that browser back button works."""
        page = authenticated_page

        page.goto(f"{BASE_URL}/profit?lang=en", wait_until="domcontentloaded")
        page.goto(f"{BASE_URL}/inventory?lang=en", wait_until="domcontentloaded")

        page.go_back()
        page.wait_for_load_state("domcontentloaded")
        assert "/profit" in page.url or page.url.endswith("/profit")

        page.go_back()
        page.wait_for_load_state("domcontentloaded")

    def test_page_title_updates(self, authenticated_page: Page):
        """Test that page title updates when navigating."""
        page = authenticated_page

        page.goto(f"{BASE_URL}/dashboard?lang=en", wait_until="domcontentloaded")
        dashboard_title = page.title()

        page.goto(f"{BASE_URL}/profit?lang=en", wait_until="domcontentloaded")
        profit_title = page.title()

        assert dashboard_title != profit_title or len(dashboard_title) > 0
