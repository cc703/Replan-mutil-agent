package io.replan.backend;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.springframework.stereotype.Component;
import org.springframework.transaction.support.TransactionTemplate;

@Component
class Writes {
    record Reply(int status, JsonNode body, boolean replay) {}

    private final Db db;
    private final World world;
    private final Scheduler scheduler;
    private final Approval approval;
    private final Facts facts;
    private final Jobs jobs;
    private final Plans plans;
    private final TransactionTemplate tx;

    Writes(Db db, World world, Scheduler scheduler, Approval approval, Facts facts, Jobs jobs,
           Plans plans, TransactionTemplate tx) {
        this.db = db;
        this.world = world;
        this.scheduler = scheduler;
        this.approval = approval;
        this.facts = facts;
        this.jobs = jobs;
        this.plans = plans;
        this.tx = tx;
    }

    Reply submit(String labId, String path, String key, JsonNode body, String trace) {
        if (key == null || key.isBlank() || key.length() > 128)
            throw ApiFailure.invalid("Idempotency-Key must be 1 to 128 characters");
        String scope = labId == null ? "labs" : labId;
        JsonNode request = db.object("method","POST","path",path,"body",body);
        String previewAction = path.equals("confirmations") ? body.path("action").asText() : "";
        boolean planPreview = previewAction.equals("PLAN_COMMIT") || previewAction.equals("PLAN_ROLLBACK");
        Reply saved = planPreview ? null : replay(scope,key,request);
        if (saved != null) return saved;
        boolean rollback = path.equals("plans/rollback");
        boolean commit = path.equals("plans/commit");
        Plans.Prepared prepared = null;
        if (commit || rollback) {
            if (commit) Input.fields(body,"job_id","candidate_id","base_version_no","confirmation_id","actor");
            else Input.fields(body,"target_version_no","base_version_no","confirmation_id","actor");
            try {
                prepared = plans.prepare(world.lab(labId,false),body,rollback,trace);
            } catch (ApiFailure failure) {
                Reply concurrentReplay = replay(scope,key,request);
                if (concurrentReplay != null) return concurrentReplay;
                throw failure;
            }
        }
        Plans.Prepared immutable = prepared;
        return tx.execute(state -> {
            if (labId == null) {
                db.one("SELECT 1 AS locked FROM pg_advisory_xact_lock(hashtext(:scope))","scope","p7-lab-collection");
            }
            JsonNode lab = labId == null ? null : world.lab(labId,true);
            Reply duplicate = replay(scope,key,request);
            if (duplicate != null) {
                if (previewAction.equals("PLAN_COMMIT")) previewCandidate(lab,Input.object(body,"payload"),trace);
                if (previewAction.equals("PLAN_ROLLBACK")) previewRollback(lab,Input.object(body,"payload"),trace);
                return duplicate;
            }
            Reply reply = immutable == null ? route(lab,path,body,trace) : response(201,plans.apply(lab,body,immutable,rollback));
            db.write("""
                    INSERT INTO idempotency(scope,key,request,status_code,response)
                    VALUES (:scope,:key,CAST(:request AS jsonb),:status,CAST(:response AS jsonb))
                    ""","scope",scope,"key",key,"request",request,"status",reply.status(),"response",reply.body());
            return reply;
        });
    }

    private Reply replay(String scope, String key, JsonNode request) {
        JsonNode row = db.one("""
                SELECT status_code, response, request=CAST(:request AS jsonb) AS matched
                FROM idempotency WHERE scope=:scope AND key=:key
                ""","scope",scope,"key",key,"request",request);
        if (row.isMissingNode()) return null;
        if (!row.path("matched").asBoolean())
            throw ApiFailure.conflict("IDEMPOTENCY_KEY_REUSED","Idempotency key already identifies another request");
        return new Reply(row.path("status_code").asInt(),row.path("response"),true);
    }

    private Reply route(JsonNode lab, String action, JsonNode body, String trace) {
        if (lab == null) return response(201,createLab(body,trace));
        String labId = lab.path("id").asText();
        return switch (action) {
            case "plans/initial" -> {
                Input.fields(body,"params");
                if (lab.path("active_version_no").asInt() != 0) throw ApiFailure.conflict("LAB_BUSY","Initial plan exists");
                rejectBusy(labId);
                yield response(202,jobs.queue(labId,"INITIAL",body.has("params") ? Input.object(body,"params") : null,trace));
            }
            case "events" -> {
                Input.fields(body,"client_event_id","event","confirmation_id","actor");
                yield response(202,facts.record(lab,body,false,trace));
            }
            case "constraints" -> {
                Input.fields(body,"ir_item_id","confirmation_id","actor");
                yield response(202,facts.record(lab,body,true,trace));
            }
            case "confirmations" -> response(201,confirmation(lab,body,trace));
            case "agent/turn" -> {
                Input.fields(body,"session_id","text","actor");
                yield response(200,facts.turn(lab,body,trace));
            }
            case "jobs/retry" -> {
                Input.fields(body,"actor");
                String actor = Input.string(body,"actor");
                rejectBusy(labId);
                if (world.facts(labId).isEmpty() && lab.path("active_version_no").asInt() > 0)
                    throw ApiFailure.conflict("LAB_BUSY","No unincorporated work remains");
                JsonNode result = jobs.queue(labId,lab.path("active_version_no").asInt() == 0 ? "INITIAL" : "REPLAN",null,trace);
                world.audit(labId,actor,"JOB_RETRY","job",result.path("job_id").asText(),null);
                yield response(202,result);
            }
            default -> dynamic(lab,action,body);
        };
    }

