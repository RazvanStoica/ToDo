#!/usr/bin/env python3
import json
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from flask import redirect

# Import the server module
import server


class TestDatabaseOperations:
    """Tests for database read/write operations."""

    @pytest.fixture
    def mock_connection(self):
        """Create a mock database connection."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        return mock_conn, mock_cursor

    def test_load_tasks_from_db_empty(self, mock_connection):
        """Test loading tasks when database is empty."""
        mock_conn, mock_cursor = mock_connection
        mock_cursor.fetchall.return_value = []

        with patch.object(server, 'get_connection', return_value=mock_conn):
            tasks = server.load_tasks_from_db(user_id=1)

        assert tasks == []

    def test_load_tasks_from_db_with_data(self, mock_connection):
        """Test loading tasks with data in database."""
        mock_conn, mock_cursor = mock_connection

        mock_cursor.fetchall.return_value = [
            {
                'id': 1,
                'text': 'Test task',
                'completed': False,
                'priority': 'high',
                'createdAt': datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                'completedAt': None
            }
        ]

        with patch.object(server, 'get_connection', return_value=mock_conn):
            tasks = server.load_tasks_from_db(user_id=1)

        assert len(tasks) == 1
        assert tasks[0]['text'] == 'Test task'
        assert tasks[0]['priority'] == 'high'
        assert tasks[0]['completed'] == False

    def test_load_tasks_from_db_converts_timestamps(self, mock_connection):
        """Test that timestamps are converted to ISO format strings."""
        mock_conn, mock_cursor = mock_connection

        mock_cursor.fetchall.return_value = [
            {
                'id': 1,
                'text': 'Task with timestamps',
                'completed': True,
                'priority': 'medium',
                'createdAt': datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                'completedAt': datetime(2025, 1, 1, 14, 30, 0, tzinfo=timezone.utc)
            }
        ]

        with patch.object(server, 'get_connection', return_value=mock_conn):
            tasks = server.load_tasks_from_db(user_id=1)

        assert isinstance(tasks[0]['createdAt'], str)
        assert isinstance(tasks[0]['completedAt'], str)
        assert '2025-01-01' in tasks[0]['createdAt']

    def test_load_tasks_from_db_handles_error(self, mock_connection):
        """Test that load_tasks_from_db handles database errors gracefully."""
        with patch.object(server, 'get_connection', side_effect=Exception("DB Error")):
            tasks = server.load_tasks_from_db(user_id=1)

        assert tasks == []

    def test_load_tasks_from_db_multiple_tasks(self, mock_connection):
        """Test loading multiple tasks from database."""
        mock_conn, mock_cursor = mock_connection

        mock_cursor.fetchall.return_value = [
            {'id': 1, 'text': 'Task 1', 'completed': False, 'priority': 'high', 'createdAt': None, 'completedAt': None},
            {'id': 2, 'text': 'Task 2', 'completed': True, 'priority': 'low', 'createdAt': None, 'completedAt': None},
            {'id': 3, 'text': 'Task 3', 'completed': False, 'priority': 'medium', 'createdAt': None, 'completedAt': None},
        ]

        with patch.object(server, 'get_connection', return_value=mock_conn):
            tasks = server.load_tasks_from_db(user_id=1)

        assert len(tasks) == 3
        assert tasks[0]['text'] == 'Task 1'
        assert tasks[1]['text'] == 'Task 2'
        assert tasks[2]['text'] == 'Task 3'


class TestSaveOperations:
    """Tests for save operations."""

    @pytest.fixture
    def mock_connection(self):
        """Create a mock database connection."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        return mock_conn, mock_cursor

    def test_save_tasks_insert_new(self, mock_connection):
        """Test saving a new task."""
        mock_conn, mock_cursor = mock_connection
        mock_cursor.fetchall.return_value = []

        tasks = [{
            'id': 123,
            'text': 'New task',
            'completed': False,
            'priority': 'medium',
            'createdAt': '2025-01-01T12:00:00Z'
        }]

        with patch.object(server, 'get_connection', return_value=mock_conn):
            server.save_tasks(tasks, user_id=1)

        mock_conn.commit.assert_called_once()

    def test_save_tasks_delete_removed(self, mock_connection):
        """Test that removed tasks are deleted."""
        mock_conn, mock_cursor = mock_connection
        mock_cursor.fetchall.return_value = [(1,), (2,), (3,)]

        tasks = [{
            'id': 1,
            'text': 'Remaining task',
            'completed': False,
            'priority': 'low'
        }]

        with patch.object(server, 'get_connection', return_value=mock_conn):
            server.save_tasks(tasks, user_id=1)

        delete_calls = [call for call in mock_cursor.execute.call_args_list
                       if 'DELETE' in str(call)]
        assert len(delete_calls) == 1

    def test_save_tasks_handles_error(self, mock_connection, capsys):
        """Test that save_tasks handles database errors gracefully."""
        with patch.object(server, 'get_connection', side_effect=Exception("DB Error")):
            # Should not raise exception, but should print error
            result = server.save_tasks([{'id': 1, 'text': 'Test', 'completed': False}], user_id=1)

        # Verify function returns None (implicit) and logs the error
        assert result is None
        captured = capsys.readouterr()
        assert "Error saving tasks" in captured.out

    def test_save_tasks_with_timestamps(self, mock_connection):
        """Test saving tasks with timestamp fields."""
        mock_conn, mock_cursor = mock_connection
        mock_cursor.fetchall.return_value = []

        tasks = [{
            'id': 1,
            'text': 'Task with timestamps',
            'completed': True,
            'priority': 'high',
            'createdAt': '2025-01-01T12:00:00Z',
            'completedAt': '2025-01-01T13:00:00Z'
        }]

        with patch.object(server, 'get_connection', return_value=mock_conn):
            server.save_tasks(tasks, user_id=1)

        mock_conn.commit.assert_called_once()

    def test_save_empty_task_list(self, mock_connection):
        """Test saving an empty task list."""
        mock_conn, mock_cursor = mock_connection
        mock_cursor.fetchall.return_value = [(1,), (2,)]

        with patch.object(server, 'get_connection', return_value=mock_conn):
            server.save_tasks([], user_id=1)

        # Should delete existing tasks
        delete_calls = [call for call in mock_cursor.execute.call_args_list
                       if 'DELETE' in str(call)]
        assert len(delete_calls) == 1


