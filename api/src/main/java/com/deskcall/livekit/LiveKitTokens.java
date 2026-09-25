package com.deskcall.livekit;

import java.nio.charset.StandardCharsets;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.Map;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;

/** JWT HS256 untuk LiveKit (access token peserta dan token server API), tanpa dependency tambahan. */
public class LiveKitTokens {

    private static final Base64.Encoder B64 = Base64.getUrlEncoder().withoutPadding();

    private final String apiKey;
    private final byte[] secret;
    private final Clock clock;
    private final ObjectMapper mapper;

    public LiveKitTokens(String apiKey, String apiSecret, Clock clock, ObjectMapper mapper) {
        this.apiKey = apiKey;
        this.secret = apiSecret.getBytes(StandardCharsets.UTF_8);
        this.clock = clock;
        this.mapper = mapper;
    }

    public LiveKitClient.CustomerToken participantToken(String room, String identity, String name, Duration ttl,
                                                        boolean canPublishData) {
        Instant now = clock.instant();
        Instant exp = now.plus(ttl);
        Map<String, Object> video = new LinkedHashMap<>();
        video.put("roomJoin", true);
        video.put("room", room);
        video.put("canPublish", true);
        video.put("canSubscribe", true);
        video.put("canPublishData", canPublishData);
        Map<String, Object> claims = baseClaims(now, exp);
        claims.put("sub", identity);
        claims.put("name", name);
        claims.put("video", video);
        return new LiveKitClient.CustomerToken(sign(claims), exp);
    }

    /** Token untuk memanggil API server LiveKit (Twirp), dengan grant minimal per operasi. */
    public String serverToken(Map<String, Object> videoGrant, Duration ttl) {
        Instant now = clock.instant();
        Map<String, Object> claims = baseClaims(now, now.plus(ttl));
        claims.put("video", videoGrant);
        return sign(claims);
    }

    private Map<String, Object> baseClaims(Instant now, Instant exp) {
        Map<String, Object> claims = new LinkedHashMap<>();
        claims.put("iss", apiKey);
        claims.put("nbf", now.getEpochSecond());
        claims.put("exp", exp.getEpochSecond());
        return claims;
    }

    private String sign(Map<String, Object> claims) {
        try {
            String header = B64.encodeToString("{\"alg\":\"HS256\",\"typ\":\"JWT\"}".getBytes(StandardCharsets.UTF_8));
            String payload = B64.encodeToString(mapper.writeValueAsBytes(claims));
            String signingInput = header + "." + payload;
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(secret, "HmacSHA256"));
            String signature = B64.encodeToString(mac.doFinal(signingInput.getBytes(StandardCharsets.UTF_8)));
            return signingInput + "." + signature;
        } catch (JsonProcessingException | java.security.GeneralSecurityException e) {
            throw new IllegalStateException("Failed to sign LiveKit token", e);
        }
    }
}
