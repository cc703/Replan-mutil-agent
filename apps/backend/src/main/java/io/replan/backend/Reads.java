package io.replan.backend;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.springframework.stereotype.Component;

@Component
class Reads {
    private final Db db;
    private final World world;
    private final Jobs jobs;
    private final Facts facts;
    private final Plans plans;
    private final Scheduler scheduler;

    Reads(Db db, World world, Jobs jobs, Facts facts, Plans plans, Scheduler scheduler) {
        this.db = db;
        this.world = world;
        this.jobs = jobs;
        this.facts = facts;
        this.plans = plans;
        this.scheduler = scheduler;
    }

    JsonNode list() {
        ArrayNode rows = db.json.createArrayNode();
        db.rows("SELECT * FROM lab ORDER BY created_at,id").forEach(row -> rows.add(world.labDto(row)));
        return rows;
    }

    JsonNode read(String labId, String path, String status, Integer base, String trace) {
        JsonNode lab = world.lab(labId,false);
        JsonNode response = switch (path) {
            case "" -> overview(lab);
            case "instance" -> world.evidence(lab).path("instance");
            case "plans" -> versions(labId);
            case "events" -> facts.events(labId,status);
            case "jobs" -> jobList(lab,trace);
            case "decisions" -> db.rows("""
                    SELECT id AS decision_id,actor,action,subject_type,subject_id,details,at
                    FROM decision_log WHERE lab_id=:lab ORDER BY id
                    ""","lab",labId);
            default -> dynamic(lab,path,base,trace);
        };
        JsonNode current = world.lab(labId,false);
        if (!lab.path("active_version_no").equals(current.path("active_version_no"))
                || !lab.path("revision").equals(current.path("revision"))) {
            throw ApiFailure.conflict("STALE_BASE_VERSION","Laboratory changed during the read");
        }
        return response;
    }

    private JsonNode dynamic(JsonNode lab, String path, Integer base, String trace) {
        String labId = lab.path("id").asText();
        String[] parts = path.split("/");
        if (parts.length == 2 && parts[0].equals("jobs"))
            return jobs.response(jobs.get(labId,parts[1]),lab,true,trace);
        if ((parts.length == 2 || parts.length == 3) && parts[0].equals("plans")) {
            int version;
            try { version = Integer.parseInt(parts[1]); }
            catch (NumberFormatException e) { throw ApiFailure.missing("Plan version"); }
            if (parts.length == 2) return plans.read(lab,version,trace);
            JsonNode row = world.version(labId,version);
            JsonNode evidence = row.path("evidence");
            if (parts[2].equals("instance")) return evidence.path("instance");
            if (parts[2].equals("diff")) {
                if (base == null) throw ApiFailure.invalid("Missing base version");
                JsonNode parent = world.version(labId,base);
                if (!plans.versionUsable(row,trace) || !plans.versionUsable(parent,trace)) {
                    throw new ApiFailure(422,"VALIDATION_FAILED","An active comparison plan is unsafe in the current world");
                }
                return scheduler.post("/diff",db.object("instance",evidence.path("instance"),
                        "plan",evidence.path("plan"),"base_plan",parent.path("evidence").path("plan")),trace);
            }
        }
        throw ApiFailure.missing("Endpoint");
    }

    private JsonNode overview(JsonNode lab) {
        String id = lab.path("id").asText();
        ObjectNode dto = world.labDto(lab);
        JsonNode job = db.one("""
                SELECT max(id) FILTER(WHERE status='RUNNING') AS running_job_id,
                max(id) FILTER(WHERE status='SUCCEEDED') AS undecided_job_id FROM job WHERE lab_id=:lab
                ""","lab",id);
        dto.set("running_job_id",job.path("running_job_id"));
        dto.set("undecided_job_id",job.path("undecided_job_id"));
        dto.put("pending_event_count",world.facts(id).size());
        return dto;
    }

    private JsonNode versions(String lab) {
        ArrayNode result = db.json.createArrayNode();
        db.rows("SELECT * FROM plan_version WHERE lab_id=:lab ORDER BY version_no","lab",lab)
                .forEach(row -> result.add(world.versionDto(row)));
        return result;
    }

    private JsonNode jobList(JsonNode lab, String trace) {
        ArrayNode result = db.json.createArrayNode();
        db.rows("SELECT * FROM job WHERE lab_id=:lab ORDER BY created_at,id","lab",lab.path("id").asText())
                .forEach(job -> result.add(jobs.response(job,lab,true,trace)));
        return result;
    }
}
