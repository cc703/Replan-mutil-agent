package io.replan.backend;

import com.fasterxml.jackson.databind.JsonNode;
import jakarta.servlet.http.HttpServletRequest;
import org.apache.commons.logging.Log;
import org.apache.commons.logging.LogFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;
import org.springframework.web.servlet.resource.NoResourceFoundException;

@RestControllerAdvice
class ApiErrors {
    private static final Log LOG = LogFactory.getLog(ApiErrors.class);
    private final Db db;

    ApiErrors(Db db) { this.db = db; }

    @ExceptionHandler(ApiFailure.class)
    ResponseEntity<JsonNode> failure(ApiFailure failure,HttpServletRequest request) {
        return ResponseEntity.status(failure.status).body(db.object("error",
                db.object("code",failure.code,"message",failure.getMessage(),"details",
                        failure.details == null ? db.object() : failure.details,"trace_id",ApiTrace.id(request))));
    }

    @ExceptionHandler(NoResourceFoundException.class)
    ResponseEntity<JsonNode> missing(NoResourceFoundException error,HttpServletRequest request) {
        return failure(ApiFailure.missing("Endpoint"),request);
    }

    @ExceptionHandler(MethodArgumentTypeMismatchException.class)
    ResponseEntity<JsonNode> badArgument(MethodArgumentTypeMismatchException error,HttpServletRequest request) {
        return failure(ApiFailure.invalid("Invalid " + error.getName()),request);
    }

    @ExceptionHandler(Exception.class)
    ResponseEntity<JsonNode> unexpected(Exception error,HttpServletRequest request) {
        LOG.error("Request failed, trace_id=" + ApiTrace.id(request) + ", type=" + error.getClass().getName());
        return failure(new ApiFailure(500,"INTERNAL_ERROR","Request failed"),request);
    }
}
