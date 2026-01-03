# ToDo App

A simple web-based task manager with priority levels, timestamps, and Google OAuth authentication. Each user has their own private task list. Backed by PostgreSQL.

## Requirements

- Python 3
- PostgreSQL

Or use Docker (see below).

## Docker Setup (Recommended)

1. Create environment file:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` with your Google OAuth credentials (see [Google OAuth Setup](#google-oauth-setup)).

2. Run with Docker Compose:
   ```bash
   docker-compose up -d
   ```

This starts both the app and PostgreSQL. Open http://localhost:3000.

To stop:
```bash
docker-compose down
```

To stop and remove data:
```bash
docker-compose down -v
```

## Manual Setup

1. Install dependencies:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. Create config file:
   ```bash
   cp config.example.json config.json
   ```
   Edit `config.json` with your database connection details and OAuth configuration.

3. Create the database and tables:
   ```bash
   createdb todo
   psql -d todo -f init.sql
   ```

## Google OAuth Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Navigate to **APIs & Services > Credentials**
4. Click **Create Credentials > OAuth client ID**
5. Select **Web application**
6. Add authorized redirect URI: `http://localhost:3000/auth/google/callback`
7. Copy the Client ID and Client Secret

Add credentials to `config.json`:
```json
{
  "oauth": {
    "google_client_id": "your-client-id.apps.googleusercontent.com",
    "google_client_secret": "your-client-secret",
    "redirect_uri": "http://localhost:3000/auth/google/callback"
  },
  "auth": {
    "email_whitelist": ["user1@example.com", "user2@example.com"],
    "allow_any_email": false
  }
}
```

Or use environment variables (recommended for production):
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `SECRET_KEY`
- `OAUTH_REDIRECT_URI`

## Access Control

The app uses email whitelisting to control access:

- **email_whitelist**: List of allowed email addresses
- **allow_any_email**: Set to `true` to allow any Google account (bypasses whitelist)

Users not on the whitelist will see an "Access Denied" page after attempting to sign in.

## Running the App

```bash
source venv/bin/activate
python3 server.py
```

Then open http://localhost:3000 in your browser.

## Features

- **Google OAuth** - Secure authentication with Google accounts
- **Private task lists** - Each user has their own tasks
- **Email whitelist** - Control who can access the app
- **Add tasks** with priority levels
- **Edit tasks** inline by clicking the Edit button
- **Mark tasks** as complete/incomplete
- **Delete tasks**
- **Change priority** using colored buttons on hover
- **Search tasks** by text
- **Filter tasks** by All, Active, or Completed
- **Pagination** - automatic pagination when more than 20 tasks
- **Timestamps** for creation and completion
- **Color-coded priorities** - task boxes are colored by importance
- **Smart sorting** - tasks sorted by priority (high to low), then by date

## Setting Priority

Use text prefixes when adding a task:

| Prefix | Priority |
|--------|----------|
| `!h` or `!high` | High (red) |
| `!m` or `!medium` | Medium (orange) |
| `!l` or `!low` | Low (green) |

**Examples:**
- `!h Call the doctor` - creates a high priority task
- `!l Water plants` - creates a low priority task
- `Buy groceries` - defaults to medium priority

You can also change the priority of existing tasks by hovering over a task and clicking the colored priority buttons.

## Keyboard Shortcuts

When editing a task:
- **Enter** - save changes
- **Escape** - cancel editing

## Testing

Run the unit tests:
```bash
source venv/bin/activate
pip install pytest pytest-cov
python -m pytest test_server.py -v
```

Run with coverage:
```bash
python -m pytest test_server.py --cov=server --cov-report=term-missing
```

## Production Deployment

For production:
1. Use HTTPS (required by Google OAuth)
2. Set a strong `SECRET_KEY` environment variable
3. Use a production WSGI server (e.g., Gunicorn)
4. Update the OAuth redirect URI to your production domain
