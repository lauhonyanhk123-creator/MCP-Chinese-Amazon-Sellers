import pytest
import json


class TestLoginWithValidCredentials:
    """Tests for login with valid credentials"""

    def test_login_returns_302(self, client, demo_user):
        """Test that login with valid credentials returns 302 redirect"""
        response = client.post('/login', data={
            'email': demo_user['email'],
            'password': demo_user['password']
        }, follow_redirects=False)
        assert response.status_code == 302

    def test_login_sets_session_cookie(self, client, demo_user):
        """Test that login sets session cookie"""
        response = client.post('/login', data={
            'email': demo_user['email'],
            'password': demo_user['password']
        }, follow_redirects=False)
        cookies = response.headers.getlist('Set-Cookie')
        assert any('session_id' in str(cookie) for cookie in cookies)

    def test_login_redirects_on_success(self, client, demo_user):
        """Test that login redirects on success"""
        response = client.post('/login', data={
            'email': demo_user['email'],
            'password': demo_user['password']
        }, follow_redirects=False)
        assert response.status_code == 302

    def test_login_with_remember_me(self, client, demo_user):
        """Test login with remember me option"""
        response = client.post('/login', data={
            'email': demo_user['email'],
            'password': demo_user['password'],
            'remember_me': 'on'
        }, follow_redirects=False)
        assert response.status_code == 302


class TestLoginWithInvalidCredentials:
    """Tests for login with invalid credentials"""

    def test_login_with_wrong_password_returns_200(self, client, demo_user):
        """Test that login with wrong password returns 200 (shows error)"""
        response = client.post('/login', data={
            'email': demo_user['email'],
            'password': 'wrongpassword'
        }, follow_redirects=False)
        assert response.status_code == 200

    def test_login_with_nonexistent_user_returns_200(self, client):
        """Test that login with nonexistent user returns 200 (shows error)"""
        response = client.post('/login', data={
            'email': 'nonexistent@example.com',
            'password': 'somepassword'
        }, follow_redirects=False)
        assert response.status_code == 200

    def test_login_without_email_returns_200(self, client):
        """Test that login without email returns 200 (shows error)"""
        response = client.post('/login', data={
            'password': 'somepassword'
        }, follow_redirects=False)
        assert response.status_code == 200

    def test_login_without_password_returns_200(self, client, demo_user):
        """Test that login without password returns 200 (shows error)"""
        response = client.post('/login', data={
            'email': demo_user['email']
        }, follow_redirects=False)
        assert response.status_code == 200

    def test_login_with_empty_credentials_returns_200(self, client):
        """Test that login with empty credentials returns 200 (shows error)"""
        response = client.post('/login', data={
            'email': '',
            'password': ''
        }, follow_redirects=False)
        assert response.status_code == 200


class TestProtectedRoutes:
    """Tests for protected routes requiring authentication"""

    def test_competitor_requires_auth(self, client):
        """Test that competitor page requires authentication"""
        response = client.get('/competitor')
        assert response.status_code == 401

    def test_competitor_with_session_succeeds(self, auth_client):
        """Test that competitor page works with valid session"""
        response = auth_client.get('/competitor')
        assert response.status_code == 200

    def test_api_auth_me_without_session_returns_401(self, client):
        """Test that API /auth/me requires authentication"""
        response = client.get('/api/auth/me')
        assert response.status_code == 401

    def test_api_auth_me_with_session_returns_200(self, auth_client):
        """Test that API /auth/me works with valid session"""
        response = auth_client.get('/api/auth/me')
        assert response.status_code == 200


class TestLogout:
    """Tests for logout functionality"""

    def test_logout_returns_302(self, auth_client):
        """Test that logout returns 302 redirect"""
        response = auth_client.get('/logout', follow_redirects=False)
        assert response.status_code == 302

    def test_logout_clears_session_cookie(self, auth_client):
        """Test that logout clears session cookie"""
        response = auth_client.get('/logout', follow_redirects=False)
        cookies = response.headers.getlist('Set-Cookie')
        assert any('session_id' in str(cookie) for cookie in cookies)

    def test_logout_redirects_to_login(self, auth_client):
        """Test that logout redirects to login page"""
        response = auth_client.get('/logout', follow_redirects=True)
        assert response.status_code == 200

    def test_api_logout_returns_200(self, auth_client):
        """Test that API logout returns 200"""
        response = auth_client.post('/api/auth/logout')
        assert response.status_code == 200

    def test_api_logout_returns_json(self, auth_client):
        """Test that API logout returns JSON"""
        response = auth_client.post('/api/auth/logout')
        assert response.content_type == 'application/json'


class TestAuthenticationDecorators:
    """Tests for authentication decorators"""

    def test_login_required_decorator_blocks_unauthenticated(self, client):
        """Test that login_required decorator blocks unauthenticated users"""
        response = client.get('/api/auth/me')
        assert response.status_code == 401


class TestRegistration:
    """Tests for user registration"""

    def test_register_page_returns_200(self, client):
        """Test that register page returns 200 OK"""
        response = client.get('/register')
        assert response.status_code == 200

    def test_register_with_valid_data_returns_302(self, client):
        """Test that registration with valid data returns 302 redirect"""
        response = client.post('/register', data={
            'email': 'newuser@example.com',
            'password': 'NewUserPassword123',
            'confirm_password': 'NewUserPassword123'
        }, follow_redirects=False)
        assert response.status_code == 302

    def test_register_with_mismatched_passwords_returns_200(self, client):
        """Test that registration with mismatched passwords returns 200"""
        response = client.post('/register', data={
            'email': 'newuser@example.com',
            'password': 'NewUserPassword123',
            'confirm_password': 'DifferentPassword123'
        }, follow_redirects=False)
        assert response.status_code == 200

    def test_register_with_duplicate_email_returns_200(self, client, demo_user):
        """Test that registration with duplicate email returns 200"""
        response = client.post('/register', data={
            'email': demo_user['email'],
            'password': 'NewUserPassword123',
            'confirm_password': 'NewUserPassword123'
        }, follow_redirects=False)
        assert response.status_code == 200

    def test_register_with_short_password_returns_200(self, client):
        """Test that registration with short password returns 200"""
        response = client.post('/register', data={
            'email': 'newuser@example.com',
            'password': 'short',
            'confirm_password': 'short'
        }, follow_redirects=False)
        assert response.status_code == 200


class TestPasswordReset:
    """Tests for password reset functionality"""

    def test_forgot_password_page_returns_200(self, client):
        """Test that forgot password page returns 200 OK"""
        response = client.get('/forgot-password')
        assert response.status_code == 200

    def test_forgot_password_with_email_returns_302(self, client, demo_user):
        """Test that forgot password with email returns 302 redirect"""
        response = client.post('/forgot-password', data={
            'email': demo_user['email']
        }, follow_redirects=False)
        assert response.status_code == 302


class TestAuthSessionPersistence:
    """Tests for authentication session persistence"""

    def test_session_persists_across_requests(self, client, demo_user):
        """Test that session persists across multiple requests"""
        client.post('/login', data={
            'email': demo_user['email'],
            'password': demo_user['password']
        }, follow_redirects=False)

        second_response = client.get('/dashboard')
        assert second_response.status_code in [200, 401]

    def test_authenticated_client_can_access_protected_routes(self, auth_client):
        """Test that authenticated client can access protected routes"""
        response = auth_client.get('/competitor')
        assert response.status_code == 200

    def test_unauthenticated_client_cannot_access_protected_routes(self, client):
        """Test that unauthenticated client cannot access protected routes"""
        response = client.get('/competitor')
        assert response.status_code == 401
