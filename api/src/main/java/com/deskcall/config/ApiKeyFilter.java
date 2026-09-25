package com.deskcall.config;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.List;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

/** Otentikasi service-to-service: header X-API-Key harus salah satu key di deskcall.security.api-keys. */
@Component
public class ApiKeyFilter extends OncePerRequestFilter {

    public static final String HEADER = "X-API-Key";

    private final List<byte[]> keys;

    public ApiKeyFilter(DeskcallProperties properties) {
        String raw = properties.security() == null ? null : properties.security().apiKeys();
        this.keys = raw == null ? List.of() : Arrays.stream(raw.split(","))
                .map(String::trim)
                .filter(s -> !s.isEmpty())
                .map(s -> s.getBytes(StandardCharsets.UTF_8))
                .toList();
        if (keys.isEmpty()) {
            throw new IllegalStateException("deskcall.security.api-keys (DESKCALL_API_KEYS) must not be empty");
        }
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        return !request.getRequestURI().startsWith("/api/");
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        if (!isValid(request.getHeader(HEADER))) {
            response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
            response.setContentType("application/problem+json");
            response.getWriter().write(
                    "{\"type\":\"about:blank\",\"title\":\"Unauthorized\",\"status\":401,"
                            + "\"detail\":\"Missing or invalid X-API-Key\"}");
            return;
        }
        chain.doFilter(request, response);
    }

    private boolean isValid(String provided) {
        if (provided == null || provided.isEmpty()) {
            return false;
        }
        byte[] candidate = provided.getBytes(StandardCharsets.UTF_8);
        boolean match = false;
        for (byte[] key : keys) { // bandingkan semua key agar waktu respons tidak membocorkan apa-apa
            match |= MessageDigest.isEqual(key, candidate);
        }
        return match;
    }
}
