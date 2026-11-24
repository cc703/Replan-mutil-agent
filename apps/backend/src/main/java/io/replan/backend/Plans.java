package io.replan.backend;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.springframework.stereotype.Component;

@Component
class Plans {
    record Prepared(long revision, JsonNode evidence, String planHash, String instanceHash, ArrayNode eventIds) {}

    private final Db db;
    private final World world;
    private final Jobs jobs;
    private final Scheduler scheduler;
    private final Approval approval;

    Plans(Db db, World world, Jobs jobs, Scheduler scheduler, Approval approval) {
        this.db = db;
        this.world = world;
        this.jobs = jobs;
        this.scheduler = scheduler;
        this.approval = approval;
    }

    Prepared prepare(JsonNode lab, JsonNode body, boolean rollback, String trace) {
        if (!body.hasNonNull("confirmation_id")) {
            throw new ApiFailure(428,"CONFIRMATION_REQUIRED","A confirmation is required");
        }
        int base = Input.integer(body,"base_version_no");
        World.base(lab,base);
        String labId = lab.path("id").asText();
        long revision = lab.path("revision").asLong();
        if (rollback) {
            ArrayNode facts = world.facts(labId);
            int target = Input.integer(body,"target_version_no");
            approval.verify(lab,body,"PLAN_ROLLBACK",db.object("target_version_no",target,"base_version_no",base));
            JsonNode result = rollbackResult(lab,target,facts,trace);
            return new Prepared(revision,result.path("evidence"),result.path("plan_sha256").asText(),
                    result.path("instance_post_sha256").asText(),world.eventIds(facts));
        }
        JsonNode job = jobs.get(labId,Input.string(body,"job_id"));
        if (job.path("base_version_no").asInt(-1) != base && job.hasNonNull("base_version_no"))
            throw ApiFailure.conflict("STALE_BASE_VERSION","Job belongs to another base version");
        JsonNode candidate = candidate(job,Input.string(body,"candidate_id"));
        JsonNode eventIds = job.path("snapshot").path("event_ids");
        JsonNode evidence = candidate.path("evidence");
        String hash = candidate.path("plan_sha256").asText();
        approval.verify(lab,body,"PLAN_COMMIT",db.object("job_id",job.path("id"),"candidate_id",
                candidate.path("candidate_id"),"base_version_no",base,"plan_sha256",hash));
        requireUsableCandidate(lab,job,candidate,trace);
        return new Prepared(revision,evidence,hash,job.path("result").path("instance_post_sha256").asText(),
                (ArrayNode) eventIds);
    }

    JsonNode rollbackResult(JsonNode lab, int targetNumber, ArrayNode facts, String trace) {
        if (lab.path("active_version_no").asInt() == 0)
            throw new ApiFailure(422,"ROLLBACK_INFEASIBLE","No active plan exists");
        String labId = lab.path("id").asText();
        JsonNode active = world.evidence(lab);
        JsonNode targetVersion = world.version(labId,targetNumber);
        JsonNode target = targetVersion.path("evidence");
        if (!scheduler.valid(target,targetVersion.path("plan_sha256").asText(),db.json.createArrayNode(),trace))
            throw new ApiFailure(422,"PLAN_INTEGRITY_ERROR","Archived rollback target failed validation");
        JsonNode result = scheduler.post("/rollback",db.object("instance",active.path("instance"),
                "base_plan",active.path("plan"),"target_plan",target.path("plan"),
                "events",world.payloads(facts,db.json.createArrayNode()),"revision",lab.path("revision")),trace);
        if (!result.path("validation").path("passed").asBoolean() ||
                !scheduler.valid(result.path("evidence"),result.path("plan_sha256").asText(),
                        db.json.createArrayNode(),trace)) {
            throw new ApiFailure(422,"ROLLBACK_INFEASIBLE","Rollback did not pass independent validation");
        }
        return result;
    }

