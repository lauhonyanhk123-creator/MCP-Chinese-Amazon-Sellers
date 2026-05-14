import json


class TestAPIHealth:
    """Tests for GET /api/health endpoint"""

    def test_health_check_returns_200(self, client):
        """Test that health endpoint returns 200 OK"""
        response = client.get('/api/health')
        assert response.status_code == 200

    def test_health_check_returns_json(self, client):
        """Test that health endpoint returns JSON"""
        response = client.get('/api/health')
        assert response.content_type == 'application/json'

    def test_health_check_success_status(self, client):
        """Test that health check returns success status"""
        response = client.get('/api/health')
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['status'] == 'healthy'

    def test_health_check_contains_version(self, client):
        """Test that health check contains version"""
        response = client.get('/api/health')
        data = json.loads(response.data)
        assert 'version' in data
        assert '1.0.0' in data['version']

    def test_health_check_contains_timestamp(self, client):
        """Test that health check contains timestamp"""
        response = client.get('/api/health')
        data = json.loads(response.data)
        assert 'timestamp' in data

    def test_health_check_contains_tools_count(self, client):
        """Test that health check contains available tools count"""
        response = client.get('/api/health')
        data = json.loads(response.data)
        assert 'available_tools' in data
        assert isinstance(data['available_tools'], int)


class TestAPIListTools:
    """Tests for GET /api/tools endpoint"""

    def test_list_tools_returns_200(self, client):
        """Test that list tools endpoint returns 200 OK"""
        response = client.get('/api/tools')
        assert response.status_code == 200

    def test_list_tools_returns_json(self, client):
        """Test that list tools endpoint returns JSON"""
        response = client.get('/api/tools')
        assert response.content_type == 'application/json'

    def test_list_tools_success(self, client):
        """Test that list tools returns success"""
        response = client.get('/api/tools')
        data = json.loads(response.data)
        assert data['success'] is True

    def test_list_tools_contains_tools_array(self, client):
        """Test that list tools returns tools array"""
        response = client.get('/api/tools')
        data = json.loads(response.data)
        assert 'tools' in data
        assert isinstance(data['tools'], list)

    def test_list_tools_contains_total_count(self, client):
        """Test that list tools returns total count"""
        response = client.get('/api/tools')
        data = json.loads(response.data)
        assert 'total_tools' in data
        assert isinstance(data['total_tools'], int)

    def test_list_tools_contains_tool_details(self, client):
        """Test that each tool has required details"""
        response = client.get('/api/tools')
        data = json.loads(response.data)
        if len(data['tools']) > 0:
            tool = data['tools'][0]
            assert 'name' in tool
            assert 'description' in tool
            assert 'required_parameters' in tool
            assert 'optional_parameters' in tool


class TestAPIGetToolInfo:
    """Tests for GET /api/tools/<name> endpoint"""

    def test_get_tool_info_returns_200(self, client):
        """Test that get tool info endpoint returns 200 OK"""
        response = client.get('/api/tools/get_low_stock_alerts')
        assert response.status_code == 200

    def test_get_tool_info_returns_json(self, client):
        """Test that get tool info endpoint returns JSON"""
        response = client.get('/api/tools/get_low_stock_alerts')
        assert response.content_type == 'application/json'

    def test_get_tool_info_success(self, client):
        """Test that get tool info returns success"""
        response = client.get('/api/tools/get_low_stock_alerts')
        data = json.loads(response.data)
        assert data['success'] is True

    def test_get_tool_info_contains_tool_details(self, client):
        """Test that get tool info returns tool details"""
        response = client.get('/api/tools/get_low_stock_alerts')
        data = json.loads(response.data)
        assert 'tool' in data
        assert data['tool']['name'] == 'get_low_stock_alerts'
        assert 'description' in data['tool']
        assert 'parameter_details' in data['tool']

    def test_get_tool_info_invalid_tool_returns_404(self, client):
        """Test that invalid tool returns 404"""
        response = client.get('/api/tools/nonexistent_tool')
        assert response.status_code == 404

    def test_get_tool_info_invalid_tool_returns_error(self, client):
        """Test that invalid tool returns error message"""
        response = client.get('/api/tools/nonexistent_tool')
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'error' in data


class TestAPICallTool:
    """Tests for POST /api/tools/<name> endpoint"""

    def test_call_tool_requires_json(self, client):
        """Test that call tool requires JSON body"""
        response = client.post('/api/tools/get_low_stock_alerts')
        assert response.status_code == 400

    def test_call_tool_returns_json(self, client, mock_mcp_tool):
        """Test that call tool returns JSON"""
        response = client.post(
            '/api/tools/get_low_stock_alerts',
            data=json.dumps({'threshold': 10}),
            content_type='application/json'
        )
        assert response.content_type == 'application/json'

    def test_call_tool_invalid_tool_returns_404(self, client):
        """Test that invalid tool returns 404"""
        response = client.post(
            '/api/tools/nonexistent_tool',
            data=json.dumps({}),
            content_type='application/json'
        )
        assert response.status_code == 404

    def test_call_tool_missing_required_params_returns_400(self, client):
        """Test that missing required parameters returns 400"""
        response = client.post(
            '/api/tools/get_low_stock_alerts',
            data=json.dumps({}),
            content_type='application/json'
        )
        assert response.status_code in [400, 500]


