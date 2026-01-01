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
