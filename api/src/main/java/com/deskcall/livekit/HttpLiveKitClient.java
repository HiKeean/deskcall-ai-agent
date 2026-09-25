package com.deskcall.livekit;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.Map;

import com.deskcall.config.DeskcallProperties;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

/** Memanggil API server LiveKit lewat Twirp (JSON over HTTPS). */
public class HttpLiveKitClient implements LiveKitClient {

    private static final String ROOM_SERVICE = "/twirp/livekit.RoomService/";
    private static final String DISPATCH_SERVICE = "/twirp/livekit.AgentDispatchService/";
    private static final Duration SERVER_TOKEN_TTL = Duration.ofSeconds(60);

    private final DeskcallProperties.LiveKit config;
    private final LiveKitTokens tokens;
    private final ObjectMapper mapper;
    private final HttpClient http;
    private final String baseUrl;

    public HttpLiveKitClient(DeskcallProperties.LiveKit config, LiveKitTokens tokens, ObjectMapper mapper) {
        this.config = config;
        this.tokens = tokens;
        this.mapper = mapper;
        this.http = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(config.httpTimeoutSeconds())).build();
        this.baseUrl = toHttp(config.url());
    }

    static String toHttp(String url) {
        String http = url.startsWith("wss://") ? "https://" + url.substring(6)
                : url.startsWith("ws://") ? "http://" + url.substring(5) : url;
        return http.endsWith("/") ? http.substring(0, http.length() - 1) : http;
    }

    @Override
    public String url() {
        return config.url();
    }

    @Override
    public void createRoom(String roomName) {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("name", roomName);
        body.put("empty_timeout", config.roomEmptyTimeoutSeconds());
        call(ROOM_SERVICE + "CreateRoom", Map.of("roomCreate", true), body);
    }

    @Override
    public String createAgentDispatch(String roomName, String agentName, String metadataJson) {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("agent_name", agentName);
        body.put("room", roomName);
        body.put("metadata", metadataJson);
        Map<String, Object> grant = new LinkedHashMap<>();
        grant.put("roomAdmin", true);
        grant.put("room", roomName);
        JsonNode response = call(DISPATCH_SERVICE + "CreateDispatch", grant, body);
        return response.path("id").asText(null);
    }

    @Override
    public void deleteRoom(String roomName) {
        call(ROOM_SERVICE + "DeleteRoom", Map.of("roomCreate", true), Map.of("room", roomName));
    }

    @Override
    public CustomerToken issueCustomerToken(String roomName, String identity, String displayName) {
        return tokens.participantToken(roomName, identity, displayName, Duration.ofSeconds(config.tokenTtlSeconds()),
                config.customerCanPublishData());
    }

    private JsonNode call(String path, Map<String, Object> grant, Object body) {
        try {
            HttpRequest request = HttpRequest.newBuilder(URI.create(baseUrl + path))
                    .timeout(Duration.ofSeconds(config.httpTimeoutSeconds()))
                    .header("Authorization", "Bearer " + tokens.serverToken(grant, SERVER_TOKEN_TTL))
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(mapper.writeValueAsString(body)))
                    .build();
            HttpResponse<String> response = http.send(request, HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() / 100 != 2) {
                throw new LiveKitException("LiveKit " + path + " returned HTTP " + response.statusCode() + ": "
                        + truncate(response.body()));
            }
            return response.body() == null || response.body().isBlank()
                    ? mapper.createObjectNode() : mapper.readTree(response.body());
        } catch (JsonProcessingException e) {
            throw new LiveKitException("Invalid JSON for LiveKit " + path, e);
        } catch (IOException e) {
            throw new LiveKitException("Cannot reach LiveKit for " + path, e);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new LiveKitException("Interrupted calling LiveKit " + path, e);
        }
    }

    private static String truncate(String s) {
        return s == null ? "" : s.length() <= 300 ? s : s.substring(0, 300) + "...";
    }
}