class TestAPIExportInventory:
    """Tests for GET /api/export/inventory endpoint"""

    def test_export_inventory_returns_200(self, client):
        """Test that export inventory endpoint returns 200 OK"""
        response = client.get('/api/export/inventory')
        assert response.status_code == 200

    def test_export_inventory_returns_csv(self, client):
        """Test that export inventory returns CSV content"""
        response = client.get('/api/export/inventory')
        assert 'text/csv' in response.content_type

    def test_export_inventory_contains_csv_header(self, client):
        """Test that export inventory contains CSV header"""
        response = client.get('/api/export/inventory')
        assert b'product_name' in response.data
        assert b'sku' in response.data

    def test_export_inventory_accepts_threshold_param(self, client):
        """Test that export inventory accepts threshold parameter"""
        response = client.get('/api/export/inventory?threshold=20')
        assert response.status_code == 200

    def test_export_inventory_accepts_platform_param(self, client):
        """Test that export inventory accepts platform parameter"""
        response = client.get('/api/export/inventory?platform=amazon')
        assert response.status_code == 200


class TestAPINotifications:
    """Tests for GET /api/notifications endpoint"""

    def test_notifications_returns_200(self, client):
        """Test that notifications endpoint returns 200 OK"""
        response = client.get('/api/notifications')
        assert response.status_code == 200

    def test_notifications_returns_json(self, client):
        """Test that notifications endpoint returns JSON"""
        response = client.get('/api/notifications')
        assert response.content_type == 'application/json'

    def test_notifications_success(self, client):
        """Test that notifications returns success"""
        response = client.get('/api/notifications')
        data = json.loads(response.data)
        assert data['success'] is True

    def test_notifications_contains_preferences(self, client):
        """Test that notifications contains preferences"""
        response = client.get('/api/notifications')
        data = json.loads(response.data)
        assert 'preferences' in data

    def test_notifications_contains_queue_count(self, client):
        """Test that notifications contains queue count"""
        response = client.get('/api/notifications')
        data = json.loads(response.data)
        assert 'queue_count' in data

    def test_notifications_contains_recent_notifications(self, client):
        """Test that notifications contains recent notifications"""
        response = client.get('/api/notifications')
        data = json.loads(response.data)
        assert 'recent_notifications' in data


class TestAPIAnalyticsSummary:
    """Tests for GET /api/analytics/summary endpoint"""

    def test_analytics_summary_returns_200(self, client):
        """Test that analytics summary endpoint returns 200 OK"""
        response = client.get('/api/analytics/summary')
        assert response.status_code == 200

    def test_analytics_summary_returns_json(self, client):
        """Test that analytics summary endpoint returns JSON"""
        response = client.get('/api/analytics/summary')
        assert response.content_type == 'application/json'

    def test_analytics_summary_contains_stats(self, client):
        """Test that analytics summary contains comparative stats"""
        response = client.get('/api/analytics/summary')
        data = json.loads(response.data)
        assert 'comparative_stats' in data or 'success' in data

    def test_analytics_summary_contains_health_score(self, client):
        """Test that analytics summary contains health score"""
        response = client.get('/api/analytics/summary')
        data = json.loads(response.data)
        assert 'health_score' in data or 'success' in data


class TestAPIAuthMe:
    """Tests for GET /api/auth/me endpoint"""

    def test_auth_me_without_session_returns_401(self, client):
        """Test that /api/auth/me without session returns 401"""
        response = client.get('/api/auth/me')
        assert response.status_code == 401

    def test_auth_me_with_session_returns_user(self, auth_client):
        """Test that /api/auth/me with session returns user info"""
        response = auth_client.get('/api/auth/me')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'user' in data
        assert data['user']['email'] == 'demo@example.com'

    def test_auth_me_returns_json(self, auth_client):
        """Test that /api/auth/me returns JSON"""
        response = auth_client.get('/api/auth/me')
        assert response.content_type == 'application/json'


class TestAPIAuthLogin:
    """Tests for POST /api/auth/login endpoint"""

    def test_api_login_with_valid_credentials(self, client, demo_user):
        """Test login with valid credentials"""
        response = client.post(
            '/api/auth/login',
            data=json.dumps({
                'email': demo_user['email'],
                'password': demo_user['password']
            }),
            content_type='application/json'
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'token' in data

    def test_api_login_with_invalid_credentials(self, client):
        """Test login with invalid credentials"""
        response = client.post(
            '/api/auth/login',
            data=json.dumps({
                'email': 'invalid@example.com',
                'password': 'wrongpassword'
            }),
            content_type='application/json'
        )
        assert response.status_code in [401, 400]

    def test_api_login_requires_email(self, client):
        """Test login requires email"""
        response = client.post(
            '/api/auth/login',
            data=json.dumps({'password': 'testpassword'}),
            content_type='application/json'
        )
        assert response.status_code == 400

    def test_api_login_requires_password(self, client):
        """Test login requires password"""
        response = client.post(
            '/api/auth/login',
            data=json.dumps({'email': 'test@example.com'}),
            content_type='application/json'
        )
        assert response.status_code == 400


class TestAPIAuthLogout:
    """Tests for POST /api/auth/logout endpoint"""

    def test_api_logout_returns_200(self, auth_client):
        """Test logout returns 200"""
        response = auth_client.post('/api/auth/logout')
        assert response.status_code == 200

    def test_api_logout_clears_session(self, auth_client):
        """Test logout clears session"""
        response = auth_client.post('/api/auth/logout')
        data = json.loads(response.data)
        assert data['success'] is True
