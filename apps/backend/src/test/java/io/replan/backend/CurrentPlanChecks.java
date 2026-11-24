package io.replan.backend;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.file.Files;
import java.nio.file.Path;
import org.springframework.context.ConfigurableApplicationContext;

/** HTTP regression using the real scheduler and the isolated schema from PostgresChecks. */
final class CurrentPlanChecks {
    private static final String ACTOR = "current-plan-check";
    private final HttpClient http = HttpClient.newHttpClient();
    private final Db db;
    private final Jobs jobs;
    private final String origin;
    private String lab;

    CurrentPlanChecks(ConfigurableApplicationContext context) {
        db = context.getBean(Db.class);
        jobs = context.getBean(Jobs.class);
        origin = "http://127.0.0.1:" + context.getEnvironment().getRequiredProperty("local.server.port") + "/api/v1";
    }

    void run() throws Exception {
        Path fixture = Path.of("apps/contracts/examples/instance.json");
        if (!Files.isRegularFile(fixture)) fixture = Path.of("../contracts/examples/instance.json");
        JsonNode instance = db.parse(Files.readString(fixture));
        lab = request("POST","/labs",db.object("name",ACTOR,"instance",instance),World.id(),201)
                .path("lab_id").asText();
        post("/plans/initial",db.object(),202);
        JsonNode initial = nextCandidate();
        commit(initial,0,accept(confirmation(initial,0,World.id(),201)));
        inject(db.object("type","DEVICE_OUTAGE","device_id","device-a",
                "start","2026-11-24T02:30:00Z","end","2026-11-24T02:35:00Z"));

        JsonNode obsolete = nextCandidate();
        String originalKey = World.id();
        JsonNode baseline = confirmation(obsolete,1,originalKey,201);
        check(baseline.path("preview").has("diff") && baseline.path("preview").path("validation").path("passed").asBoolean(),
                "Normal commit preview includes the verified candidate");
        check(confirmation(obsolete,1,originalKey,201).path("confirmation_id").equals(baseline.path("confirmation_id")),
                "An unchanged preview retains the same confirmation");
        ObjectNode forged = selection(obsolete,1);
        forged.put("plan_sha256","0".repeat(64));
        check(code(post("/confirmations",approval("PLAN_COMMIT","L2",forged),409)).equals("CONFIRMATION_MISMATCH"),
                "Forged candidate hash must be rejected");
        String approvalId = accept(baseline);
        inject(outage(obsolete.path("view").path("assignments").path(0)));
        assertPreviewRejected(confirmation(obsolete,1,World.id(),422));
        assertPreviewRejected(confirmation(obsolete,1,originalKey,422));
        String obsoleteJob = obsolete.path("job_id").asText();
        check(get("/jobs/" + obsoleteJob,200).path("candidates").isEmpty(),"Old candidate must be hidden");
        check(code(post("/plans/commit",action(obsolete,1,approvalId),422)).equals("VALIDATION_FAILED"),
                "Old candidate must not be committed");
        check(db.one("SELECT status FROM confirmation WHERE lab_id=:lab AND id=:id","lab",lab,"id",approvalId)
                .path("status").asText().equals("CONFIRMED"),"Rejection must preserve L2 approval");
        post("/jobs/" + obsoleteJob + "/discard",db.object("actor",ACTOR,"reason","stale candidate"),200);

        JsonNode replacement = nextCandidate();
        commit(replacement,1,accept(confirmation(replacement,1,World.id(),201)));
        check(get("/plans/2/diff?base=1",200).path("changes").isArray(),"Usable v2 diff must be available");
        JsonNode active = get("/plans/2",200);
        JsonNode rollbackBody = approval("PLAN_ROLLBACK","L2",db.object("target_version_no",2,"base_version_no",2));
        String rollbackKey = World.id();
        String rollbackPath = "/labs/" + lab + "/confirmations";
        JsonNode rollbackPreview = request("POST",rollbackPath,rollbackBody,rollbackKey,201);
        check(rollbackPreview.path("preview").path("validation").path("passed").asBoolean(),
                "Normal rollback preview must include successful validation");
        inject(outage(active.path("view").path("assignments").path(0)));
        check(get("/plans/2",200).path("status").asText().equals("NEEDS_REPLAN"),"L1 invalidates active v2");
        JsonNode replay = request("POST",rollbackPath,rollbackBody,rollbackKey,422);
        check(code(replay).equals("ROLLBACK_INFEASIBLE") && !replay.has("preview"),
                "Rollback replay must reject a newly unsafe target without cached details");
        for (String path : new String[]{"/plans/2/diff?base=1","/plans/1/diff?base=2"}) {
            JsonNode rejected = get(path,422);
            check(code(rejected).equals("VALIDATION_FAILED") && !rejected.has("changes"),
                    "Unsafe active plan must not expose its diff in either position");
        }
        check(get("/plans/1/diff?base=1",200).path("changes").isArray(),"Historical diff remains readable");
        System.out.println("P7 current-plan HTTP checks passed");
    }

