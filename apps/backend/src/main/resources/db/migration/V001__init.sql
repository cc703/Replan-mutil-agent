CREATE TABLE lab (
    id text PRIMARY KEY, name text NOT NULL, instance jsonb NOT NULL,
    instance_sha256 text NOT NULL, summary jsonb NOT NULL,
    active_version_no integer NOT NULL DEFAULT 0, revision bigint NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE job (
    lab_id text NOT NULL REFERENCES lab(id), id text NOT NULL, kind text NOT NULL,
    status text NOT NULL CHECK (status IN ('QUEUED','RUNNING','SUCCEEDED','FAILED','COMMITTED','DISCARDED','STALE')),
    base_version_no integer, claimed_revision bigint, params jsonb, snapshot jsonb, result jsonb,
    result_status text, error jsonb, trace_id text NOT NULL, not_before timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now(), started_at timestamptz, finished_at timestamptz,
    PRIMARY KEY (lab_id,id)
);
CREATE UNIQUE INDEX job_running ON job (lab_id) WHERE status='RUNNING';
CREATE UNIQUE INDEX job_queued ON job (lab_id) WHERE status='QUEUED';
CREATE UNIQUE INDEX job_undecided ON job (lab_id) WHERE status='SUCCEEDED';
CREATE TABLE confirmation (
    lab_id text NOT NULL REFERENCES lab(id), id text NOT NULL,
    action text NOT NULL, level text NOT NULL, payload jsonb NOT NULL, payload_hash text NOT NULL,
    preview jsonb NOT NULL, base_version_no integer NOT NULL,
    status text NOT NULL CHECK (status IN ('PENDING','CONFIRMED','REJECTED','CONSUMED')),
    requested_by text NOT NULL, confirmed_by text, expires_at timestamptz NOT NULL, consumed_at timestamptz,
    PRIMARY KEY (lab_id,id)
);
CREATE TABLE event (
    lab_id text NOT NULL REFERENCES lab(id), id text NOT NULL, seq bigserial NOT NULL,
    client_event_id text NOT NULL, payload jsonb NOT NULL, original jsonb NOT NULL,
    status text NOT NULL CHECK (status IN ('RECEIVED','BATCHED','APPLIED','RELEASED')),
    job_id text, confirmation_id text NOT NULL, created_by text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (lab_id,id), UNIQUE(lab_id,client_event_id),
    FOREIGN KEY (lab_id,job_id) REFERENCES job(lab_id,id),
    FOREIGN KEY (lab_id,confirmation_id) REFERENCES confirmation(lab_id,id)
);
CREATE INDEX event_order ON event (lab_id,seq);
CREATE TABLE plan_version (
    lab_id text NOT NULL REFERENCES lab(id), version_no integer NOT NULL, parent_version_no integer,
    status text NOT NULL CHECK(status IN ('ACTIVE','SUPERSEDED')), source text NOT NULL,
    job_id text, evidence jsonb NOT NULL, plan_sha256 text NOT NULL, instance_sha256 text NOT NULL,
    created_by text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (lab_id,version_no),
    FOREIGN KEY (lab_id,job_id) REFERENCES job(lab_id,id),
    FOREIGN KEY (lab_id,parent_version_no) REFERENCES plan_version(lab_id,version_no)
);
CREATE UNIQUE INDEX plan_active ON plan_version (lab_id) WHERE status='ACTIVE';
CREATE TABLE decision_log (
    id bigserial PRIMARY KEY, lab_id text NOT NULL REFERENCES lab(id), actor text NOT NULL,
    action text NOT NULL, subject_type text NOT NULL, subject_id text NOT NULL, details jsonb NOT NULL,
    at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE idempotency (
    scope text NOT NULL, key text NOT NULL, request jsonb NOT NULL, status_code integer NOT NULL,
    response jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(scope,key)
);
CREATE TABLE agent_session (
    lab_id text NOT NULL REFERENCES lab(id), id text NOT NULL, updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(lab_id,id)
);
CREATE TABLE ir_item (
    lab_id text NOT NULL, id text NOT NULL, session_id text NOT NULL, item jsonb NOT NULL,
    event_id text, created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(lab_id,id),
    FOREIGN KEY(lab_id,session_id) REFERENCES agent_session(lab_id,id),
    FOREIGN KEY(lab_id,event_id) REFERENCES event(lab_id,id)
);
