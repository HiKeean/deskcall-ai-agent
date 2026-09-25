package com.deskcall.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "deskcall")
public record DeskcallProperties(Security security, LiveKit livekit, Call call, Sweeper sweeper) {

    public record Security(String apiKeys) {
    }

    public record LiveKit(String url, String apiKey, String apiSecret, String agentName, String roomPrefix,
                          int tokenTtlSeconds, int roomEmptyTimeoutSeconds, int httpTimeoutSeconds,
                          boolean customerCanPublishData) {
    }

    public record Call(int ringTimeoutSeconds, int maxDurationSeconds, boolean allowUndisclosedOpening) {
    }

    public record Sweeper(boolean enabled, long intervalMs) {
    }
}
