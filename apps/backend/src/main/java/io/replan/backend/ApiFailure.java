package io.replan.backend;

import com.fasterxml.jackson.databind.JsonNode;

class ApiFailure extends RuntimeException {
    final int status;
    final String code;
    final JsonNode details;

    ApiFailure(int status, String code, String message) {
        this(status, code, message, null);
    }

    ApiFailure(int status, String code, String message, JsonNode details) {
        super(message);
        this.status = status;
        this.code = code;
        this.details = details;
    }

    static ApiFailure invalid(String message) {
        return new ApiFailure(400, "VALIDATION_ERROR", message);
    }

    static ApiFailure missing(String subject) {
        return new ApiFailure(404, "NOT_FOUND", subject + " was not found");
    }

    static ApiFailure conflict(String code, String message) {
        return new ApiFailure(409, code, message);
    }
}
