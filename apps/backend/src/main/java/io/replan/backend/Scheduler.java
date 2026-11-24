package io.replan.backend;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.net.http.HttpTimeoutException;
import java.time.Duration;
import java.util.Set;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

@Component
class Scheduler {
    private final Db db;
    private final URI origin;
    private final HttpClient http = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(3)).build();

    Scheduler(Db db, @Value("${p7.scheduler-url}") String url) {
        this.db = db;
        URI parsed = URI.create(url);
        if (!"http".equals(parsed.getScheme()) || parsed.getHost() == null
                || !Set.of("127.0.0.1", "localhost", "[::1]").contains(parsed.getHost())
                || parsed.getUserInfo() != null || parsed.getQuery() != null || parsed.getFragment() != null
                || !(parsed.getPath().isEmpty() || parsed.getPath().equals("/"))) {
            throw new IllegalArgumentException("P7_SCHEDULER_URL must be a loopback HTTP origin");
        }
        this.origin = parsed;
    }

    JsonNode post(String path, JsonNode payload, String trace) {
        HttpRequest request = HttpRequest.newBuilder(origin.resolve("/internal/v1" + path))
                .timeout(Duration.ofSeconds(135))
                .header("Content-Type", "application/json")
                .header("X-Trace-Id", trace)
                .POST(HttpRequest.BodyPublishers.ofString(payload.toString()))
                .build();
        try {
            HttpResponse<String> response = http.send(request, HttpResponse.BodyHandlers.ofString());
            JsonNode result = db.parse(response.body());
            if (response.statusCode() < 300 && result.isObject()) {
                return result;
            }
            JsonNode error = result.path("error");
            if (error.isObject() && error.path("code").isTextual()) {
                throw new ApiFailure(response.statusCode(), error.path("code").asText(),
                        error.path("message").asText(), error.path("details"));
            }
            throw unavailable();
        } catch (HttpTimeoutException e) {
            throw new ApiFailure(504, "SCHEDULER_TIMEOUT", "Scheduler request exceeded its deadline");
        } catch (IOException | IllegalStateException e) {
            throw unavailable();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw unavailable();
        }
    }

    boolean valid(JsonNode evidence, String planHash, JsonNode additional, String trace) {
        if (!evidence.isObject() || planHash.isBlank()) {
            return false;
        }
        ObjectNode request = evidence.deepCopy();
        request.put("expected_plan_sha256", planHash);
        if (!additional.isEmpty()) {
            request.set("additional_events", additional);
            if (evidence.path("base_plan").isNull()) {
                request.set("current_base_plan", evidence.path("plan"));
            }
        }
        JsonNode result = post("/validate", request, trace);
        return result.path("passed").asBoolean() && result.path("plan_sha256_ok").asBoolean();
    }

    private ApiFailure unavailable() {
        return new ApiFailure(502, "SCHEDULER_UNAVAILABLE", "Scheduler service is unavailable");
    }
}
