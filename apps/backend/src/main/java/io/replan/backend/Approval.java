package io.replan.backend;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.util.Map;
import org.springframework.stereotype.Component;

@Component
class Approval {
    private static final Map<String,String> LEVEL = Map.of("EVENT_INJECT","L1","CONSTRAINT_CHANGE","L1",
            "PLAN_COMMIT","L2","PLAN_ROLLBACK","L2");
    private final World world;
    private final Db db;
    private final Scheduler scheduler;
    private final int defaultTtl;

    Approval(World world, Db db, Scheduler scheduler,
             @org.springframework.beans.factory.annotation.Value("${p7.confirmation-ttl-s:900}") int defaultTtl) {
        this.world = world;
        this.db = db;
        this.scheduler = scheduler;
        this.defaultTtl = defaultTtl;
    }

    JsonNode create(JsonNode lab, JsonNode body, ObjectNode preview, String trace) {
        String action = Input.string(body, "action");
        String level = Input.string(body, "level");
        if (!LEVEL.containsKey(action)) throw ApiFailure.invalid("Unknown confirmation action");
        if (!LEVEL.get(action).equals(level)) throw error("CONFIRMATION_LEVEL_INSUFFICIENT");
        JsonNode payload = Input.object(body, "payload");
        String actor = Input.string(body, "actor");
        int ttl = Input.optionalInt(body, "ttl_s", defaultTtl);
        if (ttl < 1 || ttl > 3600) throw ApiFailure.invalid("TTL must be 1 to 3600 seconds");
        String hash = scheduler.post("/hash", db.object("payload", payload), trace).path("sha256").asText();
        if (!hash.matches("[a-f0-9]{64}")) throw new ApiFailure(502, "SCHEDULER_UNAVAILABLE", "Missing payload hash");
        String labId = lab.path("id").asText();
        String id = World.id();
        db.write("""
                INSERT INTO confirmation(lab_id,id,action,level,payload,payload_hash,preview,base_version_no,
                status,requested_by,expires_at) VALUES (:lab,:id,:action,:level,CAST(:payload AS jsonb),
                :hash,CAST(:preview AS jsonb),:base,'PENDING',:actor,clock_timestamp() + :ttl * interval '1 second')
                """, "lab",labId,"id",id,"action",action,"level",level,"payload",payload,"hash",hash,
                "preview",preview,"base",lab.path("active_version_no").asInt(),"actor",actor,"ttl",ttl);
        world.audit(labId,actor,"CONFIRMATION_REQUESTED","confirmation",id,db.object("action",action));
        return db.one("""
                SELECT id AS confirmation_id,action,level,payload_hash,preview,expires_at,status
                FROM confirmation WHERE lab_id=:lab AND id=:id
                ""","lab",labId,"id",id);
    }

    JsonNode decide(JsonNode lab, String id, JsonNode body, boolean accept) {
        String labId = lab.path("id").asText();
        JsonNode row = fetch(labId,id);
        String actor = Input.string(body,"actor");
        if (!row.path("payload_hash").asText().equals(Input.string(body,"payload_hash"))) throw error("CONFIRMATION_MISMATCH");
        checkCurrent(lab,row);
        if (!row.path("status").asText().equals("PENDING")) throw error("CONFIRMATION_NOT_CONFIRMED");
        String status = accept ? "CONFIRMED" : "REJECTED";
        db.write("UPDATE confirmation SET status=:status,confirmed_by=:actor WHERE lab_id=:lab AND id=:id",
                "status",status,"actor",actor,"lab",labId,"id",id);
        world.audit(labId,actor,"CONFIRMATION_" + status,"confirmation",id,null);
        return db.object("status",status);
    }

    void verify(JsonNode lab, JsonNode body, String action, JsonNode payload) {
        if (!body.hasNonNull("confirmation_id")) {
            throw new ApiFailure(428,"CONFIRMATION_REQUIRED","A confirmation is required");
        }
        String labId = lab.path("id").asText();
        String id = Input.string(body,"confirmation_id");
        JsonNode row = fetch(labId,id);
        if (!LEVEL.get(action).equals(row.path("level").asText())) throw error("CONFIRMATION_LEVEL_INSUFFICIENT");
        checkCurrent(lab,row);
        if (!row.path("status").asText().equals("CONFIRMED")) throw error("CONFIRMATION_NOT_CONFIRMED");
        if (!action.equals(row.path("action").asText()) || !payload.equals(row.path("payload")))
            throw error("CONFIRMATION_MISMATCH");
        Input.string(body,"actor");
    }

    void consume(JsonNode lab, JsonNode body, String action, JsonNode payload) {
        verify(lab,body,action,payload);
        String labId = lab.path("id").asText();
        String id = Input.string(body,"confirmation_id");
        if (db.write("""
                UPDATE confirmation SET status='CONSUMED',consumed_at=clock_timestamp()
                WHERE lab_id=:lab AND id=:id AND status='CONFIRMED' AND expires_at > clock_timestamp()
                ""","lab",labId,"id",id) != 1) throw error("CONFIRMATION_EXPIRED");
        world.audit(labId,Input.string(body,"actor"),"CONFIRMATION_CONSUMED","confirmation",id,db.object("action",action));
    }

    private JsonNode fetch(String lab, String id) {
        JsonNode row = db.one("SELECT *,expires_at <= clock_timestamp() AS expired FROM confirmation WHERE lab_id=:lab AND id=:id",
                "lab",lab,"id",id);
        if (row.isMissingNode()) throw error("CONFIRMATION_MISMATCH");
        return row;
    }

    private void checkCurrent(JsonNode lab, JsonNode row) {
        if (row.path("status").asText().equals("CONSUMED")) throw error("CONFIRMATION_CONSUMED");
        if (row.path("expired").asBoolean()) throw error("CONFIRMATION_EXPIRED");
        if (row.path("base_version_no").asInt() != lab.path("active_version_no").asInt())
            throw error("CONFIRMATION_MISMATCH");
    }

    private ApiFailure error(String code) {
        return ApiFailure.conflict(code, "Confirmation state, scope or payload does not match the requested operation");
    }
}
