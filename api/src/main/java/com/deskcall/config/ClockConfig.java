package com.deskcall.config;

import java.time.Clock;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class ClockConfig {

    /** Semua waktu di DB disimpan UTC. */
    @Bean
    public Clock clock() {
        return Clock.systemUTC();
    }
}
