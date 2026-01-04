#!/usr/bin/env python3
import json
import os
import secrets
from datetime import timedelta
from functools import wraps

import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify, redirect, url_for, session, send_file, render_template
from authlib.integrations.flask_client import OAuth

# Validation limits
MAX_TASK_TEXT_LENGTH = 1000
MAX_CATEGORY_NAME_LENGTH = 100
MAX_TASKS_PER_USER = 10000
MAX_CATEGORIES_PER_USER = 100
MAX_PAYLOAD_SIZE = 1024 * 1024  # 1MB
VALID_PRIORITIES = {'high', 'medium', 'low'}

class ValidationError(Exception):
    """Custom exception for validation errors."""
    pass

def validate_task(task):
    """Validate a single task object."""
    if not isinstance(task, dict):
        raise ValidationError("Task must be an object")

    # Validate ID
    task_id = task.get('id')
    if not isinstance(task_id, (int, float)) or task_id < 0:
        raise ValidationError("Task ID must be a positive number")

    # Validate text
    text = task.get('text')
    if not isinstance(text, str):
        raise ValidationError("Task text must be a string")
    if not text.strip():
        raise ValidationError("Task text cannot be empty")
    if len(text) > MAX_TASK_TEXT_LENGTH:
        raise ValidationError(f"Task text exceeds maximum length of {MAX_TASK_TEXT_LENGTH}")

    # Validate completed
    if 'completed' in task and not isinstance(task['completed'], bool):
        raise ValidationError("Task completed must be a boolean")

    # Validate priority
    priority = task.get('priority', 'medium')
    if priority not in VALID_PRIORITIES:
        raise ValidationError(f"Invalid priority. Must be one of: {', '.join(VALID_PRIORITIES)}")

    # Validate categoryId (optional)
    category_id = task.get('categoryId')
    if category_id is not None and not isinstance(category_id, (int, float)):
        raise ValidationError("Category ID must be a number or null")

    return True

def validate_tasks(tasks, user_id):
    """Validate a list of tasks."""
    if not isinstance(tasks, list):
        raise ValidationError("Tasks must be an array")

    if len(tasks) > MAX_TASKS_PER_USER:
        raise ValidationError(f"Cannot have more than {MAX_TASKS_PER_USER} tasks")

    seen_ids = set()
    for task in tasks:
        validate_task(task)
        task_id = task.get('id')
        if task_id in seen_ids:
            raise ValidationError(f"Duplicate task ID: {task_id}")
        seen_ids.add(task_id)

    return True

def validate_category(category):
    """Validate a single category object."""
    if not isinstance(category, dict):
        raise ValidationError("Category must be an object")

    # Validate ID
    cat_id = category.get('id')
    if not isinstance(cat_id, (int, float)) or cat_id < 0:
        raise ValidationError("Category ID must be a positive number")

    # Validate name
    name = category.get('name')
    if not isinstance(name, str):
        raise ValidationError("Category name must be a string")
    if not name.strip():
        raise ValidationError("Category name cannot be empty")
    if len(name) > MAX_CATEGORY_NAME_LENGTH:
        raise ValidationError(f"Category name exceeds maximum length of {MAX_CATEGORY_NAME_LENGTH}")

    return True

def validate_categories(categories, user_id):
    """Validate a list of categories."""
    if not isinstance(categories, list):
        raise ValidationError("Categories must be an array")

    if len(categories) > MAX_CATEGORIES_PER_USER:
        raise ValidationError(f"Cannot have more than {MAX_CATEGORIES_PER_USER} categories")

    seen_ids = set()
    seen_names = set()
    for category in categories:
        validate_category(category)
        cat_id = category.get('id')
        name = category.get('name').lower().strip()

        if cat_id in seen_ids:
            raise ValidationError(f"Duplicate category ID: {cat_id}")
        seen_ids.add(cat_id)

        if name in seen_names:
            raise ValidationError(f"Duplicate category name: {category.get('name')}")
        seen_names.add(name)

    return True

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
app.config['MAX_CONTENT_LENGTH'] = MAX_PAYLOAD_SIZE  # Limit request size

# Secure session cookie configuration
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_ENV') == 'production'  # HTTPS only in production
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Prevent JavaScript access
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # CSRF protection (Lax allows OAuth redirects)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)  # Session expires after 7 days

