CREATE TABLE jobs (
 id TEXT PRIMARY KEY,
 owner TEXT NOT NULL,
 project TEXT NOT NULL,
 sha TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 state TEXT NOT NULL CHECK(state IN ('dispatching','dispatched','dispatch_unknown'))
);
CREATE INDEX jobs_owner ON jobs(owner, created_at);