    JsonNode apply(JsonNode lab, JsonNode body, Prepared prepared, boolean rollback) {
        int base = Input.integer(body,"base_version_no");
        World.base(lab,base);
        if (lab.path("revision").asLong() != prepared.revision()) {
            throw ApiFailure.conflict("STALE_BASE_VERSION","Confirmed facts changed during validation");
        }
        String labId = lab.path("id").asText();
        String actor = Input.string(body,"actor");
        String jobId = null;
        String source = "ROLLBACK";
        if (rollback) {
            approval.consume(lab,body,"PLAN_ROLLBACK",db.object("target_version_no",
                    Input.integer(body,"target_version_no"),"base_version_no",base));
        } else {
            jobId = Input.string(body,"job_id");
            String candidateId = Input.string(body,"candidate_id");
            JsonNode job = jobs.get(labId,jobId);
            candidate(job,candidateId);
            source = job.path("kind").asText();
            approval.consume(lab,body,"PLAN_COMMIT",db.object("job_id",jobId,"candidate_id",candidateId,
                    "base_version_no",base,"plan_sha256",prepared.planHash()));
            db.write("UPDATE job SET status='COMMITTED' WHERE lab_id=:lab AND id=:id","lab",labId,"id",jobId);
        }
        for (JsonNode event : prepared.eventIds()) {
            db.write("UPDATE event SET status='APPLIED' WHERE lab_id=:lab AND id=:id","lab",labId,"id",event.asText());
        }
        for (JsonNode stale : db.rows("SELECT id FROM job WHERE lab_id=:lab AND status='SUCCEEDED'","lab",labId)) {
            jobs.transition(labId,stale.path("id").asText(),"STALE",actor);
        }
        if (rollback && world.facts(labId).isEmpty()) {
            for (JsonNode queued : db.rows("SELECT id FROM job WHERE lab_id=:lab AND status='QUEUED'","lab",labId)) {
                jobs.transition(labId,queued.path("id").asText(),"STALE",actor);
            }
        }
        db.write("UPDATE plan_version SET status='SUPERSEDED' WHERE lab_id=:lab AND status='ACTIVE'","lab",labId);
        db.write("""
                INSERT INTO plan_version(lab_id,version_no,parent_version_no,status,source,job_id,evidence,
                plan_sha256,instance_sha256,created_by)
                VALUES (:lab,:version,:parent,'ACTIVE',:source,:job,CAST(:evidence AS jsonb),:hash,:instance,:actor)
                ""","lab",labId,"version",base+1,"parent",base == 0 ? null : base,"source",source,
                "job",jobId,"evidence",prepared.evidence(),"hash",prepared.planHash(),"instance",prepared.instanceHash(),"actor",actor);
        db.write("UPDATE lab SET active_version_no=:version WHERE id=:lab","version",base+1,"lab",labId);
        world.audit(labId,actor,rollback ? "PLAN_ROLLBACK" : "PLAN_COMMIT","plan_version",String.valueOf(base+1),
                db.object("parent_version_no",base,"job_id",jobId,"plan_sha256",prepared.planHash()));
        if (base == 0 && !world.facts(labId).isEmpty()) jobs.queue(labId,"REPLAN",null,"initial-commit");
        return world.versionDto(world.version(labId,base+1));
    }

    JsonNode candidate(JsonNode job, String id) {
        if (!jobs.committable(job))
            throw ApiFailure.conflict("JOB_NOT_COMMITTABLE","Job has no committable result");
        for (JsonNode candidate : jobs.candidates(job)) {
            if (id.equals(candidate.path("candidate_id").asText())) return candidate;
        }
        throw ApiFailure.conflict("CANDIDATE_NOT_FOUND","Candidate is absent from the job");
    }

    void requireUsableCandidate(JsonNode lab, JsonNode job, JsonNode candidate, String trace) {
        World.base(lab,job.path("base_version_no").asInt(-1));
        if (!jobs.validCandidate(job,candidate,jobs.candidateFacts(lab,job),trace)) {
            throw new ApiFailure(422,"VALIDATION_FAILED","Candidate is unsafe in the current world");
        }
    }

    boolean versionUsable(JsonNode version, String trace) {
        JsonNode evidence = version.path("evidence");
        String hash = version.path("plan_sha256").asText();
        if (!scheduler.valid(evidence,hash,db.json.createArrayNode(),trace)) {
            throw new ApiFailure(422,"PLAN_INTEGRITY_ERROR","Archived plan failed validation");
        }
        if (!version.path("status").asText().equals("ACTIVE")) return true;
        ArrayNode facts = world.facts(version.path("lab_id").asText());
        return facts.isEmpty() || scheduler.valid(evidence,hash,
                world.payloads(facts,db.json.createArrayNode()),trace);
    }

    JsonNode read(JsonNode lab, int number, String trace) {
        String labId = lab.path("id").asText();
        JsonNode row = world.version(labId,number);
        JsonNode evidence = row.path("evidence");
        ObjectNode dto = world.versionDto(row);
        if (!versionUsable(row,trace)) {
            dto.put("status","NEEDS_REPLAN");
        } else {
            dto.set("plan",evidence.path("plan"));
            dto.set("plan_sha256",row.path("plan_sha256"));
            dto.set("view",scheduler.post("/view",evidence,trace));
        }
        return dto;
    }
}
