package com.deskcall.livekit;

import java.time.Clock;

import com.deskcall.config.DeskcallProperties;
import com.fasterxml.jackson.databind.ObjectMapper;

import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class LiveKitConfig {

    @Bean
    public LiveKitTokens liveKitTokens(DeskcallProperties properties, Clock clock, ObjectMapper mapper) {
        DeskcallProperties.LiveKit lk = properties.livekit();
        return new LiveKitTokens(lk.apiKey(), lk.apiSecret(), clock, mapper);
    }

    @Bean
    @ConditionalOnMissingBean(LiveKitClient.class)
    public LiveKitClient liveKitClient(DeskcallProperties properties, LiveKitTokens tokens, ObjectMapper mapper) {
        return new HttpLiveKitClient(properties.livekit(), tokens, mapper);
    }
}
