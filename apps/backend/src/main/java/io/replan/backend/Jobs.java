package io.replan.backend;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.util.Set;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

@Component
class Jobs {
    private final Db db;
    private final World world;
    private final Scheduler scheduler;
    private final int mergeMs;

    Jobs(Db db, World world, Scheduler scheduler, @Value("${p7.merge-ms:500}") int mergeMs) {
        this.db = db;
        this.world = world;
        this.scheduler = scheduler;
        this.mergeMs = mergeMs;
    }

    JsonNode get(String lab, String id) {
        JsonNode job = db.one("SELECT * FROM job WHERE lab_id=:lab AND id=:id", "lab",lab,"id",id);
        if (job.isMissingNode()) throw ApiFailure.missing("Job");
        return job;
    }

    JsonNode queue(String lab, String kind, JsonNode params, String trace) {
        db.write("""
                INSERT INTO job(lab_id,id,kind,status,params,trace_id,not_before,base_version_no)
                SELECT id,:id,:kind,'QUEUED',CAST(:params AS jsonb),:trace,
                clock_timestamp() + :merge * interval '1 millisecond',active_version_no FROM lab WHERE id=:lab
                ON CONFLICT (lab_id) WHERE status='QUEUED' DO NOTHING
                ""","lab",lab,"id",World.id(),"kind",kind,"params",params,"trace",trace,"merge",mergeMs);
        return db.one("SELECT id AS job_id,status FROM job WHERE lab_id=:lab AND status='QUEUED'","lab",lab);
    }

    @Transactional
    public JsonNode claim() {
        JsonNode lab = db.one("""
                SELECT l.* FROM lab l JOIN job j ON j.lab_id=l.id
                WHERE j.status='QUEUED' AND j.not_before <= clock_timestamp()
                AND NOT EXISTS (SELECT 1 FROM job x WHERE x.lab_id=l.id AND x.status IN ('RUNNING','SUCCEEDED'))
                ORDER BY j.created_at,j.id LIMIT 1 FOR UPDATE OF l SKIP LOCKED
                """);
        if (lab.isMissingNode()) return lab;
        String labId = lab.path("id").asText();
        JsonNode job = db.one("SELECT * FROM job WHERE lab_id=:lab AND status='QUEUED'","lab",labId);
        if (job.isMissingNode() || !db.one("""
                SELECT count(*) AS n FROM job WHERE lab_id=:lab AND status IN ('RUNNING','SUCCEEDED')
                ""","lab",labId).path("n").asText().equals("0")) return db.json.missingNode();
        String id = job.path("id").asText();
        int version = lab.path("active_version_no").asInt();
        JsonNode evidence = world.evidence(lab);
        ArrayNode facts = db.json.createArrayNode();
        if (version > 0) {
            facts = db.rows("SELECT id,payload FROM event WHERE lab_id=:lab AND " + World.OPEN
                    + " ORDER BY seq LIMIT 50","lab",labId);
        }
        for (JsonNode fact : facts) {
            db.write("UPDATE event SET status='BATCHED',job_id=:job WHERE lab_id=:lab AND id=:event",
                    "job",id,"lab",labId,"event",fact.path("id").asText());
        }
        String kind = version == 0 ? "INITIAL" : "REPLAN";
        ObjectNode snapshot = db.object("instance",evidence.path("instance"),"base_plan",evidence.path("plan"),
                "event_ids",world.eventIds(facts),"events",world.payloads(facts,db.json.createArrayNode()));
        db.write("""
                UPDATE job SET kind=:kind, status='RUNNING',base_version_no=:base,claimed_revision=:revision,
                snapshot=CAST(:snapshot AS jsonb),started_at=clock_timestamp() WHERE lab_id=:lab AND id=:id
                ""","kind",kind,"base",version,"revision",lab.path("revision").asLong(),"snapshot",snapshot,
                "lab",labId,"id",id);
        if (version > 0 && world.facts(labId).size() > facts.size()) {
            queue(labId,"REPLAN",null,job.path("trace_id").asText());
        }
        world.audit(labId,"worker","JOB_STARTED","job",id,db.object("event_ids",snapshot.path("event_ids")));
        return get(labId,id);
    }

    JsonNode solve(JsonNode job) {
        JsonNode snapshot = job.path("snapshot");
        boolean initial = job.path("kind").asText().equals("INITIAL");
        ObjectNode payload = db.object("instance",snapshot.path("instance"),"revision",job.path("claimed_revision"));
        if (job.hasNonNull("params")) payload.set("params",job.path("params"));
        if (!initial) {
            payload.set("base_plan",snapshot.path("base_plan"));
            payload.set("events",snapshot.path("events"));
        }
        JsonNode result = scheduler.post(initial ? "/initial" : "/replan",payload,job.path("trace_id").asText());
        if (!Set.of("OK","INFEASIBLE","TIMEOUT").contains(result.path("result_status").asText())) {
            throw new ApiFailure(502,"SCHEDULER_UNAVAILABLE","Scheduler returned an unsupported result");
        }
        return result;
    }

