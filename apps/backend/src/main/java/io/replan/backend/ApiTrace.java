package io.replan.backend;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.Set;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import org.apache.logging.log4j.ThreadContext;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

@Component
class ApiTrace extends OncePerRequestFilter {
    private static final String HEADER = "X-Trace-Id";
    private static final Logger LOG = LogManager.getLogger(ApiTrace.class);
    private static final Set<String> STATIC_ACTIONS = Set.of("", "/instance", "/plans", "/plans/initial",
            "/plans/commit", "/plans/rollback", "/events", "/jobs", "/jobs/retry",
            "/constraints", "/agent/turn", "/confirmations", "/decisions");

    static String id(HttpServletRequest request) { return (String) request.getAttribute(HEADER); }

    @Override
    protected void doFilterInternal(HttpServletRequest request,HttpServletResponse response,FilterChain chain)
            throws ServletException, IOException {
        String id = request.getHeader(HEADER);
        if (id == null || !id.matches("[A-Za-z0-9._-]{1,128}")) id = World.id();
        request.setAttribute(HEADER,id);
        response.setHeader(HEADER,id);
        ThreadContext.put("trace_id",id);
        try {
            chain.doFilter(request,response);
        } finally {
            ThreadContext.put("method",Set.of("GET","POST").contains(request.getMethod()) ? request.getMethod() : "OTHER");
            ThreadContext.put("path",route(request.getRequestURI()));
            ThreadContext.put("status",String.valueOf(response.getStatus()));
            try {
                LOG.info("HTTP request completed");
            } finally {
                ThreadContext.removeAll(Set.of("trace_id","method","path","status"));
            }
        }
    }

    private String route(String uri) {
        if (uri.equals("/api/v1/health") || uri.equals("/api/v1/labs")) return uri;
        String prefix = "/api/v1/labs/";
        if (!uri.startsWith(prefix)) return "unmatched";
        String labRoute = prefix + "{lab}";
        int separator = uri.indexOf('/',prefix.length());
        String action = separator < 0 ? "" : uri.substring(separator);
        if (STATIC_ACTIONS.contains(action)) return labRoute + action;
        String[] parts = action.split("/");
        if (parts.length < 3 || parts.length > 4) return "unmatched";
        String ending = parts.length == 4 ? parts[3] : "";
        return switch (parts[1]) {
            case "plans" -> Set.of("","instance","diff").contains(ending)
                    ? labRoute + "/plans/{version}" + suffix(ending) : "unmatched";
            case "jobs" -> Set.of("","discard").contains(ending)
                    ? labRoute + "/jobs/{job}" + suffix(ending) : "unmatched";
            case "confirmations" -> Set.of("confirm","reject").contains(ending)
                    ? labRoute + "/confirmations/{confirmation}" + suffix(ending) : "unmatched";
            default -> "unmatched";
        };
    }

    private String suffix(String action) { return action.isEmpty() ? "" : "/" + action; }
}
