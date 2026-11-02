CREATE TABLE jobs (
    id VARCHAR(36) NOT NULL PRIMARY KEY,
    handler_id VARCHAR(80) NOT NULL,
    idempotency_key VARCHAR(128) NOT NULL,
    payload_sha256 VARCHAR(64) NOT NULL,
    payload_json TEXT NOT NULL,
    status VARCHAR(32) NOT NULL,
    result_json TEXT,
    error_code VARCHAR(80),
    attempt INTEGER NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    CONSTRAINT uq_jobs_handler_idempotency UNIQUE (handler_id, idempotency_key)
);
CREATE INDEX ix_jobs_created_at ON jobs (created_at);
CREATE TABLE job_events (
    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    job_id VARCHAR(36) NOT NULL,
    status VARCHAR(32) NOT NULL,
    diagnostic_code VARCHAR(80),
    created_at DATETIME NOT NULL,
    FOREIGN KEY(job_id) REFERENCES jobs (id) ON DELETE CASCADE
);
CREATE INDEX ix_job_events_job_created ON job_events (job_id, created_at);
