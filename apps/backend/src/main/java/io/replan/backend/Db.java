package io.replan.backend;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.regex.Pattern;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.SelectProvider;
import org.apache.ibatis.annotations.UpdateProvider;
import org.springframework.stereotype.Component;

@Component
class Db {
    @Mapper
    public interface Statements {
        @SelectProvider(type = Sql.class, method = "render")
        String query(Map<String, Object> arguments);

        @UpdateProvider(type = Sql.class, method = "render")
        int execute(Map<String, Object> arguments);
    }

    public static class Sql {
        private static final Pattern PARAMETER = Pattern.compile("(?<!:):([a-z][a-z_0-9]*)");

        public static String render(Map<String, Object> arguments) {
            return PARAMETER.matcher((String) arguments.get("sql"))
                    .replaceAll("#{parameters.$1,jdbcType=OTHER}");
        }
    }

    final ObjectMapper json;
    private final Statements statements;

    Db(ObjectMapper json, Statements statements) {
        this.json = json;
        this.statements = statements;
    }

    JsonNode parse(String value) {
        try {
            return json.readTree(value);
        } catch (JsonProcessingException e) {
            throw new IllegalStateException("Invalid stored JSON", e);
        }
    }

    int write(String sql, Object... pairs) {
        return statements.execute(arguments(sql, pairs));
    }

    ArrayNode rows(String sql, Object... pairs) {
        String wrapped = "SELECT COALESCE(json_agg(row_to_json(p7_query_row.*)), '[]'::json)::text FROM (" + sql + ") p7_query_row";
        return (ArrayNode) parse(statements.query(arguments(wrapped, pairs)));
    }

    JsonNode one(String sql, Object... pairs) {
        return rows(sql, pairs).path(0);
    }

    ObjectNode object(Object... pairs) {
        ObjectNode object = json.createObjectNode();
        for (int i = 0; i < pairs.length; i += 2) {
            object.set((String) pairs[i], json.valueToTree(pairs[i + 1]));
        }
        return object;
    }

    private Map<String, Object> arguments(String sql, Object[] pairs) {
        Map<String, Object> parameters = new LinkedHashMap<>();
        for (int i = 0; i < pairs.length; i += 2) {
            Object value = pairs[i + 1];
            parameters.put((String) pairs[i], value instanceof JsonNode node ? node.toString() : value);
        }
        return Map.of("sql", sql, "parameters", parameters);
    }
}
