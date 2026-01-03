#!/usr/bin/env python3
import json
import os
import secrets
from functools import wraps

import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify, redirect, url_for, session, send_file, render_template
from authlib.integrations.flask_client import OAuth

# Configuration
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')

def load_config():
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

config = load_config()
PORT = config['server']['port']

# Flask app setup
app = Flask(__name__, template_folder='templates')
app.secret_key = os.environ.get('SECRET_KEY') or config['server'].get('secret_key') or secrets.token_hex(32)

# OAuth setup
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.environ.get('GOOGLE_CLIENT_ID') or config.get('oauth', {}).get('google_client_id'),
    client_secret=os.environ.get('GOOGLE_CLIENT_SECRET') or config.get('oauth', {}).get('google_client_secret'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

# Database connection
def get_connection():
    db = config['database']
    return psycopg2.connect(
        host=db['host'] or None,
        port=db['port'] or None,
        dbname=db['name'],
        user=db['user'] or None,
        password=db['password'] or None
    )

# Authentication helpers
def is_email_whitelisted(email):
    """Check if email is in the whitelist."""
    auth_config = config.get('auth', {})
    if auth_config.get('allow_any_email', False):
        return True
    whitelist = auth_config.get('email_whitelist', [])
    return email.lower() in [e.lower() for e in whitelist]

def get_or_create_user(google_id, email, name, picture_url):
    """Get existing user or create new one."""
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Try to find existing user
                cur.execute("SELECT id, email, name, picture_url FROM users WHERE google_id = %s", (google_id,))
                user = cur.fetchone()

                if user:
                    # Update last login and user info
                    cur.execute("""
                        UPDATE users SET last_login = NOW(), name = %s, picture_url = %s
                        WHERE google_id = %s
                        RETURNING id, email, name, picture_url
                    """, (name, picture_url, google_id))
                    user = cur.fetchone()
                else:
                    # Create new user
                    cur.execute("""
                        INSERT INTO users (google_id, email, name, picture_url)
                        VALUES (%s, %s, %s, %s)
                        RETURNING id, email, name, picture_url
                    """, (google_id, email, name, picture_url))
                    user = cur.fetchone()

                conn.commit()
                return dict(user)
    except Exception as e:
        print(f"Error in get_or_create_user: {e}")
        return None

def login_required(f):
    """Decorator to require authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Unauthorized'}), 401
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_current_user_id():
    """Get current user ID from session."""
    user = session.get('user')
    return user['id'] if user else None

# Task database operations
def load_tasks_from_db(user_id):
    """Load tasks for a specific user from database."""
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, text, completed, priority,
                           created_at as "createdAt",
                           completed_at as "completedAt"
                    FROM tasks
                    WHERE user_id = %s
                    ORDER BY id
                """, (user_id,))
                tasks = cur.fetchall()
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

def save_tasks(tasks, user_id):
    """Save tasks for a specific user to database."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Get existing task IDs for this user
                cur.execute("SELECT id FROM tasks WHERE user_id = %s", (user_id,))
                existing_ids = {row[0] for row in cur.fetchall()}

                incoming_ids = {task['id'] for task in tasks}

                # Delete removed tasks
                deleted_ids = existing_ids - incoming_ids
                if deleted_ids:
                    cur.execute("DELETE FROM tasks WHERE id = ANY(%s) AND user_id = %s",
                               (list(deleted_ids), user_id))

                # Upsert tasks
                for task in tasks:
                    created_at = task.get('createdAt')
                    completed_at = task.get('completedAt')

                    cur.execute("""
                        INSERT INTO tasks (id, user_id, text, completed, priority, created_at, completed_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (id) DO UPDATE SET
                            text = EXCLUDED.text,
                            completed = EXCLUDED.completed,
                            priority = EXCLUDED.priority,
                            created_at = EXCLUDED.created_at,
                            completed_at = EXCLUDED.completed_at
                        WHERE tasks.user_id = %s
                    """, (task['id'], user_id, task['text'], task['completed'],
                          task.get('priority', 'medium'), created_at, completed_at, user_id))

                conn.commit()
    except Exception as e:
        print(f"Error saving tasks: {e}")

# Authentication routes
@app.route('/login')
def login():
    """Show login page."""
    error = request.args.get('error')
    return render_template('login.html', error=error)

@app.route('/auth/google')
def auth_google():
    """Initiate Google OAuth flow."""
    redirect_uri = os.environ.get('OAUTH_REDIRECT_URI') or config.get('oauth', {}).get('redirect_uri') or url_for('auth_google_callback', _external=True)
    # Force account selection to allow switching users after logout
    return google.authorize_redirect(redirect_uri, prompt='select_account')

@app.route('/auth/google/callback')
def auth_google_callback():
    """Handle Google OAuth callback."""
    try:
        token = google.authorize_access_token()
        user_info = token.get('userinfo')

        if not user_info:
            return redirect(url_for('login', error='Failed to get user info from Google'))

        email = user_info.get('email')
        google_id = user_info.get('sub')
        name = user_info.get('name')
        picture = user_info.get('picture')

        # Check whitelist
        if not is_email_whitelisted(email):
            return render_template('denied.html', email=email)

        # Get or create user
        user = get_or_create_user(google_id, email, name, picture)
        if not user:
            return redirect(url_for('login', error='Failed to create user account'))

        # Set session
        session['user'] = user
        session.permanent = True

        return redirect(url_for('index'))

    except Exception as e:
        print(f"OAuth callback error: {e}")
        return redirect(url_for('login', error='Authentication failed'))

@app.route('/auth/logout')
def logout():
    """Log out user."""
    session.clear()
    return redirect(url_for('login'))

@app.route('/api/me')
@login_required
def get_current_user():
    """Get current user info."""
    return jsonify(session.get('user'))

# Application routes
@app.route('/')
@login_required
def index():
    """Serve the main application page."""
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'index.html')
    return send_file(html_path)

@app.route('/api/tasks', methods=['GET'])
@login_required
def get_tasks():
    """Get all tasks for current user."""
    user_id = get_current_user_id()
    tasks = load_tasks_from_db(user_id)
    return jsonify(tasks)

@app.route('/api/tasks', methods=['POST'])
@login_required
def post_tasks():
    """Save tasks for current user."""
    user_id = get_current_user_id()
    try:
        tasks = request.get_json()
        save_tasks(tasks, user_id)
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 400

if __name__ == '__main__':
    print(f'ToDo app running at http://localhost:{PORT}')
    app.run(host='0.0.0.0', port=PORT, debug=False)
