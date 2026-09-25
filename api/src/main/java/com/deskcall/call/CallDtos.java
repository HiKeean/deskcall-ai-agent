package com.deskcall.call;

import java.time.Instant;
import java.time.LocalDate;
import java.util.List;

import com.fasterxml.jackson.annotation.JsonIgnore;

import jakarta.validation.Valid;
import jakarta.validation.constraints.AssertTrue;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Positive;
import jakarta.validation.constraints.PositiveOrZero;
import jakarta.validation.constraints.Size;

/** Bentuk request/response API. CreateCallRequest = CallContext (bahan kontrak untuk klarfinance). */
public final class CallDtos {

    private CallDtos() {
    }

    public record CreateCallRequest(
            @Size(max = 100) String externalCustomerId,
            @Size(max = 100) String externalLoanId,
            @NotBlank @Size(max = 200) String customerName,
            @NotBlank @Size(max = 100) String aiName,
            @NotBlank @Size(max = 200) String companyName,
            @NotNull @Positive Long installmentAmount,
            @NotNull @PositiveOrZero Long penaltyAmount,
            @NotNull LocalDate dueDate,
            @Pattern(regexp = "^\\d{1,2}[.:]\\d{2}$", message = "must look like 21.00") String autodebetCutoff,
            @Size(max = 200) String closingMagicWords,
            LocalDate birthDate,
            @Size(max = 500) String address,
            @Min(1) @Max(30) Integer maxPromiseDays,
            Boolean discloseAi) {

        @JsonIgnore
        @AssertTrue(message = "birthDate or address is required for identity verification")
        public boolean isVerificationDataPresent() {
            return birthDate != null || (address != null && !address.isBlank());
        }
    }

    public record CreateCallResponse(
            String callId,
            CallStatus status,
            String roomName,
            String livekitUrl,
            String customerIdentity,
            String customerToken,
            Instant tokenExpiresAt,
            int ringTimeoutSeconds) {
    }

    public record EventRequest(@NotNull EventType type, @Size(max = 2000) String detail) {
    }

    public record TurnRequest(
            @NotBlank @Pattern(regexp = "ai|customer", message = "must be ai or customer") String speaker,
            @NotBlank @Size(max = 4000) String text,
            @Size(max = 40) String state) {
    }

    public record ResultRequest(
            @NotNull CallTag tag,
            boolean verified,
            LocalDate ptpDate,
            @Size(max = 1000) String note,
            @Valid @Size(max = 300) List<TurnRequest> transcript,
            @Size(max = 50) List<@Size(max = 40) String> statesVisited) {
    }

    public record EventView(String type, String detail, Instant occurredAt) {
    }

    public record TurnView(int seq, String speaker, String text, String state) {
    }

    public record CallView(
            String callId,
            String externalCustomerId,
            String externalLoanId,
            String customerName,
            CallStatus status,
            CallTag tag,
            boolean verified,
            LocalDate ptpDate,
            String note,
            String roomName,
            Instant createdAt,
            Instant answeredAt,
            Instant endedAt,
            List<EventView> events,
            List<TurnView> transcript) {
    }

    public record PagedResponse<T>(List<T> items, int page, int size, long totalElements, int totalPages) {
    }
}
