CREATE TABLE IF NOT EXISTS tasks (
    id BIGINT PRIMARY KEY,
    text TEXT NOT NULL,
    completed BOOLEAN DEFAULT FALSE,
    priority VARCHAR(10) DEFAULT 'medium',
    created_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);
