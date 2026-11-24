package io.replan.backend;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.util.UUID;
import org.springframework.stereotype.Component;

@Component
class World {
    static final String OPEN = "status IN ('RECEIVED','RELEASED','BATCHED')";
    final Db db;

    World(Db db) { this.db = db; }

    static String id() { return UUID.randomUUID().toString(); }

    JsonNode lab(String id, boolean lock) {
        JsonNode result = db.one("SELECT * FROM lab WHERE id=:lab" + (lock ? " FOR UPDATE" : ""), "lab", id);
        if (result.isMissingNode()) throw ApiFailure.missing("Lab");
        return result;
    }

    JsonNode version(String lab, int version) {
        JsonNode result = db.one("SELECT * FROM plan_version WHERE lab_id=:lab AND version_no=:version",
                "lab", lab, "version", version);
        if (result.isMissingNode()) throw ApiFailure.missing("Plan version");
        return result;
    }

    JsonNode evidence(JsonNode lab) {
        int version = lab.path("active_version_no").asInt();
        return version == 0 ? db.object("instance", lab.path("instance"), "plan", null)
                : version(lab.path("id").asText(), version).path("evidence");
    }

    ArrayNode facts(String lab) {
        return db.rows("SELECT id,payload FROM event WHERE lab_id=:lab AND " + OPEN + " ORDER BY seq", "lab", lab);
    }

    ArrayNode payloads(ArrayNode facts, JsonNode excluded) {
        ArrayNode result = db.json.createArrayNode();
        for (JsonNode fact : facts) {
            boolean captured = false;
            for (JsonNode id : excluded) {
                if (id.equals(fact.path("id"))) captured = true;
            }
            if (!captured) result.add(fact.path("payload"));
        }
        return result;
    }

    ArrayNode eventIds(ArrayNode facts) {
        ArrayNode ids = db.json.createArrayNode();
        facts.forEach(fact -> ids.add(fact.path("id")));
        return ids;
    }

    void audit(String lab, String actor, String action, String subject, String id, JsonNode details) {
        db.write("""
                INSERT INTO decision_log(lab_id,actor,action,subject_type,subject_id,details)
                VALUES (:lab,:actor,:action,:subject,:id,CAST(:details AS jsonb))
                """, "lab", lab, "actor", actor, "action", action, "subject", subject, "id", id,
                "details", details == null ? db.object() : details);
    }

    static void base(JsonNode lab, int expected) {
        if (lab.path("active_version_no").asInt() != expected)
            throw ApiFailure.conflict("STALE_BASE_VERSION", "Active version has changed");
    }

    ObjectNode labDto(JsonNode lab) {
        return db.object("lab_id", lab.path("id"), "name", lab.path("name"), "instance_sha256",
                lab.path("instance_sha256"), "summary", lab.path("summary"),
                "active_version_no", lab.path("active_version_no"));
    }

    ObjectNode versionDto(JsonNode version) {
        return db.object("version_no", version.path("version_no"), "parent_version_no",
                version.path("parent_version_no"), "status", version.path("status"), "created_at",
                version.path("created_at"), "source", version.path("source"), "job_id", version.path("job_id"));
    }
}
