# ToDo App

A simple web-based task manager with priority levels and timestamps.

## Running the App

```bash
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

## Data Storage

Tasks are stored in `tasks.json` with the following structure:

```json
{
  "id": 1234567890,
  "text": "Task description",
  "completed": false,
  "priority": "high",
  "createdAt": "2025-01-01T12:00:00.000Z",
  "completedAt": "2025-01-01T13:00:00.000Z"
}
```