# Security headers
@app.after_request
def add_security_headers(response):
    # Prevent clickjacking
    response.headers['X-Frame-Options'] = 'DENY'
    # Prevent MIME type sniffing
    response.headers['X-Content-Type-Options'] = 'nosniff'
    # XSS protection (legacy, but still useful for older browsers)
    response.headers['X-XSS-Protection'] = '1; mode=block'
    # Control referrer information
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    # Permissions policy (restrict browser features)
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
    # Content Security Policy
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' https://*.googleusercontent.com data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "form-action 'self' https://accounts.google.com; "
        "base-uri 'self'"
    )
    # HSTS (only in production with HTTPS)
    if os.environ.get('FLASK_ENV') == 'production':
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

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
                           category_id as "categoryId",
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
                    category_id = task.get('categoryId')

                    cur.execute("""
                        INSERT INTO tasks (id, user_id, text, completed, priority, category_id, created_at, completed_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (id) DO UPDATE SET
                            text = EXCLUDED.text,
                            completed = EXCLUDED.completed,
                            priority = EXCLUDED.priority,
                            category_id = EXCLUDED.category_id,
                            created_at = EXCLUDED.created_at,
                            completed_at = EXCLUDED.completed_at
                        WHERE tasks.user_id = %s
                    """, (task['id'], user_id, task['text'], task['completed'],
                          task.get('priority', 'medium'), category_id, created_at, completed_at, user_id))

                conn.commit()
    except Exception as e:
        print(f"Error saving tasks: {e}")

# Category database operations
def load_categories_from_db(user_id):
    """Load categories for a specific user from database."""
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, name, created_at as "createdAt"
                    FROM categories
                    WHERE user_id = %s
                    ORDER BY name
                """, (user_id,))
                categories = cur.fetchall()
                result = []
                for cat in categories:
                    c = dict(cat)
                    if c['createdAt']:
                        c['createdAt'] = c['createdAt'].isoformat()
                    result.append(c)
                return result
    except Exception as e:
        print(f"Error reading categories from database: {e}")
        return []

def save_categories(categories, user_id):
    """Save categories for a specific user to database."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Get existing category IDs for this user
                cur.execute("SELECT id FROM categories WHERE user_id = %s", (user_id,))
                existing_ids = {row[0] for row in cur.fetchall()}

                incoming_ids = {cat['id'] for cat in categories}

                # Delete removed categories
                deleted_ids = existing_ids - incoming_ids
                if deleted_ids:
                    cur.execute("DELETE FROM categories WHERE id = ANY(%s) AND user_id = %s",
                               (list(deleted_ids), user_id))

                # Upsert categories
                for cat in categories:
                    created_at = cat.get('createdAt')

                    cur.execute("""
                        INSERT INTO categories (id, user_id, name, created_at)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (id) DO UPDATE SET
                            name = EXCLUDED.name
                        WHERE categories.user_id = %s
                    """, (cat['id'], user_id, cat['name'], created_at, user_id))

                conn.commit()
    except Exception as e:
        print(f"Error saving categories: {e}")

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
        tasks = request.get_json(silent=True)
        if tasks is None:
            return jsonify({'error': 'Invalid JSON payload'}), 400

        # Validate tasks before saving
        validate_tasks(tasks, user_id)
        save_tasks(tasks, user_id)
        return jsonify({'success': True})
    except ValidationError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        print(f"Error saving tasks: {e}")
        return jsonify({'error': 'Failed to save tasks'}), 500

@app.route('/api/categories', methods=['GET'])
@login_required
def get_categories():
    """Get all categories for current user."""
    user_id = get_current_user_id()
    categories = load_categories_from_db(user_id)
    return jsonify(categories)

@app.route('/api/categories', methods=['POST'])
@login_required
def post_categories():
    """Save categories for current user."""
    user_id = get_current_user_id()
    try:
        categories = request.get_json(silent=True)
        if categories is None:
            return jsonify({'error': 'Invalid JSON payload'}), 400

        # Validate categories before saving
        validate_categories(categories, user_id)
        save_categories(categories, user_id)
        return jsonify({'success': True})
    except ValidationError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        print(f"Error saving categories: {e}")
        return jsonify({'error': 'Failed to save categories'}), 500

if __name__ == '__main__':
    print(f'ToDo app running at http://localhost:{PORT}')
    app.run(host='0.0.0.0', port=PORT, debug=False)
