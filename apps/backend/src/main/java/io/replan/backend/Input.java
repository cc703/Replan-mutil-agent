package io.replan.backend;

import com.fasterxml.jackson.databind.JsonNode;
import java.util.Set;

final class Input {
    private Input() {}

    static void fields(JsonNode body, String... names) {
        if (!body.isObject()) throw ApiFailure.invalid("Expected a JSON object");
        Set<String> allowed = Set.of(names);
        body.fieldNames().forEachRemaining(field -> {
            if (!allowed.contains(field)) throw ApiFailure.invalid("Unknown field: " + field);
        });
    }

    static String string(JsonNode body, String field) {
        JsonNode value = body.path(field);
        if (!value.isTextual() || value.asText().isBlank()) throw ApiFailure.invalid("Invalid " + field);
        return value.asText();
    }

    static JsonNode object(JsonNode body, String field) {
        if (!body.path(field).isObject()) throw ApiFailure.invalid("Invalid " + field);
        return body.path(field);
    }

    static int integer(JsonNode body, String field) {
        JsonNode value = body.path(field);
        if (!value.isIntegralNumber() || !value.canConvertToInt() || value.asInt() < 0)
            throw ApiFailure.invalid("Invalid " + field);
        return value.asInt();
    }

    static int optionalInt(JsonNode body, String field, int fallback) {
        return body.has(field) ? integer(body,field) : fallback;
    }
}
