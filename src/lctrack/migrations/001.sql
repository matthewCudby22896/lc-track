CREATE TABLE IF NOT EXISTS problems (
    title_slug TEXT PRIMARY KEY,
    ui_id INTEGER NOT NULL UNIQUE, /* May be an issue when updating problem ui_id */
    slug TEXT NOT NULL UNIQUE,
    title TEXT,
    difficulty INTEGER CHECK (difficulty BETWEEN 0 AND 2),
    last_review_at INTEGER,
    next_review_at INTEGER DEFAULT 0,
    EF REAL DEFAULT 2.5,
    I INTEGER DEFAULT 0,
    n INTEGER DEFAULT 0,
    active BOOLEAN DEFAULT 0
);

CREATE TABLE IF NOT EXISTS topics (
    topic_slug TEXT PRIMARY KEY,
    topic_title TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS problem_topic (
    problem_id INTEGER NOT NULL,
    topic_slug TEXT NOT NULL,
    PRIMARY KEY (problem_id, topic_slug),
    FOREIGN KEY (problem_id) REFERENCES problems(id) ON DELETE CASCADE,
    FOREIGN KEY (topic_slug) REFERENCES topics(topic_slug) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS entries(
    uuid TEXT PRIMARY KEY,
    problem_id INTEGER NOT NULL,
    confidence INTEGER NOT NULL CHECK (confidence BETWEEN 0 and 5),
    ts INTEGER NOT NULL,
    FOREIGN KEY (problem_id) references problems(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS app_state (
    key TEXT PRIMARY KEY,
    value TEXT
);