    @Transactional
    public void finish(JsonNode claimed, JsonNode result, JsonNode error) {
        String lab = claimed.path("lab_id").asText(), id = claimed.path("id").asText();
        JsonNode current = world.lab(lab,true);
        JsonNode job = get(lab,id);
        if (!job.path("status").asText().equals("RUNNING")) return;
        if (job.path("base_version_no").asInt() != current.path("active_version_no").asInt()) {
            transition(lab,id,"STALE","worker");
            return;
        }
        String status = error == null ? "SUCCEEDED" : "FAILED";
        if (result != null) {
            persistCandidates(lab,id,result.path("candidates"));
            ObjectNode metadata = result.deepCopy();
            metadata.remove("candidates");
            result = metadata;
        }
        db.write("""
                UPDATE job SET status=:status,result_status=:result_status,result=CAST(:result AS jsonb),
                error=CAST(:error AS jsonb),finished_at=clock_timestamp() WHERE lab_id=:lab AND id=:id
                ""","status",status,"result_status",result == null ? null : result.path("result_status").asText(),
                "result",result,"error",error,"lab",lab,"id",id);
        if (error != null) release(lab,id);
        world.audit(lab,"worker","JOB_" + status,"job",id,error);
    }

    void transition(String lab, String id, String status, String actor) {
        db.write("""
                UPDATE job SET status=:status,finished_at=COALESCE(finished_at,clock_timestamp())
                WHERE lab_id=:lab AND id=:id
                ""","status",status,"lab",lab,"id",id);
        release(lab,id);
        world.audit(lab,actor,"JOB_" + status,"job",id,null);
    }

    private void release(String lab, String id) {
        db.write("UPDATE event SET status='RELEASED' WHERE lab_id=:lab AND job_id=:id AND status='BATCHED'",
                "lab",lab,"id",id);
    }

    @Transactional
    public void recover() {
        for (JsonNode job : db.rows("SELECT * FROM job WHERE status='RUNNING' ORDER BY lab_id")) {
            finish(job,null,db.object("code","WORKER_RESTARTED","message","Worker restarted during execution"));
        }
    }

    private void persistCandidates(String lab, String job, JsonNode candidates) {
        int ordinal = 0;
        for (JsonNode candidate : candidates) {
            String id = candidate.path("candidate_id").asText();
            if (id.isBlank()) continue;
            db.write("""
                    INSERT INTO candidate(lab_id,job_id,id,ordinal,body)
                    VALUES(:lab,:job,:id,:ordinal,CAST(:body AS jsonb))
                    ON CONFLICT (lab_id,job_id,id) DO NOTHING
                    ""","lab",lab,"job",job,"id",id,"ordinal",++ordinal,"body",candidate);
        }
    }

    ArrayNode candidates(JsonNode job) {
        ArrayNode candidates = db.json.createArrayNode();
        db.rows("SELECT body FROM candidate WHERE lab_id=:lab AND job_id=:job ORDER BY ordinal",
                "lab",job.path("lab_id").asText(),"job",job.path("id").asText())
            .forEach(row -> candidates.add(row.path("body")));
        return candidates;
    }

    boolean committable(JsonNode job) {
        return job.path("status").asText().equals("SUCCEEDED")
                && job.path("result_status").asText().equals("OK");
    }

    ArrayNode candidateFacts(JsonNode lab, JsonNode job) {
        return world.payloads(world.facts(lab.path("id").asText()),job.path("snapshot").path("event_ids"));
    }

    boolean validCandidate(JsonNode job, JsonNode candidate, ArrayNode additional, String trace) {
        JsonNode evidence = candidate.path("evidence");
        JsonNode snapshot = job.path("snapshot");
        boolean initial = job.path("kind").asText().equals("INITIAL");
        if (!snapshot.path("event_ids").isArray() || !candidate.path("validation").path("passed").asBoolean()
                || !evidence.path("instance").isObject() || !evidence.path("plan").isObject()
                || !evidence.path("revision").isIntegralNumber()
                || !evidence.path("revision").equals(job.path("claimed_revision"))
                || !evidence.path("base_plan").equals(snapshot.path("base_plan"))
                || !candidate.path("candidate_id").equals(evidence.path("plan").path("id"))) {
            return false;
        }
        if (initial ? !(evidence.path("free").isNull() && evidence.path("context").isNull())
                : !(evidence.path("base_plan").isObject() && evidence.path("free").isArray()
                  && evidence.path("context").isObject())) {
            return false;
        }
        return scheduler.valid(evidence,candidate.path("plan_sha256").asText(),additional,trace);
    }

    ObjectNode response(JsonNode job, JsonNode lab, boolean eligibility, String trace) {
        JsonNode result = job.path("result");
        ArrayNode shown = db.json.createArrayNode();
        if (eligibility && committable(job)
                && job.path("base_version_no").asInt() == lab.path("active_version_no").asInt()) {
            ArrayNode additional = candidateFacts(lab,job);
            for (JsonNode candidate : candidates(job)) {
                if (validCandidate(job,candidate,additional,trace)) {
                    ObjectNode dto = candidate.deepCopy();
                    dto.remove(java.util.List.of("evidence","plan"));
                    dto.set("view",scheduler.post("/view",candidate.path("evidence"),trace));
                    shown.add(dto);
                }
            }
        }
        String resultStatus = job.path("result_status").asText();
        return db.object("job_id",job.path("id"),"kind",job.path("kind"),"status",job.path("status"),
                "result_status",job.path("result_status"),"base_version_no",job.path("base_version_no"),
                "event_ids",job.path("snapshot").path("event_ids").isArray() ? job.path("snapshot").path("event_ids") : db.json.createArrayNode(),
                "created_at",job.path("created_at"),"started_at",job.path("started_at"),"finished_at",job.path("finished_at"),
                "error",job.path("error"),"candidates",shown,"conflict",resultStatus.equals("INFEASIBLE") ? result.path("conflict") : null,
                "relaxations",resultStatus.equals("INFEASIBLE") ? result.path("relaxations") : db.json.createArrayNode(),
                "solver",result.path("solver"));
    }
}