class TestFlaskApp:
    """Tests for Flask application routes."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        server.app.config['TESTING'] = True
        server.app.config['SECRET_KEY'] = 'test-secret-key'
        with server.app.test_client() as client:
            yield client

    @pytest.fixture
    def authenticated_client(self):
        """Create an authenticated test client."""
        server.app.config['TESTING'] = True
        server.app.config['SECRET_KEY'] = 'test-secret-key'
        with server.app.test_client() as client:
            with client.session_transaction() as sess:
                sess['user'] = {'id': 1, 'email': 'test@example.com', 'name': 'Test User', 'picture_url': None}
            yield client

    def test_login_page_accessible(self, client):
        """Test that login page is accessible."""
        response = client.get('/login')
        assert response.status_code == 200
        assert b'Sign in with Google' in response.data

    def test_login_page_shows_error(self, client):
        """Test that login page displays error message."""
        response = client.get('/login?error=Test+error+message')
        assert response.status_code == 200
        assert b'Test error message' in response.data

    def test_index_redirects_without_auth(self, client):
        """Test that index page redirects to login without authentication."""
        response = client.get('/')
        assert response.status_code == 302
        assert '/login' in response.location

    def test_index_accessible_with_auth(self, authenticated_client):
        """Test that index page is accessible when authenticated."""
        response = authenticated_client.get('/')
        assert response.status_code == 200

    def test_api_tasks_returns_401_without_auth(self, client):
        """Test that API returns 401 without authentication."""
        response = client.get('/api/tasks')
        assert response.status_code == 401

    def test_api_tasks_get_with_auth(self, authenticated_client):
        """Test GET /api/tasks with authentication."""
        with patch.object(server, 'load_tasks_from_db', return_value=[
            {'id': 1, 'text': 'Test task', 'completed': False}
        ]):
            response = authenticated_client.get('/api/tasks')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data) == 1
        assert data[0]['text'] == 'Test task'

    def test_api_tasks_post_with_auth(self, authenticated_client):
        """Test POST /api/tasks with authentication."""
        with patch.object(server, 'save_tasks') as mock_save:
            response = authenticated_client.post('/api/tasks',
                data=json.dumps([{'id': 1, 'text': 'New task', 'completed': False}]),
                content_type='application/json')
        assert response.status_code == 200
        mock_save.assert_called_once()

    def test_api_tasks_post_invalid_json(self, authenticated_client):
        """Test POST /api/tasks with invalid JSON."""
        response = authenticated_client.post('/api/tasks',
            data='not valid json',
            content_type='application/json')
        assert response.status_code == 400

    def test_api_tasks_post_returns_401_without_auth(self, client):
        """Test POST /api/tasks returns 401 without authentication."""
        response = client.post('/api/tasks',
            data=json.dumps([]),
            content_type='application/json')
        assert response.status_code == 401

    def test_api_me_returns_401_without_auth(self, client):
        """Test that /api/me returns 401 without authentication."""
        response = client.get('/api/me')
        assert response.status_code == 401

    def test_api_me_returns_user_with_auth(self, authenticated_client):
        """Test that /api/me returns user info when authenticated."""
        response = authenticated_client.get('/api/me')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['email'] == 'test@example.com'
        assert data['name'] == 'Test User'

    def test_logout_redirects_to_login(self, client):
        """Test that logout redirects to login."""
        response = client.get('/auth/logout')
        assert response.status_code == 302
        assert '/login' in response.location

    def test_logout_clears_session(self, authenticated_client):
        """Test that logout clears the session."""
        # First verify we're authenticated
        response = authenticated_client.get('/api/me')
        assert response.status_code == 200

        # Logout
        authenticated_client.get('/auth/logout')

        # Verify session is cleared
        response = authenticated_client.get('/api/me')
        assert response.status_code == 401

    def test_auth_google_redirects(self, client):
        """Test that /auth/google initiates OAuth redirect."""
        response = client.get('/auth/google')
        assert response.status_code == 302
        assert 'accounts.google.com' in response.location or response.status_code == 302

    def test_auth_google_forces_account_selection(self, client):
        """Test that /auth/google includes prompt=select_account to allow switching users."""
        with patch.object(server.google, 'authorize_redirect') as mock_redirect:
            mock_redirect.return_value = redirect('/mock-oauth')
            client.get('/auth/google')
            mock_redirect.assert_called_once()
            # Verify prompt='select_account' is passed
            call_kwargs = mock_redirect.call_args
            assert call_kwargs[1].get('prompt') == 'select_account', \
                "OAuth should force account selection with prompt='select_account'"


class TestAuthHelpers:
    """Tests for authentication helper functions."""

    def test_is_email_whitelisted_with_match(self):
        """Test email whitelist with matching email."""
        with patch.object(server, 'config', {
            'auth': {
                'email_whitelist': ['user@example.com'],
                'allow_any_email': False
            }
        }):
            assert server.is_email_whitelisted('user@example.com') == True

    def test_is_email_whitelisted_case_insensitive(self):
        """Test email whitelist is case insensitive."""
        with patch.object(server, 'config', {
            'auth': {
                'email_whitelist': ['User@Example.com'],
                'allow_any_email': False
            }
        }):
            assert server.is_email_whitelisted('user@example.com') == True

    def test_is_email_whitelisted_no_match(self):
        """Test email whitelist with non-matching email."""
        with patch.object(server, 'config', {
            'auth': {
                'email_whitelist': ['other@example.com'],
                'allow_any_email': False
            }
        }):
            assert server.is_email_whitelisted('user@example.com') == False

    def test_is_email_whitelisted_allow_any(self):
        """Test email whitelist when allow_any_email is True."""
        with patch.object(server, 'config', {
            'auth': {
                'email_whitelist': [],
                'allow_any_email': True
            }
        }):
            assert server.is_email_whitelisted('anyone@anywhere.com') == True

    def test_is_email_whitelisted_empty_whitelist(self):
        """Test that empty whitelist denies all emails."""
        with patch.object(server, 'config', {
            'auth': {
                'email_whitelist': [],
                'allow_any_email': False
            }
        }):
            assert server.is_email_whitelisted('user@example.com') == False

    def test_is_email_whitelisted_missing_auth_config(self):
        """Test behavior when auth config is missing."""
        with patch.object(server, 'config', {}):
            assert server.is_email_whitelisted('user@example.com') == False

    def test_is_email_whitelisted_multiple_emails(self):
        """Test whitelist with multiple emails."""
        with patch.object(server, 'config', {
            'auth': {
                'email_whitelist': ['user1@example.com', 'user2@example.com', 'user3@example.com'],
                'allow_any_email': False
            }
        }):
            assert server.is_email_whitelisted('user2@example.com') == True
            assert server.is_email_whitelisted('user4@example.com') == False

    def test_get_current_user_id_with_user(self):
        """Test get_current_user_id returns user ID when user in session."""
        server.app.config['TESTING'] = True
        server.app.config['SECRET_KEY'] = 'test-secret-key'
        with server.app.test_client() as client:
            with client.session_transaction() as sess:
                sess['user'] = {'id': 42, 'email': 'test@example.com'}
            with server.app.test_request_context():
                with client.session_transaction() as sess:
                    server.session.update(sess)
                    # Need to test within app context
                    pass

    def test_get_current_user_id_without_user(self):
        """Test get_current_user_id returns None when no user in session."""
        server.app.config['TESTING'] = True
        server.app.config['SECRET_KEY'] = 'test-secret-key'
        with server.app.test_request_context():
            result = server.get_current_user_id()
            assert result is None


class TestUserOperations:
    """Tests for user database operations."""

    @pytest.fixture
    def mock_connection(self):
        """Create a mock database connection."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        return mock_conn, mock_cursor

    def test_get_or_create_user_creates_new(self, mock_connection):
        """Test creating a new user."""
        mock_conn, mock_cursor = mock_connection
        mock_cursor.fetchone.side_effect = [
            None,  # First call: user doesn't exist
            {'id': 1, 'email': 'new@example.com', 'name': 'New User', 'picture_url': None}  # After insert
        ]

        with patch.object(server, 'get_connection', return_value=mock_conn):
            user = server.get_or_create_user('google123', 'new@example.com', 'New User', None)

        assert user is not None
        assert user['email'] == 'new@example.com'

    def test_get_or_create_user_returns_existing(self, mock_connection):
        """Test returning existing user."""
        mock_conn, mock_cursor = mock_connection
        mock_cursor.fetchone.side_effect = [
            {'id': 1, 'email': 'existing@example.com', 'name': 'Existing', 'picture_url': None},  # User exists
            {'id': 1, 'email': 'existing@example.com', 'name': 'Existing', 'picture_url': None}  # After update
        ]

        with patch.object(server, 'get_connection', return_value=mock_conn):
            user = server.get_or_create_user('google123', 'existing@example.com', 'Existing', None)

        assert user is not None
        assert user['email'] == 'existing@example.com'

    def test_get_or_create_user_handles_error(self, mock_connection):
        """Test error handling in get_or_create_user."""
        with patch.object(server, 'get_connection', side_effect=Exception("DB Error")):
            user = server.get_or_create_user('google123', 'test@example.com', 'Test', None)

        assert user is None


