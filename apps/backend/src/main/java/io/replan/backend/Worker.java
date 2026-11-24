package io.replan.backend;

import com.fasterxml.jackson.databind.JsonNode;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Semaphore;
import org.apache.commons.logging.Log;
import org.apache.commons.logging.LogFactory;
import org.springframework.beans.factory.DisposableBean;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
@org.springframework.boot.autoconfigure.condition.ConditionalOnProperty(name="p7.worker-enabled",matchIfMissing=true)
class Worker implements DisposableBean {
    private static final Log LOG = LogFactory.getLog(Worker.class);
    private final Jobs jobs;
    private final Db db;
    private final ExecutorService executor;
    private final Semaphore slots;
    private volatile boolean ready;

    Worker(Jobs jobs, Db db, @Value("${p7.workers}") int workers) {
        this.jobs = jobs;
        this.db = db;
        this.executor = Executors.newFixedThreadPool(workers);
        this.slots = new Semaphore(workers);
    }

    @EventListener(ApplicationReadyEvent.class)
    void recover() {
        jobs.recover();
        ready = true;
    }

    @Scheduled(fixedDelayString = "${p7.poll-ms}")
    void poll() {
        if (!ready) return;
        while (slots.tryAcquire()) {
            boolean submitted = false;
            try {
                JsonNode claimed = jobs.claim();
                if (claimed.isMissingNode()) return;
                executor.submit(() -> run(claimed));
                submitted = true;
            } finally {
                if (!submitted) slots.release();
            }
        }
    }

    private void run(JsonNode job) {
        JsonNode result = null, error = null;
        try {
            result = jobs.solve(job);
        } catch (ApiFailure failure) {
            error = db.object("code",failure.code,"message",failure.getMessage(),"details",failure.details);
        } catch (RuntimeException failure) {
            LOG.error("Job execution failed, trace_id=" + job.path("trace_id").asText());
            error = db.object("code","INTERNAL_ERROR","message","Job execution failed");
        }
        try {
            jobs.finish(job,result,error);
        } finally {
            slots.release();
        }
    }

    @Override
    public void destroy() {
        ready = false;
        executor.shutdownNow();
    }
}
