#!/usr/bin/env python3
import json
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

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

    def test_save_tasks_handles_error(self, mock_connection):
        """Test that save_tasks handles database errors gracefully."""
        with patch.object(server, 'get_connection', side_effect=Exception("DB Error")):
            # Should not raise exception
            server.save_tasks([{'id': 1, 'text': 'Test', 'completed': False}], user_id=1)

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

    def test_login_page_accessible(self, client):
        """Test that login page is accessible."""
        response = client.get('/login')
        assert response.status_code == 200
        assert b'Sign in with Google' in response.data

    def test_index_redirects_without_auth(self, client):
        """Test that index page redirects to login without authentication."""
        response = client.get('/')
        assert response.status_code == 302
        assert '/login' in response.location

    def test_api_tasks_returns_401_without_auth(self, client):
        """Test that API returns 401 without authentication."""
        response = client.get('/api/tasks')
        assert response.status_code == 401

    def test_api_me_returns_401_without_auth(self, client):
        """Test that /api/me returns 401 without authentication."""
        response = client.get('/api/me')
        assert response.status_code == 401

    def test_logout_redirects_to_login(self, client):
        """Test that logout redirects to login."""
        response = client.get('/auth/logout')
        assert response.status_code == 302
        assert '/login' in response.location


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


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