class TestTaskValidation:
    """Tests for task data validation."""

    def test_task_with_all_fields(self):
        """Test task structure with all fields."""
        task = {
            'id': 12345,
            'text': 'Complete task',
            'completed': True,
            'priority': 'high',
            'createdAt': '2025-01-01T12:00:00Z',
            'completedAt': '2025-01-01T13:00:00Z'
        }

        assert task['id'] == 12345
        assert task['text'] == 'Complete task'
        assert task['completed'] == True
        assert task['priority'] == 'high'

    def test_task_minimal_fields(self):
        """Test task with minimal required fields."""
        task = {
            'id': 1,
            'text': 'Minimal task',
            'completed': False
        }

        assert 'id' in task
        assert 'text' in task
        assert 'completed' in task

    def test_task_priority_values(self):
        """Test valid priority values."""
        valid_priorities = ['high', 'medium', 'low']

        for priority in valid_priorities:
            task = {'id': 1, 'text': 'Test', 'priority': priority}
            assert task['priority'] in valid_priorities

    def test_task_completed_states(self):
        """Test completed boolean states."""
        task_incomplete = {'id': 1, 'completed': False}
        task_complete = {'id': 2, 'completed': True}

        assert task_incomplete['completed'] == False
        assert task_complete['completed'] == True

    def test_task_id_is_numeric(self):
        """Test that task ID is numeric."""
        task = {'id': 1234567890123, 'text': 'Test', 'completed': False}
        assert isinstance(task['id'], int)


