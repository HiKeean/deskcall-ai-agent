package com.deskcall.livekit;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;

import com.deskcall.config.DeskcallProperties;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.sun.net.httpserver.HttpServer;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class HttpLiveKitClientTest {

    static final String SECRET = "unit-test-secret-unit-test-secret-12345";
    static final ObjectMapper MAPPER = new ObjectMapper();

    record Seen(String path, String authorization, JsonNode body) {
    }

    private HttpServer server;
    private final List<Seen> seen = new CopyOnWriteArrayList<>();
    private volatile int status = 200;
    private volatile String responseBody = "{}";
    private HttpLiveKitClient client;

    @BeforeEach
    void start() throws IOException {
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/", exchange -> {
            String body = new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8);
            seen.add(new Seen(exchange.getRequestURI().getPath(), exchange.getRequestHeaders().getFirst("Authorization"),
                    MAPPER.readTree(body)));
            byte[] out = responseBody.getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().add("Content-Type", "application/json");
            exchange.sendResponseHeaders(status, out.length);
            exchange.getResponseBody().write(out);
            exchange.close();
        });
        server.start();
        client = clientFor("ws://127.0.0.1:" + server.getAddress().getPort());
    }

    @AfterEach
    void stop() {
        server.stop(0);
    }

    private HttpLiveKitClient clientFor(String url) {
        DeskcallProperties.LiveKit config =
                new DeskcallProperties.LiveKit(url, "APIkey", SECRET, "deskcall-agent", "deskcall-", 300, 60, 2, false);
        LiveKitTokens tokens = new LiveKitTokens("APIkey", SECRET,
                Clock.fixed(Instant.parse("2026-09-21T02:00:00Z"), ZoneOffset.UTC), MAPPER);
        return new HttpLiveKitClient(config, tokens, MAPPER);
    }

    @Test
    void createRoomCallsTwirpWithRoomCreateGrant() throws Exception {
        client.createRoom("deskcall-abc");

        Seen call = seen.get(0);
        assertThat(call.path()).isEqualTo("/twirp/livekit.RoomService/CreateRoom");
        assertThat(call.body().path("name").asText()).isEqualTo("deskcall-abc");
        assertThat(call.body().path("empty_timeout").asInt()).isEqualTo(60);
        JsonNode claims = LiveKitTokensTest.verifyAndDecode(call.authorization().substring("Bearer ".length()), SECRET);
        assertThat(claims.path("video").path("roomCreate").asBoolean()).isTrue();
    }

    @Test
    void createAgentDispatchSendsMetadataAndReturnsId() throws Exception {
        responseBody = "{\"id\":\"AD_abc\",\"agent_name\":\"deskcall-agent\",\"room\":\"deskcall-abc\"}";

        String id = client.createAgentDispatch("deskcall-abc", "deskcall-agent", "{\"call_id\":\"x\"}");

        assertThat(id).isEqualTo("AD_abc");
        Seen call = seen.get(0);
        assertThat(call.path()).isEqualTo("/twirp/livekit.AgentDispatchService/CreateDispatch");
        assertThat(call.body().path("agent_name").asText()).isEqualTo("deskcall-agent");
        assertThat(call.body().path("room").asText()).isEqualTo("deskcall-abc");
        assertThat(call.body().path("metadata").asText()).isEqualTo("{\"call_id\":\"x\"}");
        JsonNode claims = LiveKitTokensTest.verifyAndDecode(call.authorization().substring("Bearer ".length()), SECRET);
        assertThat(claims.path("video").path("roomAdmin").asBoolean()).isTrue();
        assertThat(claims.path("video").path("room").asText()).isEqualTo("deskcall-abc");
    }

    @Test
    void deleteRoomCallsTwirp() {
        client.deleteRoom("deskcall-abc");

        assertThat(seen.get(0).path()).isEqualTo("/twirp/livekit.RoomService/DeleteRoom");
        assertThat(seen.get(0).body().path("room").asText()).isEqualTo("deskcall-abc");
    }

    @Test
    void nonSuccessResponseBecomesLiveKitException() {
        status = 401;
        responseBody = "{\"code\":\"unauthenticated\",\"msg\":\"invalid token\"}";

        assertThatThrownBy(() -> client.createRoom("deskcall-abc"))
                .isInstanceOf(LiveKitException.class)
                .hasMessageContaining("HTTP 401");
    }

    @Test
    void unreachableServerBecomesLiveKitException() {
        HttpLiveKitClient unreachable = clientFor("ws://127.0.0.1:1");

        assertThatThrownBy(() -> unreachable.createRoom("deskcall-abc")).isInstanceOf(LiveKitException.class);
    }

    @Test
    void wsUrlsAreMappedToHttp() {
        assertThat(HttpLiveKitClient.toHttp("wss://livekit.example.xyz")).isEqualTo("https://livekit.example.xyz");
        assertThat(HttpLiveKitClient.toHttp("ws://localhost:7880/")).isEqualTo("http://localhost:7880");
    }

    @Test
    void customerTokenIsIssuedLocallyForTheRoom() throws Exception {
        LiveKitClient.CustomerToken token = client.issueCustomerToken("deskcall-abc", "customer", "Budi");

        JsonNode claims = LiveKitTokensTest.verifyAndDecode(token.token(), SECRET);
        assertThat(claims.path("video").path("room").asText()).isEqualTo("deskcall-abc");
        assertThat(seen).isEmpty(); // tidak ada panggilan jaringan
        assertThat(new ArrayList<>(seen)).isEmpty();
    }
}
