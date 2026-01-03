-- Users table for OAuth authentication
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    google_id VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    picture_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_login TIMESTAMPTZ DEFAULT NOW()
);

-- Tasks table with user association
CREATE TABLE IF NOT EXISTS tasks (
    id BIGINT PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    completed BOOLEAN DEFAULT FALSE,
    priority VARCHAR(10) DEFAULT 'medium',
    created_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

-- Index for efficient user task lookups
CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks(user_id);