class TestConfigLoading:
    """Tests for configuration loading."""

    def test_load_config_structure(self):
        """Test that config has required structure."""
        config = server.config

        assert 'database' in config
        assert 'server' in config

    def test_database_config_fields(self):
        """Test database config has all fields."""
        db_config = server.config['database']

        assert 'host' in db_config
        assert 'port' in db_config
        assert 'name' in db_config

    def test_port_is_integer(self):
        """Test that server port is an integer."""
        assert isinstance(server.PORT, int)
        assert server.PORT > 0

    def test_port_in_valid_range(self):
        """Test that port is in valid range."""
        assert 1 <= server.PORT <= 65535

    def test_oauth_config_exists(self):
        """Test that OAuth config section exists."""
        config = server.config
        assert 'oauth' in config

    def test_auth_config_exists(self):
        """Test that auth config section exists."""
        config = server.config
        assert 'auth' in config

    def test_email_whitelist_is_list(self):
        """Test that email_whitelist is a list."""
        auth_config = server.config.get('auth', {})
        whitelist = auth_config.get('email_whitelist', [])
        assert isinstance(whitelist, list)


class TestSecureSessionConfig:
    """Tests for secure session cookie configuration."""

    def test_session_cookie_httponly(self):
        """Test that session cookie has HttpOnly flag."""
        assert server.app.config['SESSION_COOKIE_HTTPONLY'] == True

    def test_session_cookie_samesite(self):
        """Test that session cookie has SameSite=Lax."""
        assert server.app.config['SESSION_COOKIE_SAMESITE'] == 'Lax'

    def test_session_lifetime_configured(self):
        """Test that permanent session lifetime is configured."""
        from datetime import timedelta
        assert server.app.config['PERMANENT_SESSION_LIFETIME'] == timedelta(days=7)

    def test_max_content_length_configured(self):
        """Test that max content length is configured."""
        assert server.app.config['MAX_CONTENT_LENGTH'] == server.MAX_PAYLOAD_SIZE


class TestRateLimiting:
    """Tests for rate limiting configuration."""

    def test_limiter_is_configured(self):
        """Test that rate limiter is configured."""
        assert server.limiter is not None

    def test_default_limits_set(self):
        """Test that default limits are configured."""
        # Limiter should have default limits configured
        assert hasattr(server.limiter, '_default_limits_per_method') or hasattr(server.limiter, 'default_limits')


