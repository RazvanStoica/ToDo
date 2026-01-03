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

-- Categories table for organizing tasks
CREATE TABLE IF NOT EXISTS categories (
    id BIGINT PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for efficient user category lookups
CREATE INDEX IF NOT EXISTS idx_categories_user_id ON categories(user_id);

-- Add category_id to tasks (nullable - tasks can be uncategorized)
-- Note: Run this as ALTER TABLE if tasks table already exists
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'tasks' AND column_name = 'category_id') THEN
        ALTER TABLE tasks ADD COLUMN category_id BIGINT REFERENCES categories(id) ON DELETE SET NULL;
    END IF;
END $$;
