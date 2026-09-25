package com.deskcall.call;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

@Entity
@Table(name = "call_turns")
public class CallTurn {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "call_id", nullable = false)
    private Long callId;

    @Column(nullable = false)
    private int seq;

    @Column(nullable = false, length = 20)
    private String speaker;

    @Column(nullable = false, length = 4000)
    private String content;

    @Column(length = 40)
    private String state;

    protected CallTurn() {
    }

    public CallTurn(Long callId, int seq, String speaker, String content, String state) {
        this.callId = callId;
        this.seq = seq;
        this.speaker = speaker;
        this.content = content;
        this.state = state;
    }

    public int getSeq() { return seq; }
    public String getSpeaker() { return speaker; }
    public String getContent() { return content; }
    public String getState() { return state; }
}