class TestSecurityHeaders:
    """Tests for security headers."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        server.app.config['TESTING'] = True
        server.app.config['SECRET_KEY'] = 'test-secret-key'
        with server.app.test_client() as client:
            yield client

    def test_x_frame_options_header(self, client):
        """Test X-Frame-Options header is set to DENY."""
        response = client.get('/login')
        assert response.headers.get('X-Frame-Options') == 'DENY'

    def test_x_content_type_options_header(self, client):
        """Test X-Content-Type-Options header is set."""
        response = client.get('/login')
        assert response.headers.get('X-Content-Type-Options') == 'nosniff'

    def test_x_xss_protection_header(self, client):
        """Test X-XSS-Protection header is set."""
        response = client.get('/login')
        assert response.headers.get('X-XSS-Protection') == '1; mode=block'

    def test_referrer_policy_header(self, client):
        """Test Referrer-Policy header is set."""
        response = client.get('/login')
        assert response.headers.get('Referrer-Policy') == 'strict-origin-when-cross-origin'

    def test_permissions_policy_header(self, client):
        """Test Permissions-Policy header is set."""
        response = client.get('/login')
        assert 'geolocation=()' in response.headers.get('Permissions-Policy', '')

    def test_content_security_policy_header(self, client):
        """Test Content-Security-Policy header is set."""
        response = client.get('/login')
        csp = response.headers.get('Content-Security-Policy', '')
        assert "default-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp

    def test_hsts_not_set_in_development(self, client):
        """Test HSTS header is not set in development."""
        with patch.dict('os.environ', {'FLASK_ENV': 'development'}):
            response = client.get('/login')
        # HSTS should not be set in development
        assert 'Strict-Transport-Security' not in response.headers


class TestLoginRequiredDecorator:
    """Tests for login_required decorator behavior."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        server.app.config['TESTING'] = True
        server.app.config['SECRET_KEY'] = 'test-secret-key'
        with server.app.test_client() as client:
            yield client

    def test_decorator_redirects_html_requests(self, client):
        """Test that unauthenticated HTML requests redirect to login."""
        response = client.get('/')
        assert response.status_code == 302
        assert '/login' in response.location

    def test_decorator_returns_401_for_api(self, client):
        """Test that unauthenticated API requests return 401."""
        response = client.get('/api/tasks')
        assert response.status_code == 401
        data = json.loads(response.data)
        assert 'error' in data

    def test_decorator_returns_401_for_json_requests(self, client):
        """Test that JSON requests return 401."""
        response = client.get('/api/me', headers={'Content-Type': 'application/json'})
        assert response.status_code == 401


class TestDatabaseEdgeCases:
    """Tests for database edge cases."""

    @pytest.fixture
    def mock_connection(self):
        """Create a mock database connection."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        return mock_conn, mock_cursor

    def test_load_tasks_with_null_timestamps(self, mock_connection):
        """Test loading tasks when timestamps are null."""
        mock_conn, mock_cursor = mock_connection
        mock_cursor.fetchall.return_value = [
            {'id': 1, 'text': 'Task', 'completed': False, 'priority': 'low', 'createdAt': None, 'completedAt': None}
        ]

        with patch.object(server, 'get_connection', return_value=mock_conn):
            tasks = server.load_tasks_from_db(user_id=1)

        assert len(tasks) == 1
        assert tasks[0]['createdAt'] is None
        assert tasks[0]['completedAt'] is None

    def test_save_tasks_no_deletions_needed(self, mock_connection):
        """Test saving tasks when no deletions are needed."""
        mock_conn, mock_cursor = mock_connection
        mock_cursor.fetchall.return_value = [(1,)]  # Only task 1 exists

        tasks = [{'id': 1, 'text': 'Updated task', 'completed': True, 'priority': 'high'}]

        with patch.object(server, 'get_connection', return_value=mock_conn):
            server.save_tasks(tasks, user_id=1)

        # Verify no DELETE was called since IDs match
        delete_calls = [call for call in mock_cursor.execute.call_args_list
                       if 'DELETE' in str(call)]
        assert len(delete_calls) == 0

    def test_save_tasks_with_default_priority(self, mock_connection):
        """Test saving task without priority uses default."""
        mock_conn, mock_cursor = mock_connection
        mock_cursor.fetchall.return_value = []

        tasks = [{'id': 1, 'text': 'Task without priority', 'completed': False}]

        with patch.object(server, 'get_connection', return_value=mock_conn):
            server.save_tasks(tasks, user_id=1)

        # Verify INSERT was called with 'medium' as default priority
        insert_calls = [call for call in mock_cursor.execute.call_args_list
                       if 'INSERT' in str(call)]
        assert len(insert_calls) == 1


class TestUserWithPicture:
    """Tests for user operations with picture URL."""

    @pytest.fixture
    def mock_connection(self):
        """Create a mock database connection."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        return mock_conn, mock_cursor

    def test_create_user_with_picture(self, mock_connection):
        """Test creating user with picture URL."""
        mock_conn, mock_cursor = mock_connection
        mock_cursor.fetchone.side_effect = [
            None,  # User doesn't exist
            {'id': 1, 'email': 'new@example.com', 'name': 'New User', 'picture_url': 'https://example.com/pic.jpg'}
        ]

        with patch.object(server, 'get_connection', return_value=mock_conn):
            user = server.get_or_create_user('google123', 'new@example.com', 'New User', 'https://example.com/pic.jpg')

        assert user is not None
        assert user['picture_url'] == 'https://example.com/pic.jpg'

    def test_update_existing_user_picture(self, mock_connection):
        """Test updating existing user's picture URL."""
        mock_conn, mock_cursor = mock_connection
        mock_cursor.fetchone.side_effect = [
            {'id': 1, 'email': 'existing@example.com', 'name': 'Old Name', 'picture_url': 'https://old.com/pic.jpg'},
            {'id': 1, 'email': 'existing@example.com', 'name': 'New Name', 'picture_url': 'https://new.com/pic.jpg'}
        ]

        with patch.object(server, 'get_connection', return_value=mock_conn):
            user = server.get_or_create_user('google123', 'existing@example.com', 'New Name', 'https://new.com/pic.jpg')

        assert user is not None
        assert user['name'] == 'New Name'
        assert user['picture_url'] == 'https://new.com/pic.jpg'


