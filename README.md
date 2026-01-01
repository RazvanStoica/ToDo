# ToDo App

A simple web-based task manager with priority levels and timestamps, backed by PostgreSQL.

## Requirements

- Python 3
- PostgreSQL

## Setup

1. Install dependencies:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install psycopg2-binary
   ```

2. Create config file:
   ```bash
   cp config.example.json config.json
   ```
   Edit `config.json` with your database connection details.

3. Create the database and table:
   ```bash
   createdb todo
   psql -d todo -c "
   CREATE TABLE tasks (
       id BIGINT PRIMARY KEY,
       text TEXT NOT NULL,
       completed BOOLEAN DEFAULT FALSE,
       priority VARCHAR(10) DEFAULT 'medium',
       created_at TIMESTAMPTZ,
       completed_at TIMESTAMPTZ
   );"
   ```

## Running the App

```bash
source venv/bin/activate
python3 server.py
```

Then open http://localhost:3000 in your browser.

## Features

- **Add tasks** with priority levels
- **Mark tasks** as complete/incomplete
- **Delete tasks**
- **Timestamps** for creation and completion
- **Color-coded priorities** - task boxes are colored by importance

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
