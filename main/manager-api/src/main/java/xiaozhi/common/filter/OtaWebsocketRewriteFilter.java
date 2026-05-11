package xiaozhi.common.filter;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;
import org.springframework.web.util.ContentCachingResponseWrapper;

import java.io.IOException;
import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;

@Component
@Order(Ordered.LOWEST_PRECEDENCE)
public class OtaWebsocketRewriteFilter extends OncePerRequestFilter {

    private static final String FIXED_WEBSOCKET_URL = "ws://221.6.214.20:8001/xiaozhi/v1/";

    private final ObjectMapper objectMapper;

    public OtaWebsocketRewriteFilter(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        return !"/ota/".equals(request.getServletPath());
    }

    @Override
    protected void doFilterInternal(
            HttpServletRequest request,
            HttpServletResponse response,
            FilterChain filterChain
    ) throws ServletException, IOException {
        ContentCachingResponseWrapper responseWrapper = new ContentCachingResponseWrapper(response);
        filterChain.doFilter(request, responseWrapper);

        byte[] content = responseWrapper.getContentAsByteArray();
        if (content.length == 0 || !isJsonResponse(responseWrapper)) {
            responseWrapper.copyBodyToResponse();
            return;
        }

        Charset charset = getCharset(responseWrapper);
        String body = new String(content, charset);

        try {
            JsonNode root = objectMapper.readTree(body);
            if (root instanceof ObjectNode objectNode) {
                JsonNode websocketNode = objectNode.get("websocket");
                if (websocketNode instanceof ObjectNode websocketObject) {
                    websocketObject.put("url", FIXED_WEBSOCKET_URL);
                    byte[] rewritten = objectMapper.writeValueAsBytes(objectNode);
                    responseWrapper.resetBuffer();
                    responseWrapper.setContentLength(rewritten.length);
                    responseWrapper.getOutputStream().write(rewritten);
                }
            }
        } catch (Exception ignored) {
            // 非OTA JSON结构时保持原响应，避免影响其他接口。
        }

        responseWrapper.copyBodyToResponse();
    }

    private boolean isJsonResponse(ContentCachingResponseWrapper response) {
        String contentType = response.getContentType();
        return contentType != null && contentType.contains(MediaType.APPLICATION_JSON_VALUE);
    }

    private Charset getCharset(ContentCachingResponseWrapper response) {
        String encoding = response.getCharacterEncoding();
        if (encoding == null || encoding.isBlank()) {
            return StandardCharsets.UTF_8;
        }
        return Charset.forName(encoding);
    }
}