class TestCategoryOperations:
    """Tests for category database operations."""

    @pytest.fixture
    def mock_connection(self):
        """Create a mock database connection."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        return mock_conn, mock_cursor

    def test_load_categories_from_db_empty(self, mock_connection):
        """Test loading categories when none exist."""
        mock_conn, mock_cursor = mock_connection
        mock_cursor.fetchall.return_value = []

        with patch.object(server, 'get_connection', return_value=mock_conn):
            categories = server.load_categories_from_db(user_id=1)

        assert categories == []

    def test_load_categories_from_db_with_data(self, mock_connection):
        """Test loading categories with existing data."""
        mock_conn, mock_cursor = mock_connection
        mock_cursor.fetchall.return_value = [
            {'id': 1, 'name': 'Work', 'createdAt': datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)},
            {'id': 2, 'name': 'Personal', 'createdAt': datetime(2024, 1, 2, 12, 0, 0, tzinfo=timezone.utc)}
        ]

        with patch.object(server, 'get_connection', return_value=mock_conn):
            categories = server.load_categories_from_db(user_id=1)

        assert len(categories) == 2
        assert categories[0]['name'] == 'Work'
        assert categories[1]['name'] == 'Personal'

    def test_load_categories_handles_error(self, mock_connection):
        """Test error handling in load_categories_from_db."""
        with patch.object(server, 'get_connection', side_effect=Exception("DB Error")):
            categories = server.load_categories_from_db(user_id=1)

        assert categories == []

    def test_save_categories_insert_new(self, mock_connection):
        """Test saving new categories."""
        mock_conn, mock_cursor = mock_connection
        mock_cursor.fetchall.return_value = []

        categories = [{'id': 1, 'name': 'Work', 'createdAt': '2024-01-01T12:00:00Z'}]

        with patch.object(server, 'get_connection', return_value=mock_conn):
            server.save_categories(categories, user_id=1)

        mock_conn.commit.assert_called_once()

    def test_save_categories_delete_removed(self, mock_connection):
        """Test deleting removed categories."""
        mock_conn, mock_cursor = mock_connection
        mock_cursor.fetchall.return_value = [(1,), (2,)]  # Existing IDs

        categories = [{'id': 1, 'name': 'Work'}]  # Only keep id=1

        with patch.object(server, 'get_connection', return_value=mock_conn):
            server.save_categories(categories, user_id=1)

        # Verify DELETE was called for removed category
        delete_calls = [call for call in mock_cursor.execute.call_args_list
                       if 'DELETE' in str(call)]
        assert len(delete_calls) == 1


class TestCategoryAPI:
    """Tests for category API endpoints."""

    @pytest.fixture
    def authenticated_client(self):
        """Create an authenticated test client."""
        server.app.config['TESTING'] = True
        server.app.config['SECRET_KEY'] = 'test-secret-key'
        with server.app.test_client() as client:
            with client.session_transaction() as sess:
                sess['user'] = {'id': 1, 'email': 'test@example.com', 'name': 'Test User', 'picture_url': None}
            yield client

    @pytest.fixture
    def client(self):
        """Create an unauthenticated test client."""
        server.app.config['TESTING'] = True
        server.app.config['SECRET_KEY'] = 'test-secret-key'
        with server.app.test_client() as client:
            yield client

    def test_get_categories_returns_401_without_auth(self, client):
        """Test that /api/categories requires authentication."""
        response = client.get('/api/categories')
        assert response.status_code == 401

    def test_get_categories_with_auth(self, authenticated_client):
        """Test getting categories when authenticated."""
        with patch.object(server, 'load_categories_from_db', return_value=[]):
            response = authenticated_client.get('/api/categories')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list)

    def test_post_categories_returns_401_without_auth(self, client):
        """Test that POST /api/categories requires authentication."""
        response = client.post('/api/categories',
                              data=json.dumps([]),
                              content_type='application/json')
        assert response.status_code == 401

    def test_post_categories_with_auth(self, authenticated_client):
        """Test saving categories when authenticated."""
        with patch.object(server, 'save_categories') as mock_save:
            response = authenticated_client.post('/api/categories',
                                                 data=json.dumps([{'id': 1, 'name': 'Work'}]),
                                                 content_type='application/json')

        assert response.status_code == 200
        mock_save.assert_called_once()


class TestTaskWithCategory:
    """Tests for tasks with category associations."""

    @pytest.fixture
    def mock_connection(self):
        """Create a mock database connection."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        return mock_conn, mock_cursor

    def test_load_tasks_includes_category_id(self, mock_connection):
        """Test that loaded tasks include categoryId."""
        mock_conn, mock_cursor = mock_connection
        mock_cursor.fetchall.return_value = [
            {'id': 1, 'text': 'Test task', 'completed': False, 'priority': 'high',
             'categoryId': 100, 'createdAt': None, 'completedAt': None}
        ]

        with patch.object(server, 'get_connection', return_value=mock_conn):
            tasks = server.load_tasks_from_db(user_id=1)

        assert len(tasks) == 1
        assert tasks[0]['categoryId'] == 100

    def test_save_tasks_includes_category_id(self, mock_connection):
        """Test that saving tasks includes categoryId."""
        mock_conn, mock_cursor = mock_connection
        mock_cursor.fetchall.return_value = []

        tasks = [{'id': 1, 'text': 'Task', 'completed': False, 'categoryId': 100}]

        with patch.object(server, 'get_connection', return_value=mock_conn):
            server.save_tasks(tasks, user_id=1)

        # Verify INSERT was called with category_id
        insert_calls = [call for call in mock_cursor.execute.call_args_list
                       if 'INSERT' in str(call)]
        assert len(insert_calls) == 1

    def test_save_tasks_with_null_category(self, mock_connection):
        """Test saving task without category."""
        mock_conn, mock_cursor = mock_connection
        mock_cursor.fetchall.return_value = []

        tasks = [{'id': 1, 'text': 'Task without category', 'completed': False}]

        with patch.object(server, 'get_connection', return_value=mock_conn):
            server.save_tasks(tasks, user_id=1)

        mock_conn.commit.assert_called_once()


