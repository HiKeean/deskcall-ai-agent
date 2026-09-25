package com.deskcall.call;

import java.time.LocalDateTime;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

@Entity
@Table(name = "call_events")
public class CallEvent {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "call_id", nullable = false)
    private Long callId;

    @Column(nullable = false, length = 40)
    private String type;

    @Column(length = 2000)
    private String detail;

    @Column(name = "occurred_at", nullable = false)
    private LocalDateTime occurredAt;

    protected CallEvent() {
    }

    public CallEvent(Long callId, String type, String detail, LocalDateTime occurredAt) {
        this.callId = callId;
        this.type = type;
        this.detail = detail != null && detail.length() > 2000 ? detail.substring(0, 2000) : detail;
        this.occurredAt = occurredAt;
    }

    public String getType() { return type; }
    public String getDetail() { return detail; }
    public LocalDateTime getOccurredAt() { return occurredAt; }
}
