CREATE TABLE candidate (
    lab_id text NOT NULL, job_id text NOT NULL, id text NOT NULL, ordinal integer NOT NULL,
    body jsonb NOT NULL,
    PRIMARY KEY (lab_id,job_id,id),
    UNIQUE (lab_id,job_id,ordinal),
    FOREIGN KEY (lab_id,job_id) REFERENCES job(lab_id,id)
);

INSERT INTO candidate(lab_id,job_id,id,ordinal,body)
SELECT j.lab_id,j.id,c.entry->>'candidate_id',c.ordinality,c.entry
FROM job j CROSS JOIN LATERAL jsonb_array_elements(j.result->'candidates') WITH ORDINALITY AS c(entry,ordinality)
WHERE c.entry->>'candidate_id' IS NOT NULL
ON CONFLICT (lab_id,job_id,id) DO NOTHING;

UPDATE job SET result = result - 'candidates' WHERE result ? 'candidates';