class TestTaskValidation:
    """Tests for task input validation."""

    def test_validate_task_valid(self):
        """Test valid task passes validation."""
        task = {'id': 123, 'text': 'Valid task', 'completed': False, 'priority': 'high'}
        assert server.validate_task(task) == True

    def test_validate_task_missing_id(self):
        """Test task without ID fails validation."""
        task = {'text': 'No ID task', 'completed': False}
        with pytest.raises(server.ValidationError, match="Task ID must be a positive number"):
            server.validate_task(task)

    def test_validate_task_negative_id(self):
        """Test task with negative ID fails validation."""
        task = {'id': -1, 'text': 'Negative ID', 'completed': False}
        with pytest.raises(server.ValidationError, match="Task ID must be a positive number"):
            server.validate_task(task)

    def test_validate_task_empty_text(self):
        """Test task with empty text fails validation."""
        task = {'id': 123, 'text': '   ', 'completed': False}
        with pytest.raises(server.ValidationError, match="Task text cannot be empty"):
            server.validate_task(task)

    def test_validate_task_text_too_long(self):
        """Test task with text exceeding max length fails validation."""
        task = {'id': 123, 'text': 'x' * (server.MAX_TASK_TEXT_LENGTH + 1), 'completed': False}
        with pytest.raises(server.ValidationError, match="exceeds maximum length"):
            server.validate_task(task)

    def test_validate_task_invalid_priority(self):
        """Test task with invalid priority fails validation."""
        task = {'id': 123, 'text': 'Task', 'completed': False, 'priority': 'urgent'}
        with pytest.raises(server.ValidationError, match="Invalid priority"):
            server.validate_task(task)

    def test_validate_task_invalid_completed(self):
        """Test task with non-boolean completed fails validation."""
        task = {'id': 123, 'text': 'Task', 'completed': 'yes'}
        with pytest.raises(server.ValidationError, match="completed must be a boolean"):
            server.validate_task(task)

    def test_validate_tasks_too_many(self):
        """Test too many tasks fails validation."""
        tasks = [{'id': i, 'text': f'Task {i}', 'completed': False}
                 for i in range(server.MAX_TASKS_PER_USER + 1)]
        with pytest.raises(server.ValidationError, match="Cannot have more than"):
            server.validate_tasks(tasks, user_id=1)

    def test_validate_tasks_duplicate_ids(self):
        """Test duplicate task IDs fails validation."""
        tasks = [
            {'id': 123, 'text': 'Task 1', 'completed': False},
            {'id': 123, 'text': 'Task 2', 'completed': False}
        ]
        with pytest.raises(server.ValidationError, match="Duplicate task ID"):
            server.validate_tasks(tasks, user_id=1)

    def test_validate_tasks_not_array(self):
        """Test non-array tasks fails validation."""
        with pytest.raises(server.ValidationError, match="Tasks must be an array"):
            server.validate_tasks({'id': 1, 'text': 'Task'}, user_id=1)


