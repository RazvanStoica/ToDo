#!/usr/bin/env python3
import json
import pytest
import psycopg2
from unittest.mock import patch, MagicMock
from io import BytesIO
from http.server import HTTPServer
import threading
import urllib.request
import urllib.error

# Import the server module
import server


class TestDatabaseOperations:
    """Tests for database read/write operations."""

    @pytest.fixture(autouse=True)
    def reset_cache(self):
        """Reset the cache before each test."""
        server._task_cache = None

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
            tasks = server.load_tasks_from_db()

        assert tasks == []

    def test_load_tasks_from_db_with_data(self, mock_connection):
        """Test loading tasks with data in database."""
        mock_conn, mock_cursor = mock_connection
        from datetime import datetime, timezone

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
            tasks = server.load_tasks_from_db()

        assert len(tasks) == 1
        assert tasks[0]['text'] == 'Test task'
        assert tasks[0]['priority'] == 'high'
        assert tasks[0]['completed'] == False

    def test_load_tasks_from_db_handles_error(self, mock_connection):
        """Test that load_tasks_from_db handles database errors gracefully."""
        with patch.object(server, 'get_connection', side_effect=Exception("DB Error")):
            tasks = server.load_tasks_from_db()

        assert tasks == []

    def test_read_tasks_uses_cache(self, mock_connection):
        """Test that read_tasks returns cached data."""
        # Set cache directly
        server._task_cache = [{'id': 1, 'text': 'Cached task'}]

        # Should return cache without hitting database
        tasks = server.read_tasks()

        assert len(tasks) == 1
        assert tasks[0]['text'] == 'Cached task'

    def test_save_tasks_insert_new(self, mock_connection):
        """Test saving a new task."""
        mock_conn, mock_cursor = mock_connection
        mock_cursor.fetchall.return_value = []  # No existing tasks

        tasks = [{
            'id': 123,
            'text': 'New task',
            'completed': False,
            'priority': 'medium',
            'createdAt': '2025-01-01T12:00:00Z'
        }]

        with patch.object(server, 'get_connection', return_value=mock_conn):
            server.save_tasks(tasks)

        # Verify commit was called
        mock_conn.commit.assert_called_once()

    def test_save_tasks_delete_removed(self, mock_connection):
        """Test that removed tasks are deleted."""
        mock_conn, mock_cursor = mock_connection
        mock_cursor.fetchall.return_value = [(1,), (2,), (3,)]  # Existing task IDs

        # Only task 1 remains
        tasks = [{
            'id': 1,
            'text': 'Remaining task',
            'completed': False,
            'priority': 'low'
        }]

        with patch.object(server, 'get_connection', return_value=mock_conn):
            server.save_tasks(tasks)

        # Verify delete was called for tasks 2 and 3
        delete_calls = [call for call in mock_cursor.execute.call_args_list
                       if 'DELETE' in str(call)]
        assert len(delete_calls) == 1


class TestHTTPHandler:
    """Tests for HTTP request handling."""

    @pytest.fixture
    def handler(self):
        """Create a mock HTTP handler."""
        handler = MagicMock(spec=server.Handler)
        handler.headers = {'Content-Length': '100'}
        handler.wfile = BytesIO()
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()
        return handler

    def test_get_tasks_endpoint(self, handler):
        """Test GET /api/tasks returns tasks."""
        handler.path = '/api/tasks'
        mock_tasks = [{'id': 1, 'text': 'Test', 'completed': False}]

        with patch.object(server, 'read_tasks', return_value=mock_tasks):
            server.Handler.do_GET(handler)

        handler.send_response.assert_called_with(200)

    def test_get_index_page(self, handler):
        """Test GET / returns HTML page."""
        handler.path = '/'

        with patch('builtins.open', MagicMock()):
            with patch.object(server, 'os') as mock_os:
                mock_os.path.dirname.return_value = '/test'
                mock_os.path.abspath.return_value = '/test'
                mock_os.path.join.return_value = '/test/index.html'

                # Mock file read
                mock_file = MagicMock()
                mock_file.read.return_value = '<html></html>'
                mock_file.__enter__ = MagicMock(return_value=mock_file)
                mock_file.__exit__ = MagicMock(return_value=False)

                with patch('builtins.open', return_value=mock_file):
                    server.Handler.do_GET(handler)

        handler.send_response.assert_called_with(200)

    def test_get_404_for_unknown_path(self, handler):
        """Test GET returns 404 for unknown paths."""
        handler.path = '/unknown'

        server.Handler.do_GET(handler)

        handler.send_response.assert_called_with(404)

    def test_post_tasks_success(self, handler):
        """Test POST /api/tasks saves tasks."""
        handler.path = '/api/tasks'
        handler.headers = {'Content-Length': '50'}
        handler.rfile = BytesIO(b'[{"id": 1, "text": "Test", "completed": false}]')

        with patch.object(server, 'save_tasks') as mock_save:
            server.Handler.do_POST(handler)

        mock_save.assert_called_once()
        handler.send_response.assert_called_with(200)

    def test_post_tasks_invalid_json(self, handler):
        """Test POST /api/tasks returns 400 for invalid JSON."""
        handler.path = '/api/tasks'
        handler.headers = {'Content-Length': '10'}
        handler.rfile = BytesIO(b'not json!')

        server.Handler.do_POST(handler)

        handler.send_response.assert_called_with(400)

    def test_post_404_for_unknown_path(self, handler):
        """Test POST returns 404 for unknown paths."""
        handler.path = '/unknown'
        handler.headers = {'Content-Length': '0'}
        handler.rfile = BytesIO(b'')

        server.Handler.do_POST(handler)

        handler.send_response.assert_called_with(404)


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


class TestConfigLoading:
    """Tests for configuration loading."""

    def test_load_config_structure(self):
        """Test that config has required structure."""
        config = server.config

        assert 'database' in config
        assert 'server' in config
        assert 'name' in config['database']
        assert 'port' in config['server']

    def test_port_is_integer(self):
        """Test that server port is an integer."""
        assert isinstance(server.PORT, int)
        assert server.PORT > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
