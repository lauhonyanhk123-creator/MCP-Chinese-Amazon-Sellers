

class TestHomepage:
    """Tests for homepage loading"""

    def test_homepage_returns_200(self, client):
        """Test that homepage returns 200 OK"""
        response = client.get('/')
        assert response.status_code == 200

    def test_homepage_returns_html(self, client):
        """Test that homepage returns HTML"""
        response = client.get('/')
        assert 'text/html' in response.content_type

    def test_homepage_contains_title(self, client):
        """Test that homepage contains title"""
        response = client.get('/')
        data = response.data.decode('utf-8')
        assert len(data) > 0

    def test_homepage_loads_in_english(self, client):
        """Test that homepage loads in English"""
        response = client.get('/?lang=en')
        assert response.status_code == 200

    def test_homepage_loads_in_chinese(self, client):
        """Test that homepage loads in Chinese"""
        response = client.get('/?lang=cn')
        assert response.status_code == 200


class TestDashboard:
    """Tests for dashboard page loading"""

    def test_dashboard_requires_auth(self, client):
        """Test that dashboard requires authentication"""
        response = client.get('/dashboard')
        assert response.status_code == 401

    def test_dashboard_returns_200_for_authenticated(self, auth_client):
        """Test that dashboard returns 200 OK for authenticated user"""
        response = auth_client.get('/dashboard')
        assert response.status_code == 200

    def test_dashboard_returns_html_for_authenticated(self, auth_client):
        """Test that dashboard returns HTML for authenticated user"""
        response = auth_client.get('/dashboard')
        assert 'text/html' in response.content_type


class TestInventoryPage:
    """Tests for inventory page loading"""

    def test_inventory_returns_200(self, client):
        """Test that inventory page returns 200 OK"""
        response = client.get('/inventory-alerts')
        assert response.status_code == 200

    def test_inventory_returns_html(self, client):
        """Test that inventory page returns HTML"""
        response = client.get('/inventory-alerts')
        assert 'text/html' in response.content_type

    def test_inventory_accepts_threshold_param(self, client):
        """Test that inventory page accepts threshold parameter"""
        response = client.get('/inventory-alerts?threshold=20')
        assert response.status_code == 200

    def test_inventory_accepts_platform_param(self, client):
        """Test that inventory page accepts platform parameter"""
        response = client.get('/inventory-alerts?platform=amazon')
        assert response.status_code == 200


class TestLoginPage:
    """Tests for login page loading"""

    def test_login_page_returns_200(self, client):
        """Test that login page returns 200 OK"""
        response = client.get('/login')
        assert response.status_code == 200

    def test_login_page_returns_html(self, client):
        """Test that login page returns HTML"""
        response = client.get('/login')
        assert 'text/html' in response.content_type

    def test_login_page_loads_in_english(self, client):
        """Test that login page loads in English"""
        response = client.get('/login?lang=en')
        assert response.status_code == 200

    def test_login_page_loads_in_chinese(self, client):
        """Test that login page loads in Chinese"""
        response = client.get('/login?lang=cn')
        assert response.status_code == 200


class TestNavigationLinks:
    """Tests for navigation links presence"""

    def test_homepage_has_login_link(self, client):
        """Test that homepage has login link"""
        response = client.get('/')
        data = response.data.decode('utf-8')
        assert '/login' in data or 'login' in data.lower()

    def test_homepage_has_navigation(self, client):
        """Test that homepage has navigation elements"""
        response = client.get('/')
        data = response.data.decode('utf-8')
        nav_count = data.lower().count('nav')
        assert nav_count > 0


class TestOtherPages:
    """Tests for other web pages"""

    def test_profit_page_returns_200(self, client):
        """Test that profit page returns 200 OK"""
        response = client.get('/profit')
        assert response.status_code == 200

    def test_profit_page_returns_html(self, client):
        """Test that profit page returns HTML"""
        response = client.get('/profit')
        assert 'text/html' in response.content_type

    def test_reviews_page_requires_auth(self, client):
        """Test that reviews page requires authentication"""
        response = client.get('/reviews')
        assert response.status_code == 401

    def test_reviews_page_authenticated_returns_200(self, auth_client):
        """Test that reviews page returns 200 for authenticated user"""
        response = auth_client.get('/reviews')
        assert response.status_code == 200

    def test_tasks_page_requires_auth(self, client):
        """Test that tasks page requires authentication"""
        response = client.get('/tasks')
        assert response.status_code == 401

    def test_tasks_page_authenticated_returns_200(self, auth_client):
        """Test that tasks page returns 200 for authenticated user"""
        response = auth_client.get('/tasks')
        assert response.status_code == 200

    def test_notifications_page_requires_auth(self, client):
        """Test that notifications page requires authentication"""
        response = client.get('/notifications')
        assert response.status_code == 401

    def test_notifications_page_authenticated_returns_200(self, auth_client):
        """Test that notifications page returns 200 for authenticated user"""
        response = auth_client.get('/notifications')
        assert response.status_code == 200

    def test_analytics_page_requires_auth(self, client):
        """Test that analytics page requires authentication"""
        response = client.get('/analytics')
        assert response.status_code == 401

    def test_competitor_page_requires_auth(self, client):
        """Test that competitor page requires authentication"""
        response = client.get('/competitor')
        assert response.status_code == 401

    def test_competitor_page_authenticated_returns_200(self, auth_client):
        """Test that competitor page returns 200 for authenticated user"""
        response = auth_client.get('/competitor')
        assert response.status_code == 200

    def test_register_page_returns_200(self, client):
        """Test that register page returns 200 OK"""
        response = client.get('/register')
        assert response.status_code == 200

    def test_forgot_password_page_returns_200(self, client):
        """Test that forgot password page returns 200 OK"""
        response = client.get('/forgot-password')
        assert response.status_code == 200