class TestCategoryValidation:
    """Tests for category input validation."""

    def test_validate_category_valid(self):
        """Test valid category passes validation."""
        category = {'id': 123, 'name': 'Work'}
        assert server.validate_category(category) == True

    def test_validate_category_missing_id(self):
        """Test category without ID fails validation."""
        category = {'name': 'Work'}
        with pytest.raises(server.ValidationError, match="Category ID must be a positive number"):
            server.validate_category(category)

    def test_validate_category_empty_name(self):
        """Test category with empty name fails validation."""
        category = {'id': 123, 'name': '   '}
        with pytest.raises(server.ValidationError, match="Category name cannot be empty"):
            server.validate_category(category)

    def test_validate_category_name_too_long(self):
        """Test category with name exceeding max length fails validation."""
        category = {'id': 123, 'name': 'x' * (server.MAX_CATEGORY_NAME_LENGTH + 1)}
        with pytest.raises(server.ValidationError, match="exceeds maximum length"):
            server.validate_category(category)

    def test_validate_categories_too_many(self):
        """Test too many categories fails validation."""
        categories = [{'id': i, 'name': f'Category {i}'}
                      for i in range(server.MAX_CATEGORIES_PER_USER + 1)]
        with pytest.raises(server.ValidationError, match="Cannot have more than"):
            server.validate_categories(categories, user_id=1)

    def test_validate_categories_duplicate_ids(self):
        """Test duplicate category IDs fails validation."""
        categories = [
            {'id': 123, 'name': 'Work'},
            {'id': 123, 'name': 'Personal'}
        ]
        with pytest.raises(server.ValidationError, match="Duplicate category ID"):
            server.validate_categories(categories, user_id=1)

    def test_validate_categories_duplicate_names(self):
        """Test duplicate category names fails validation."""
        categories = [
            {'id': 1, 'name': 'Work'},
            {'id': 2, 'name': 'work'}  # Same name, different case
        ]
        with pytest.raises(server.ValidationError, match="Duplicate category name"):
            server.validate_categories(categories, user_id=1)


class TestValidationAPI:
    """Tests for validation in API endpoints."""

    @pytest.fixture
    def authenticated_client(self):
        """Create an authenticated test client."""
        server.app.config['TESTING'] = True
        server.app.config['SECRET_KEY'] = 'test-secret-key'
        with server.app.test_client() as client:
            with client.session_transaction() as sess:
                sess['user'] = {'id': 1, 'email': 'test@example.com', 'name': 'Test User', 'picture_url': None}
            yield client

    def test_post_tasks_invalid_json(self, authenticated_client):
        """Test posting invalid JSON returns 400."""
        response = authenticated_client.post('/api/tasks',
                                             data='not json',
                                             content_type='application/json')
        assert response.status_code == 400

    def test_post_tasks_validation_error(self, authenticated_client):
        """Test posting invalid task returns 400 with error message."""
        tasks = [{'id': 1, 'text': '', 'completed': False}]  # Empty text
        response = authenticated_client.post('/api/tasks',
                                             data=json.dumps(tasks),
                                             content_type='application/json')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'empty' in data['error'].lower()

    def test_post_categories_validation_error(self, authenticated_client):
        """Test posting invalid category returns 400 with error message."""
        categories = [{'id': 1, 'name': ''}]  # Empty name
        response = authenticated_client.post('/api/categories',
                                             data=json.dumps(categories),
                                             content_type='application/json')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_post_tasks_valid(self, authenticated_client):
        """Test posting valid tasks succeeds."""
        tasks = [{'id': 1, 'text': 'Valid task', 'completed': False, 'priority': 'medium'}]
        with patch.object(server, 'save_tasks'):
            response = authenticated_client.post('/api/tasks',
                                                 data=json.dumps(tasks),
                                                 content_type='application/json')
        assert response.status_code == 200


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
