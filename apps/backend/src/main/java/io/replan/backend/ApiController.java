package io.replan.backend;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import jakarta.servlet.http.HttpServletRequest;
import java.io.IOException;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1")
class ApiController {
    private static final int MAX_BODY = 8 * 1024 * 1024;
    private final Db db;
    private final Writes writes;
    private final Reads reads;

    ApiController(Db db,Writes writes,Reads reads) {
        this.db = db;
        this.writes = writes;
        this.reads = reads;
    }

    @GetMapping("/health")
    JsonNode health() {
        db.one("SELECT 1 AS ready");
        return db.object("status","UP");
    }

    @GetMapping("/labs")
    JsonNode labs() { return reads.list(); }

    @GetMapping({"/labs/{lab}","/labs/{lab}/{*path}"})
    JsonNode read(@PathVariable String lab,@PathVariable(required=false) String path,
                  @RequestParam(required=false) String status,@RequestParam(required=false) Integer base,
                  HttpServletRequest request) {
        return reads.read(lab,relative(path),status,base,ApiTrace.id(request));
    }

    @PostMapping("/labs")
    ResponseEntity<JsonNode> create(@RequestHeader(value="Idempotency-Key",required=false) String key,
                                   HttpServletRequest request) throws IOException {
        return response(writes.submit(null,"labs",key,body(request),ApiTrace.id(request)));
    }

    @PostMapping("/labs/{lab}/{*path}")
    ResponseEntity<JsonNode> write(@PathVariable String lab,@PathVariable String path,
                                   @RequestHeader(value="Idempotency-Key",required=false) String key,
                                   HttpServletRequest request) throws IOException {
        return response(writes.submit(lab,relative(path),key,body(request),ApiTrace.id(request)));
    }

    private JsonNode body(HttpServletRequest request) throws IOException {
        if (request.getContentLengthLong() > MAX_BODY) throw tooLarge();
        byte[] body = request.getInputStream().readNBytes(MAX_BODY+1);
        if (body.length > MAX_BODY) throw tooLarge();
        try {
            JsonNode json = db.json.reader().with(com.fasterxml.jackson.databind.DeserializationFeature.FAIL_ON_TRAILING_TOKENS)
                    .with(com.fasterxml.jackson.core.JsonParser.Feature.STRICT_DUPLICATE_DETECTION).readTree(body);
            if (json == null || !json.isObject()) throw ApiFailure.invalid("Expected a JSON object");
            return json;
        } catch (JsonProcessingException e) {
            throw ApiFailure.invalid("Malformed JSON request");
        }
    }

    private ApiFailure tooLarge() {
        return new ApiFailure(413,"PAYLOAD_TOO_LARGE","Body exceeds 8 MiB");
    }

    private ResponseEntity<JsonNode> response(Writes.Reply reply) {
        ResponseEntity.BodyBuilder response = ResponseEntity.status(reply.status());
        if (reply.replay()) response.header("Idempotent-Replay","true");
        return response.body(reply.body());
    }

    private String relative(String path) {
        return path == null || path.isEmpty() ? "" : path.substring(1);
    }
}