    private Reply dynamic(JsonNode lab, String action, JsonNode body) {
        String[] parts = action.split("/");
        String labId = lab.path("id").asText();
        if (parts.length == 3 && parts[0].equals("confirmations")
                && (parts[2].equals("confirm") || parts[2].equals("reject"))) {
            Input.fields(body,"actor","payload_hash");
            return response(200,approval.decide(lab,parts[1],body,parts[2].equals("confirm")));
        }
        if (parts.length == 3 && parts[0].equals("jobs") && parts[2].equals("discard")) {
            Input.fields(body,"actor","reason");
            String reason = Input.string(body,"reason");
            String actor = Input.string(body,"actor");
            JsonNode job = jobs.get(labId,parts[1]);
            if (!job.path("status").asText().equals("SUCCEEDED"))
                throw ApiFailure.conflict("JOB_NOT_COMMITTABLE","Only undecided work may be discarded");
            jobs.transition(labId,parts[1],"DISCARDED",actor);
            world.audit(labId,actor,"JOB_DISCARD_REASON","job",parts[1],db.object("reason",reason));
            return response(200,db.object("job_id",parts[1],"status","DISCARDED"));
        }
        throw ApiFailure.missing("Endpoint");
    }

    private JsonNode createLab(JsonNode body, String trace) {
        Input.fields(body,"name","instance");
        String name = Input.string(body,"name");
        JsonNode instance = Input.object(body,"instance");
        JsonNode checked = scheduler.post("/instances/check",db.object("instance",instance),trace);
        if (!checked.path("ok").asBoolean())
            throw new ApiFailure(400,"INVALID_INSTANCE","Instance check failed");
        String id = World.id();
        db.write("""
                INSERT INTO lab(id,name,instance,instance_sha256,summary)
                VALUES (:id,:name,CAST(:instance AS jsonb),:hash,CAST(:summary AS jsonb))
                ""","id",id,"name",name,"instance",instance,"hash",checked.path("instance_sha256").asText(),
                "summary",checked.path("summary"));
        world.audit(id,"local","LAB_CREATED","lab",id,null);
        return world.labDto(world.lab(id,false));
    }

    private JsonNode confirmation(JsonNode lab, JsonNode body, String trace) {
        Input.fields(body,"action","level","payload","actor","ttl_s");
        String labId = lab.path("id").asText();
        String action = Input.string(body,"action");
        JsonNode payload = Input.object(body,"payload");
        ObjectNode preview = db.object("payload",payload);
        switch (action) {
            case "EVENT_INJECT", "CONSTRAINT_CHANGE" -> {
                JsonNode event = payload;
                if (action.equals("EVENT_INJECT")) facts.checkEvent(event);
                else {
                    Input.fields(payload,"ir_item_id");
                    event = facts.constraint(labId,Input.string(payload,"ir_item_id"));
                }
                JsonNode inspected = facts.preview(lab,event,trace);
                preview.set("back_translation",inspected.path("back_translation"));
                preview.set("warnings",inspected.path("warnings"));
                preview.set("event_normalized",inspected.path("event_normalized"));
            }
            case "PLAN_COMMIT" -> {
                JsonNode candidate = previewCandidate(lab,payload,trace);
                for (String key : java.util.List.of("f1","f2","f3","diff","validation")) {
                    preview.set(key,candidate.path(key));
                }
            }
            case "PLAN_ROLLBACK" -> {
                JsonNode result = previewRollback(lab,payload,trace);
                preview.set("changes",result.path("changes"));
                preview.set("validation",result.path("validation"));
            }
            default -> throw ApiFailure.invalid("Unknown confirmation action");
        }
        return approval.create(lab,body,preview,trace);
    }

    private JsonNode previewCandidate(JsonNode lab, JsonNode payload, String trace) {
        Input.fields(payload,"job_id","candidate_id","base_version_no","plan_sha256");
        int base = Input.integer(payload,"base_version_no");
        World.base(lab,base);
        JsonNode job = jobs.get(lab.path("id").asText(),Input.string(payload,"job_id"));
        JsonNode candidate = plans.candidate(job,Input.string(payload,"candidate_id"));
        if (base != job.path("base_version_no").asInt() ||
                !Input.string(payload,"plan_sha256").equals(candidate.path("plan_sha256").asText()))
            throw ApiFailure.conflict("CONFIRMATION_MISMATCH","Candidate evidence does not match");
        plans.requireUsableCandidate(lab,job,candidate,trace);
        return candidate;
    }

    private JsonNode previewRollback(JsonNode lab, JsonNode payload, String trace) {
        Input.fields(payload,"target_version_no","base_version_no");
        World.base(lab,Input.integer(payload,"base_version_no"));
        return plans.rollbackResult(lab,Input.integer(payload,"target_version_no"),
                world.facts(lab.path("id").asText()),trace);
    }

    private void rejectBusy(String lab) {
        if (!db.one("SELECT id FROM job WHERE lab_id=:lab AND status IN ('QUEUED','RUNNING','SUCCEEDED') LIMIT 1",
                "lab",lab).isMissingNode()) throw ApiFailure.conflict("LAB_BUSY","Lab already has outstanding work");
    }

    private Reply response(int status, JsonNode body) { return new Reply(status,body,false); }
}
