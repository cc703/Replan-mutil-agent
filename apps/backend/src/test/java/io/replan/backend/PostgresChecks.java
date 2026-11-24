package io.replan.backend;

import com.fasterxml.jackson.databind.JsonNode;
import java.sql.DriverManager;
import java.util.List;
import java.util.Map;
import java.util.concurrent.Callable;
import java.util.concurrent.Executors;
import org.springframework.boot.WebApplicationType;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.transaction.support.TransactionTemplate;

/** Executed by Maven verify with an isolated schema in the dedicated local test database. */
public final class PostgresChecks {
    private PostgresChecks() {}

    public static void main(String[] args) throws Exception {
        String url = System.getenv("P7_TEST_DB_URL");
        String user = System.getenv("P7_TEST_DB_USER");
        String password = System.getenv("P7_TEST_DB_PASSWORD");
        if (url == null || !url.matches("jdbc:postgresql://(127\\.0\\.0\\.1|localhost):[0-9]+/p7_test")
                || user == null || password == null) {
            throw new IllegalArgumentException("Configure P7_TEST_DB_* for the separate loopback p7_test database");
        }
        String schema = "check_" + World.id().replace("-","");
        String scheduler = System.getenv("P7_TEST_SCHEDULER_URL");
        boolean httpChecks = scheduler != null && !scheduler.isBlank();
        Map<String,Object> config = new java.util.HashMap<>(Map.of("spring.datasource.url",url + "?currentSchema=" + schema,
                "spring.datasource.username",user,"spring.datasource.password",password,
                "spring.flyway.schemas",schema,"spring.flyway.default-schema",schema,"p7.worker-enabled","false"));
        if (httpChecks) {
            config.put("server.port",0);
            config.put("p7.scheduler-url",scheduler);
        }
        try (var context = new SpringApplicationBuilder(BackendApplication.class).web(httpChecks ? WebApplicationType.SERVLET : WebApplicationType.NONE)
                .run(config.entrySet().stream().map(entry -> "--" + entry.getKey() + "="
                        + entry.getValue()).toArray(String[]::new))) {
            Db db = context.getBean(Db.class);
            World world = context.getBean(World.class);
            Jobs jobs = context.getBean(Jobs.class);
            Approval approval = context.getBean(Approval.class);
            TransactionTemplate tx = context.getBean(TransactionTemplate.class);
            seed(db,"first");
            seed(db,"second");
            concurrency(db,jobs);
            approvalRollback(db,world,approval,tx);
            recovery(db,jobs);
            if (httpChecks) new CurrentPlanChecks(context).run();
            System.out.println("P7 PostgreSQL checks passed");
        } finally {
            try (var connection = DriverManager.getConnection(url,user,password);
                 var statement = connection.createStatement()) {
                statement.execute("DROP SCHEMA IF EXISTS " + schema + " CASCADE");
            }
        }
    }

    private static void concurrency(Db db, Jobs jobs) throws Exception {
        var executor = Executors.newFixedThreadPool(8);
        try {
            List<Callable<JsonNode>> calls = java.util.stream.IntStream.range(0,8)
                    .mapToObj(index -> (Callable<JsonNode>) jobs::claim).toList();
            int claimed = 0;
            for (var result : executor.invokeAll(calls)) {
                if (!result.get().isMissingNode()) claimed++;
            }
            check(claimed == 2,"One job may run in each of two labs");
            check(db.rows("SELECT id FROM job WHERE status='RUNNING'").size() == 2,"Both jobs run");
            JsonNode first = db.one("SELECT * FROM job WHERE lab_id='first' AND status='RUNNING'");
            jobs.finish(first,db.object("result_status","TIMEOUT"),null);
            db.write("INSERT INTO job(lab_id,id,kind,status,trace_id) VALUES ('first','next','INITIAL','QUEUED','next')");
            check(jobs.claim().isMissingNode(),"An undecided timeout blocks the next job");
            db.write("UPDATE job SET status='DISCARDED' WHERE lab_id='first' AND id='job'");
            check(jobs.claim().path("id").asText().equals("next"),"Discard releases the next claim");
        } finally {
            executor.shutdownNow();
        }
    }

    private static void approvalRollback(Db db, World world, Approval approval, TransactionTemplate tx) {
        JsonNode request = db.object("confirmation_id","approval","actor","operator");
        JsonNode payload = db.object("type","DEVICE_OUTAGE");
        try {
            tx.executeWithoutResult(status -> {
                approval.consume(world.lab("first",true),request,"EVENT_INJECT",payload);
                throw ApiFailure.invalid("Simulated late failure");
            });
            throw new AssertionError("Expected transaction failure");
        } catch (ApiFailure expected) {
            check(expected.status == 400,"Expected validation failure");
        }
        check(db.one("SELECT status FROM confirmation WHERE lab_id='first'").path("status").asText()
                .equals("CONFIRMED"),"Failed transaction retained authorization");
        tx.executeWithoutResult(status -> approval.consume(world.lab("first",true),request,"EVENT_INJECT",payload));
        try {
            tx.executeWithoutResult(status -> approval.consume(world.lab("first",true),request,"EVENT_INJECT",payload));
            throw new AssertionError("Consumed approval was accepted");
        } catch (ApiFailure expected) {
            check(expected.code.equals("CONFIRMATION_CONSUMED"),"Single-use approval");
        }
    }

    private static void recovery(Db db, Jobs jobs) {
        db.write("""
                INSERT INTO event(lab_id,id,client_event_id,original,payload,status,job_id,confirmation_id,created_by)
                VALUES ('second','fact','client','{}','{}','BATCHED','job','approval','test')
                """);
        jobs.recover();
        check(db.one("SELECT status FROM event WHERE lab_id='second'").path("status").asText()
                .equals("RELEASED"),"Restart retained the confirmed fact");
        check(db.one("SELECT error FROM job WHERE lab_id='second'").path("error").path("code").asText()
                .equals("WORKER_RESTARTED"),"Restart recorded its reason");
    }

    private static void seed(Db db, String lab) {
        db.write("INSERT INTO lab(id,name,instance,instance_sha256,summary) VALUES (:lab,:lab,'{}','hash','{}')","lab",lab);
        db.write("INSERT INTO job(lab_id,id,kind,status,trace_id) VALUES (:lab,'job','INITIAL','QUEUED','seed')","lab",lab);
        db.write("""
                INSERT INTO confirmation(lab_id,id,action,level,payload,payload_hash,preview,base_version_no,
                status,requested_by,confirmed_by,expires_at)
                VALUES (:lab,'approval','EVENT_INJECT','L1','{"type":"DEVICE_OUTAGE"}','hash','{}',0,
                'CONFIRMED','operator','operator',clock_timestamp() + interval '1 hour')
                ""","lab",lab);
    }

    private static void check(boolean passed, String message) {
        if (!passed) throw new AssertionError(message);
    }
}
