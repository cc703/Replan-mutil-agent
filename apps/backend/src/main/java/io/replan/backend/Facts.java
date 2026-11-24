package io.replan.backend;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.springframework.stereotype.Component;

@Component
class Facts {
    private final Db db;
    private final World world;
    private final Scheduler scheduler;
    private final Approval approval;
    private final Jobs jobs;

    Facts(Db db, World world, Scheduler scheduler, Approval approval, Jobs jobs) {
        this.db = db;
        this.world = world;
        this.scheduler = scheduler;
        this.approval = approval;
        this.jobs = jobs;
    }

    JsonNode preview(JsonNode lab, JsonNode event, String trace) {
        JsonNode evidence = world.evidence(lab);
        if (evidence.path("plan").isNull()) throw ApiFailure.conflict("LAB_BUSY","Commit an initial plan first");
        return scheduler.post("/events/preview",db.object("instance",evidence.path("instance"),
                "base_plan",evidence.path("plan"),"event",event,"pending_events",
                world.payloads(world.facts(lab.path("id").asText()),db.json.createArrayNode())),trace);
    }

    JsonNode record(JsonNode lab, JsonNode body, boolean constraint, String trace) {
        String labId = lab.path("id").asText();
        String actor = Input.string(body,"actor");
        String item = constraint ? Input.string(body,"ir_item_id") : null;
        String key = constraint ? "constraint:" + item : "event:" + Input.string(body,"client_event_id");
        JsonNode event = constraint ? constraint(labId,item) : Input.object(body,"event");
        JsonNode previous = db.one("SELECT id AS event_id,status,original FROM event WHERE lab_id=:lab AND client_event_id=:key",
                "lab",labId,"key",key);
        if (!previous.isMissingNode()) {
            if (!previous.path("original").equals(event)) {
                throw ApiFailure.conflict("DUPLICATE_EVENT_CONFLICT","Client event ID already refers to another event");
            }
            ((ObjectNode) previous).remove("original");
            return previous;
        }
        if (!constraint) checkEvent(event);
        String action = constraint ? "CONSTRAINT_CHANGE" : "EVENT_INJECT";
        approval.consume(lab,body,action,constraint ? db.object("ir_item_id",item) : event);
        JsonNode normalized = preview(lab,event,trace).path("event_normalized");
        if (!normalized.isObject()) throw new ApiFailure(502,"SCHEDULER_UNAVAILABLE","Event normalization is missing");
        String id = World.id();
        db.write("""
                INSERT INTO event(lab_id,id,client_event_id,original,payload,status,confirmation_id,created_by)
                VALUES (:lab,:id,:client,CAST(:original AS jsonb),CAST(:payload AS jsonb),'RECEIVED',:approval,:actor)
                ""","lab",labId,"id",id,"client",key,"original",event,"payload",event,
                "approval",Input.string(body,"confirmation_id"),"actor",actor);
        if (constraint) db.write("UPDATE ir_item SET event_id=:event WHERE lab_id=:lab AND id=:id",
                "event",id,"lab",labId,"id",item);
        db.write("UPDATE lab SET revision=revision+1 WHERE id=:lab","lab",labId);
        world.audit(labId,actor,action,"event",id,null);
        jobs.queue(labId,"REPLAN",null,trace);
        return db.object("event_id",id,"status","RECEIVED");
    }

    JsonNode constraint(String lab, String id) {
        JsonNode item = db.one("SELECT item FROM ir_item WHERE lab_id=:lab AND id=:id","lab",lab,"id",id).path("item");
        if (item.isMissingNode()) throw ApiFailure.missing("IR item");
        if (!item.path("action").asText().equals("CONSTRAINT_CHANGE"))
            throw new ApiFailure(400,"UNSUPPORTED_CONSTRAINT_TYPE","Only deadline constraints are supported");
        return db.object("type","CONSTRAINT_CHANGE","ir",item.path("ir"));
    }

    void checkEvent(JsonNode event) {
        String type = Input.string(event,"type");
        if (!type.equals("DEVICE_OUTAGE") && !type.equals("URGENT_INSERT")) {
            throw new ApiFailure(400,"UNSUPPORTED_EVENT","Unsupported event type");
        }
    }

    JsonNode events(String lab, String status) {
        return db.rows("""
                SELECT id AS event_id,substring(client_event_id from position(':' in client_event_id)+1) AS client_event_id,
                payload AS event,status,job_id,created_at FROM event WHERE lab_id=:lab
                AND (CAST(:status AS text) IS NULL OR status=:status) ORDER BY seq
                ""","lab",lab,"status",status);
    }

    JsonNode turn(JsonNode lab, JsonNode body, String trace) {
        String labId = lab.path("id").asText();
        JsonNode evidence = world.evidence(lab);
        if (evidence.path("plan").isNull()) throw ApiFailure.conflict("LAB_BUSY","Commit an initial plan first");
        ObjectNode request = db.object("lab_id",labId,"text",Input.string(body,"text"),"actor",Input.string(body,"actor"),
                "instance",evidence.path("instance"),"base_plan",evidence.path("plan"),"revision",lab.path("revision"),
                "events",world.payloads(world.facts(labId),db.json.createArrayNode()));
        if (body.hasNonNull("session_id")) {
            String session = Input.string(body,"session_id");
            if (db.one("SELECT id FROM agent_session WHERE lab_id=:lab AND id=:id","lab",labId,"id",session).isMissingNode())
                throw ApiFailure.missing("Agent session");
            request.put("session_id",session);
        }
        JsonNode response = scheduler.post("/agent/turn",request,trace);
        String id = Input.string(response,"session_id");
        db.write("""
                INSERT INTO agent_session(lab_id,id) VALUES(:lab,:id)
                ON CONFLICT(lab_id,id) DO UPDATE SET updated_at=clock_timestamp()
                ""","lab",labId,"id",id);
        for (JsonNode item : response.path("pending_items")) {
            db.write("""
                    INSERT INTO ir_item(lab_id,id,session_id,item) VALUES(:lab,:id,:session,CAST(:item AS jsonb))
                    ON CONFLICT(lab_id,id) DO NOTHING
                    ""","lab",labId,"id",Input.string(item,"item_id"),"session",id,"item",item);
        }
        return response;
    }
}
