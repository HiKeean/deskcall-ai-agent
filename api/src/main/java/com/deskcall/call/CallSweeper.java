package com.deskcall.call;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

/** Menutup panggilan yang macet: tidak di-accept (NSTD) atau tidak pernah dapat hasil (OTHERS). */
@Component
@ConditionalOnProperty(prefix = "deskcall.sweeper", name = "enabled", havingValue = "true", matchIfMissing = true)
public class CallSweeper {

    private static final Logger log = LoggerFactory.getLogger(CallSweeper.class);

    private final CallService service;

    public CallSweeper(CallService service) {
        this.service = service;
    }

    @Scheduled(fixedDelayString = "${deskcall.sweeper.interval-ms:5000}")
    public void sweep() {
        try {
            int unanswered = service.expireUnanswered();
            int overdue = service.expireOverdue();
            if (unanswered + overdue > 0) {
                log.info("Sweeper closed {} unanswered and {} overdue calls", unanswered, overdue);
            }
        } catch (RuntimeException e) {
            log.warn("Sweeper run failed: {}", e.getMessage());
        }
    }
}
