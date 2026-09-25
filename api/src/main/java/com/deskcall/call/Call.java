package com.deskcall.call;

import java.time.LocalDate;
import java.time.LocalDateTime;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import jakarta.persistence.Version;

/**
 * Satu panggilan. Sengaja TIDAK menyimpan tanggal lahir / alamat nasabah (data verifikasi) —
 * data itu hanya lewat metadata dispatch ke agent. Status/tag disimpan sebagai String (lihat CallStatus/CallTag).
 */
@Entity
@Table(name = "calls")
public class Call {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "call_uid", nullable = false, updatable = false, length = 36)
    private String callUid;

    @Column(name = "external_customer_id", length = 100)
    private String externalCustomerId;

    @Column(name = "external_loan_id", length = 100)
    private String externalLoanId;

    @Column(name = "customer_name", nullable = false, length = 200)
    private String customerName;

    @Column(name = "installment_amount", nullable = false)
    private long installmentAmount;

    @Column(name = "penalty_amount", nullable = false)
    private long penaltyAmount;

    @Column(name = "due_date", nullable = false)
    private LocalDate dueDate;

    @Column(nullable = false, length = 20)
    private String status;

    @Column(length = 30)
    private String tag;

    @Column(nullable = false)
    private boolean verified;

    @Column(name = "ptp_date")
    private LocalDate ptpDate;

    @Column(length = 1000)
    private String note;

    @Column(name = "room_name", nullable = false, length = 100)
    private String roomName;

    @Column(name = "created_at", nullable = false)
    private LocalDateTime createdAt;

    @Column(name = "answered_at")
    private LocalDateTime answeredAt;

    @Column(name = "ended_at")
    private LocalDateTime endedAt;

    @Column(name = "result_received_at")
    private LocalDateTime resultReceivedAt;

    @Version
    private long version;

    protected Call() {
    }

    public Call(String callUid, String externalCustomerId, String externalLoanId, String customerName,
                long installmentAmount, long penaltyAmount, LocalDate dueDate, String roomName,
                LocalDateTime createdAt) {
        this.callUid = callUid;
        this.externalCustomerId = externalCustomerId;
        this.externalLoanId = externalLoanId;
        this.customerName = customerName;
        this.installmentAmount = installmentAmount;
        this.penaltyAmount = penaltyAmount;
        this.dueDate = dueDate;
        this.roomName = roomName;
        this.createdAt = createdAt;
        this.status = CallStatus.CREATED.name();
    }

    public Long getId() { return id; }
    public String getCallUid() { return callUid; }
    public String getExternalCustomerId() { return externalCustomerId; }
    public String getExternalLoanId() { return externalLoanId; }
    public String getCustomerName() { return customerName; }
    public long getInstallmentAmount() { return installmentAmount; }
    public long getPenaltyAmount() { return penaltyAmount; }
    public LocalDate getDueDate() { return dueDate; }
    public CallStatus getStatus() { return CallStatus.valueOf(status); }
    public CallTag getTag() { return tag == null ? null : CallTag.valueOf(tag); }
    public boolean isVerified() { return verified; }
    public LocalDate getPtpDate() { return ptpDate; }
    public String getNote() { return note; }
    public String getRoomName() { return roomName; }
    public LocalDateTime getCreatedAt() { return createdAt; }
    public LocalDateTime getAnsweredAt() { return answeredAt; }
    public LocalDateTime getEndedAt() { return endedAt; }
    public LocalDateTime getResultReceivedAt() { return resultReceivedAt; }

    public void markAnswered(LocalDateTime now) {
        this.status = CallStatus.ANSWERED.name();
        this.answeredAt = now;
    }

    public void markEnded(CallTag tag, String note, LocalDateTime now) {
        this.status = CallStatus.ENDED.name();
        this.tag = tag.name();
        this.note = truncate(note, 1000);
        if (this.endedAt == null) {
            this.endedAt = now;
        }
    }

    public void markFailed(String note, LocalDateTime now) {
        this.status = CallStatus.FAILED.name();
        this.note = truncate(note, 1000);
        this.endedAt = now;
    }

    public void applyResult(CallTag tag, boolean verified, LocalDate ptpDate, String note, LocalDateTime now) {
        markEnded(tag, note, now);
        this.verified = verified;
        this.ptpDate = ptpDate;
        this.resultReceivedAt = now;
    }

    private static String truncate(String s, int max) {
        return s == null || s.length() <= max ? s : s.substring(0, max);
    }
}