    private JsonNode nextCandidate() throws Exception {
        for (int attempt = 0; attempt < 20; attempt++) {
            JsonNode job = jobs.claim();
            if (!job.isMissingNode()) {
                jobs.finish(job,jobs.solve(job),null);
                JsonNode result = get("/jobs/" + job.path("id").asText(),200);
                JsonNode candidate = result.path("candidates").path(0);
                check(candidate.isObject(),"Expected an independently validated candidate");
                return ((ObjectNode) candidate).set("job_id",job.path("id"));
            }
            Thread.sleep(100);
        }
        throw new AssertionError("Expected a queued job");
    }

    private JsonNode confirmation(JsonNode candidate, int base, String key, int status) throws Exception {
        return request("POST","/labs/" + lab + "/confirmations",
                approval("PLAN_COMMIT","L2",selection(candidate,base)),key,status);
    }

    private ObjectNode selection(JsonNode candidate, int base) {
        return db.object("job_id",candidate.path("job_id"),"candidate_id",candidate.path("candidate_id"),
                "base_version_no",base,"plan_sha256",candidate.path("plan_sha256"));
    }

    private JsonNode approval(String action, String level, JsonNode payload) {
        return db.object("action",action,"level",level,"payload",payload,"actor",ACTOR);
    }

    private String accept(JsonNode confirmation) throws Exception {
        String id = confirmation.path("confirmation_id").asText();
        post("/confirmations/" + id + "/confirm",db.object("actor",ACTOR,"payload_hash",confirmation.path("payload_hash")),200);
        return id;
    }

    private ObjectNode action(JsonNode candidate, int base, String id) {
        ObjectNode action = selection(candidate,base);
        action.remove("plan_sha256");
        return action.put("confirmation_id",id).put("actor",ACTOR);
    }

    private void commit(JsonNode candidate, int base, String id) throws Exception {
        post("/plans/commit",action(candidate,base,id),201);
    }

    private JsonNode outage(JsonNode assignment) {
        return db.object("type","DEVICE_OUTAGE","device_id",assignment.path("device_id"),
                "start",assignment.path("start_iso"),"end",assignment.path("end_iso"));
    }

    private void inject(JsonNode event) throws Exception {
        String id = accept(post("/confirmations",approval("EVENT_INJECT","L1",event),201));
        post("/events",db.object("client_event_id",World.id(),"event",event,"confirmation_id",id,"actor",ACTOR),202);
    }

    private void assertPreviewRejected(JsonNode response) {
        check(code(response).equals("VALIDATION_FAILED") && !response.has("preview")
                && !response.has("diff") && !response.has("validation"),"Unsafe preview must expose no candidate details");
    }

    private String code(JsonNode response) { return response.path("error").path("code").asText(); }

    private JsonNode post(String path, JsonNode body, int status) throws Exception {
        return request("POST","/labs/" + lab + path,body,World.id(),status);
    }

    private JsonNode get(String path, int status) throws Exception {
        return request("GET","/labs/" + lab + path,null,null,status);
    }

    private JsonNode request(String method, String path, JsonNode body, String key, int status) throws Exception {
        HttpRequest.Builder builder = HttpRequest.newBuilder(URI.create(origin + path));
        if (method.equals("POST")) {
            builder.header("Content-Type","application/json").header("Idempotency-Key",key)
                    .POST(HttpRequest.BodyPublishers.ofString(body.toString()));
        }
        var response = http.send(builder.build(),HttpResponse.BodyHandlers.ofString());
        JsonNode data = db.parse(response.body());
        check(response.statusCode() == status,method + " " + path + " expected " + status
                + " got " + response.statusCode() + " " + code(data));
        return data;
    }

    private void check(boolean passed, String reason) { if (!passed) throw new AssertionError(reason); }
}
