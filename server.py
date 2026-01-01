#!/usr/bin/env python3
import copy
import http.server
import json
import os
import psycopg2
from psycopg2.extras import RealDictCursor

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')

def load_config():
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

config = load_config()
PORT = config['server']['port']

# In-memory cache
_task_cache = None

def get_connection():
    db = config['database']
    return psycopg2.connect(
        host=db['host'] or None,
        port=db['port'] or None,
        dbname=db['name'],
        user=db['user'] or None,
        password=db['password'] or None
    )

def load_tasks_from_db():
    """Load tasks directly from database."""
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, text, completed, priority,
                           created_at as "createdAt",
                           completed_at as "completedAt"
                    FROM tasks ORDER BY id
                """)
                tasks = cur.fetchall()
                # Convert to JSON-serializable format
                result = []
                for task in tasks:
                    t = dict(task)
                    if t['createdAt']:
                        t['createdAt'] = t['createdAt'].isoformat()
                    if t['completedAt']:
                        t['completedAt'] = t['completedAt'].isoformat()
                    result.append(t)
                return result
    except Exception as e:
        print(f"Error reading tasks from database: {e}")
        return []

def init_cache():
    """Initialize the cache from database."""
    global _task_cache
    _task_cache = load_tasks_from_db()
    print(f"Cache initialized with {len(_task_cache)} tasks")

def read_tasks():
    """Read tasks from cache (fast)."""
    global _task_cache
    if _task_cache is None:
        init_cache()
    return _task_cache

def save_tasks(tasks):
    """Save tasks to database and update cache."""
    global _task_cache
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Get existing task IDs
                cur.execute("SELECT id FROM tasks")
                existing_ids = {row[0] for row in cur.fetchall()}

                incoming_ids = {task['id'] for task in tasks}

                # Delete removed tasks
                deleted_ids = existing_ids - incoming_ids
                if deleted_ids:
                    cur.execute("DELETE FROM tasks WHERE id = ANY(%s)", (list(deleted_ids),))

                # Upsert tasks
                for task in tasks:
                    created_at = task.get('createdAt')
                    completed_at = task.get('completedAt')

                    cur.execute("""
                        INSERT INTO tasks (id, text, completed, priority, created_at, completed_at)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (id) DO UPDATE SET
                            text = EXCLUDED.text,
                            completed = EXCLUDED.completed,
                            priority = EXCLUDED.priority,
                            created_at = EXCLUDED.created_at,
                            completed_at = EXCLUDED.completed_at
                    """, (task['id'], task['text'], task['completed'],
                          task.get('priority', 'medium'), created_at, completed_at))

                conn.commit()

        # Update cache after successful save (deep copy to avoid reference issues)
        _task_cache = copy.deepcopy(tasks)
    except Exception as e:
        print(f"Error saving tasks: {e}")

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'index.html')
            with open(html_path, 'r') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(content.encode())
        elif self.path == '/api/tasks':
            tasks = read_tasks()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(tasks).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == '/api/tasks':
            content_length = int(self.headers['Content-Length'])
            body = self.rfile.read(content_length)
            try:
                tasks = json.loads(body)
                save_tasks(tasks)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': True}).encode())
            except Exception as e:
                print(f"Error: {e}")
                self.send_response(400)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress request logging

if __name__ == '__main__':
    # Initialize cache on startup
    init_cache()

    server = http.server.HTTPServer(('', PORT), Handler)
    print(f'ToDo app running at http://localhost:{PORT}')
    server.serve_forever()
