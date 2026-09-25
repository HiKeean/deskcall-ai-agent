package com.deskcall.livekit;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.charset.StandardCharsets;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.Base64;
import java.util.Map;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import org.junit.jupiter.api.Test;

class LiveKitTokensTest {

    static final String SECRET = "unit-test-secret-unit-test-secret-12345";
    static final Instant NOW = Instant.parse("2026-09-21T02:00:00Z");
    static final ObjectMapper MAPPER = new ObjectMapper();

    private final LiveKitTokens tokens =
            new LiveKitTokens("APIkey", SECRET, Clock.fixed(NOW, ZoneOffset.UTC), MAPPER);

    /** Verifikasi HS256 seperti server LiveKit: hitung ulang signature dan bandingkan. */
    static JsonNode verifyAndDecode(String jwt, String secret) throws Exception {
        String[] parts = jwt.split("\\.");
        assertThat(parts).hasSize(3);
        Mac mac = Mac.getInstance("HmacSHA256");
        mac.init(new SecretKeySpec(secret.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
        String expected = Base64.getUrlEncoder().withoutPadding()
                .encodeToString(mac.doFinal((parts[0] + "." + parts[1]).getBytes(StandardCharsets.UTF_8)));
        assertThat(parts[2]).isEqualTo(expected);
        assertThat(MAPPER.readTree(Base64.getUrlDecoder().decode(parts[0])).path("alg").asText()).isEqualTo("HS256");
        return MAPPER.readTree(Base64.getUrlDecoder().decode(parts[1]));
    }

    @Test
    void participantTokenCarriesJoinGrantForOneRoom() throws Exception {
        LiveKitClient.CustomerToken token =
                tokens.participantToken("deskcall-abc", "customer", "Budi", Duration.ofMinutes(5), false);

        JsonNode claims = verifyAndDecode(token.token(), SECRET);
        assertThat(claims.path("iss").asText()).isEqualTo("APIkey");
        assertThat(claims.path("sub").asText()).isEqualTo("customer");
        assertThat(claims.path("name").asText()).isEqualTo("Budi");
        assertThat(claims.path("nbf").asLong()).isEqualTo(NOW.getEpochSecond());
        assertThat(claims.path("exp").asLong()).isEqualTo(NOW.plusSeconds(300).getEpochSecond());
        assertThat(token.expiresAt()).isEqualTo(NOW.plusSeconds(300));
        JsonNode video = claims.path("video");
        assertThat(video.path("roomJoin").asBoolean()).isTrue();
        assertThat(video.path("room").asText()).isEqualTo("deskcall-abc");
        assertThat(video.path("canPublish").asBoolean()).isTrue();
        assertThat(video.path("canPublishData").asBoolean()).isFalse(); // suara saja; data channel ditutup
        assertThat(video.path("roomCreate").isMissingNode()).isTrue();
        assertThat(video.path("roomAdmin").isMissingNode()).isTrue();
    }

    @Test
    void dataChannelGrantIsOptIn() throws Exception {
        String jwt = tokens.participantToken("deskcall-abc", "customer", "Budi", Duration.ofMinutes(5), true).token();

        assertThat(verifyAndDecode(jwt, SECRET).path("video").path("canPublishData").asBoolean()).isTrue();
    }

    @Test
    void serverTokenCarriesOnlyRequestedGrant() throws Exception {
        String jwt = tokens.serverToken(Map.of("roomCreate", true), Duration.ofSeconds(60));

        JsonNode claims = verifyAndDecode(jwt, SECRET);
        assertThat(claims.path("video").path("roomCreate").asBoolean()).isTrue();
        assertThat(claims.path("video").has("roomJoin")).isFalse();
        assertThat(claims.path("exp").asLong()).isEqualTo(NOW.plusSeconds(60).getEpochSecond());
    }

    @Test
    void tokenSignedWithOtherSecretDoesNotVerify() {
        String jwt = tokens.serverToken(Map.of("roomCreate", true), Duration.ofSeconds(60));
        org.junit.jupiter.api.Assertions.assertThrows(AssertionError.class, () -> verifyAndDecode(jwt, "another-secret-another-secret-123"));
    }
}
