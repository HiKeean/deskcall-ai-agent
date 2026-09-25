package com.deskcall.livekit;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Clock;
import java.util.UUID;

import com.deskcall.config.DeskcallProperties;
import com.fasterxml.jackson.databind.ObjectMapper;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;

/**
 * Smoke test ke server LiveKit BENERAN (room `deskcall-smoke-*`, dibuat lalu langsung dihapus).
 * Hanya jalan kalau LIVEKIT_SMOKE=1, dengan LIVEKIT_URL / LIVEKIT_API_KEY / LIVEKIT_API_SECRET di environment:
 *   set -a; source ../.env; set +a; LIVEKIT_SMOKE=1 mvn test -Dtest=LiveKitSmokeTest
 */
@EnabledIfEnvironmentVariable(named = "LIVEKIT_SMOKE", matches = "1")
class LiveKitSmokeTest {

    @Test
    void createDispatchAndDeleteRoomAgainstRealServer() {
        ObjectMapper mapper = new ObjectMapper();
        DeskcallProperties.LiveKit config = new DeskcallProperties.LiveKit(
                System.getenv("LIVEKIT_URL"), System.getenv("LIVEKIT_API_KEY"), System.getenv("LIVEKIT_API_SECRET"),
                "deskcall-agent", "deskcall-", 300, 30, 10, false);
        LiveKitClient client = new HttpLiveKitClient(config,
                new LiveKitTokens(config.apiKey(), config.apiSecret(), Clock.systemUTC(), mapper), mapper);
        String room = "deskcall-smoke-" + UUID.randomUUID();

        client.createRoom(room);
        try {
            String dispatchId = client.createAgentDispatch(room, "deskcall-agent", "{\"call_id\":\"smoke\"}");
            assertThat(dispatchId).isNotBlank();
            assertThat(client.issueCustomerToken(room, "customer", "Smoke").token()).isNotBlank();
        } finally {
            client.deleteRoom(room);
        }
    }
}
