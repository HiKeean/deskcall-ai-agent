package com.deskcall.call;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doReturn;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneId;
import java.time.ZoneOffset;

import com.deskcall.livekit.LiveKitClient;
import com.deskcall.livekit.LiveKitException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Import;
import org.springframework.context.annotation.Primary;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@Import(CallApiTest.TestClock.class)
class CallApiTest {

    static class MutableClock extends Clock {
        private volatile Instant now = Instant.parse("2026-09-21T02:00:00Z");

        void advance(Duration d) {
            now = now.plus(d);
        }

        void reset() {
            now = Instant.parse("2026-09-21T02:00:00Z");
        }

        @Override
        public ZoneId getZone() {
            return ZoneOffset.UTC;
        }

        @Override
        public Clock withZone(ZoneId zone) {
            return this;
        }

        @Override
        public Instant instant() {
            return now;
        }
    }

    @TestConfiguration
    static class TestClock {
        @Bean
        @Primary
        MutableClock mutableClock() {
            return new MutableClock();
        }
    }

    static final String KEY = "test-key";

    @Autowired MockMvc mvc;
    @Autowired ObjectMapper mapper;
    @Autowired MutableClock clock;
    @Autowired CallService service;
    @Autowired CallRepository calls;
    @Autowired CallEventRepository events;
    @Autowired CallTurnRepository turns;
    @MockitoBean LiveKitClient liveKit;

    @BeforeEach
    void setUp() {
        clock.reset();
        turns.deleteAll();
        events.deleteAll();
        calls.deleteAll();
        when(liveKit.url()).thenReturn("wss://livekit.test");
        when(liveKit.createAgentDispatch(anyString(), anyString(), anyString())).thenReturn("AD_1");
        when(liveKit.issueCustomerToken(anyString(), anyString(), anyString()))
                .thenReturn(new LiveKitClient.CustomerToken("jwt-token", Instant.parse("2026-09-21T02:05:00Z")));
    }

    // --- helpers ---

    static String body(String loanId) {
        return """
                {"externalCustomerId":"C-1","externalLoanId":"%s","customerName":"Budi Santoso",
                 "aiName":"Sinta","companyName":"PT Demo Finance","installmentAmount":1500000,
                 "penaltyAmount":90000,"dueDate":"2026-09-18","autodebetCutoff":"21.00",
                 "birthDate":"1990-08-17","address":"Jl. Merdeka No. 10 Bandung","maxPromiseDays":9}
                """.formatted(loanId);
    }

    ResultActions send(org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder req)
            throws Exception {
        return mvc.perform(req.header("X-API-Key", KEY).contentType(MediaType.APPLICATION_JSON));
    }

    String createCall(String loanId) throws Exception {
        String json = send(post("/api/v1/calls").content(body(loanId)))
                .andExpect(status().isCreated()).andReturn().getResponse().getContentAsString();
        return mapper.readTree(json).path("callId").asText();
    }

    ResultActions event(String callId, String type, String detail) throws Exception {
        String d = detail == null ? "" : ",\"detail\":\"" + detail + "\"";
        return send(post("/api/v1/calls/" + callId + "/events").content("{\"type\":\"" + type + "\"" + d + "}"));
    }

    static String result(String tag, String ptpDate) {
        String ptp = ptpDate == null ? "" : ",\"ptpDate\":\"" + ptpDate + "\"";
        return """
                {"tag":"%s","verified":true%s,"note":"catatan",
                 "transcript":[{"speaker":"ai","text":"Selamat pagi","state":"AWAIT_IDENTITY"},
                               {"speaker":"customer","text":"iya betul","state":"AWAIT_IDENTITY"}],
                 "statesVisited":["AWAIT_IDENTITY","CLOSING"]}
                """.formatted(tag, ptp);
    }

    // --- buat panggilan ---

    @Test
    void createBuildsRoomDispatchesAgentAndReturnsCustomerToken() throws Exception {
        send(post("/api/v1/calls").content(body("L-1")))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.callId").isNotEmpty())
                .andExpect(jsonPath("$.status").value("CREATED"))
                .andExpect(jsonPath("$.roomName").value(org.hamcrest.Matchers.startsWith("deskcall-")))
                .andExpect(jsonPath("$.livekitUrl").value("wss://livekit.test"))
                .andExpect(jsonPath("$.customerIdentity").value("customer"))
                .andExpect(jsonPath("$.customerToken").value("jwt-token"))
                .andExpect(jsonPath("$.tokenExpiresAt").value("2026-09-21T02:05:00Z"))
                .andExpect(jsonPath("$.ringTimeoutSeconds").value(45));

        ArgumentCaptor<String> room = ArgumentCaptor.forClass(String.class);
        ArgumentCaptor<String> metadata = ArgumentCaptor.forClass(String.class);
        verify(liveKit).createRoom(room.capture());
        verify(liveKit).createAgentDispatch(eq(room.getValue()), eq("deskcall-agent"), metadata.capture());

        JsonNode meta = mapper.readTree(metadata.getValue());
        assertThat(meta.path("call_id").asText()).isEqualTo(room.getValue().substring("deskcall-".length()));
        assertThat(meta.path("customer_name").asText()).isEqualTo("Budi Santoso");
        assertThat(meta.path("installment_amount").asLong()).isEqualTo(1_500_000);
        assertThat(meta.path("due_date").asText()).isEqualTo("2026-09-18");
        assertThat(meta.path("birth_date").asText()).isEqualTo("1990-08-17");
        assertThat(meta.path("address").asText()).isEqualTo("Jl. Merdeka No. 10 Bandung");
        assertThat(meta.path("max_promise_days").asInt()).isEqualTo(9);
        assertThat(meta.path("external_loan_id").asText()).isEqualTo("L-1");
    }

    @Test
    void verificationDataIsNotPersisted() throws Exception {
        String callId = createCall("L-1");

        String json = send(get("/api/v1/calls/" + callId)).andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();
        assertThat(json).doesNotContain("1990-08-17").doesNotContain("Merdeka");
        assertThat(calls.findByCallUid(callId)).isPresent();
    }

    @Test
    void createRejectsInvalidRequests() throws Exception {
        send(post("/api/v1/calls").content("{}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.errors.customerName").exists())
                .andExpect(jsonPath("$.errors.installmentAmount").exists());

        String noVerification = body("L-1")
                .replace("\"birthDate\":\"1990-08-17\",\"address\":\"Jl. Merdeka No. 10 Bandung\",", "");
        assertThat(noVerification).doesNotContain("birthDate").doesNotContain("address");
        send(post("/api/v1/calls").content(noVerification))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.errors.verificationDataPresent").exists());

        send(post("/api/v1/calls").content(body("L-1").replace("\"penaltyAmount\":90000", "\"penaltyAmount\":-1")))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.errors.penaltyAmount").exists());
        verify(liveKit, never()).createRoom(anyString());
    }

    @Test
    void requiresApiKey() throws Exception {
        mvc.perform(post("/api/v1/calls").contentType(MediaType.APPLICATION_JSON).content(body("L-1")))
                .andExpect(status().isUnauthorized());
        mvc.perform(get("/api/v1/calls").header("X-API-Key", "wrong")).andExpect(status().isUnauthorized());
        mvc.perform(get("/api/v1/calls").header("X-API-Key", "other-key")).andExpect(status().isOk());
        mvc.perform(get("/actuator/health")).andExpect(status().isOk());
    }

    @Test
    void secondActiveCallForSameLoanIsRejectedUntilFirstEnds() throws Exception {
        String first = createCall("L-1");

        send(post("/api/v1/calls").content(body("L-1")))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("ACTIVE_CALL_EXISTS"));
        createCall("L-2"); // loan lain tidak terpengaruh

        event(first, "CUSTOMER_DECLINED", null).andExpect(status().isOk());
        createCall("L-1");
    }

    @Test
    void liveKitFailureMarksCallFailedAndReturns502() throws Exception {
        doThrow(new LiveKitException("LiveKit dispatch returned HTTP 500"))
                .when(liveKit).createAgentDispatch(anyString(), anyString(), anyString());

        send(post("/api/v1/calls").content(body("L-1")))
                .andExpect(status().isBadGateway())
                .andExpect(jsonPath("$.code").value("LIVEKIT_UNAVAILABLE"));

        send(get("/api/v1/calls").queryParam("status", "FAILED"))
                .andExpect(jsonPath("$.totalElements").value(1))
                .andExpect(jsonPath("$.items[0].note").value(org.hamcrest.Matchers.containsString("Gagal menyiapkan")));
        verify(liveKit).deleteRoom(anyString());
        // loan yang gagal boleh dicoba lagi
        doReturn("AD_2").when(liveKit).createAgentDispatch(anyString(), anyString(), anyString());
        createCall("L-1");
    }

    // --- event lifecycle ---

    @Test
    void customerJoinedMovesToAnswered() throws Exception {
        String id = createCall("L-1");

        event(id, "CUSTOMER_JOINED", null)
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("ANSWERED"))
                .andExpect(jsonPath("$.answeredAt").value("2026-09-21T02:00:00Z"));
    }

    @Test
    void declineIsNstd() throws Exception {
        String id = createCall("L-1");

        event(id, "CUSTOMER_DECLINED", null)
                .andExpect(jsonPath("$.status").value("ENDED"))
                .andExpect(jsonPath("$.tag").value("NSTD"));
        verify(liveKit).deleteRoom("deskcall-" + id);
    }

    @Test
    void unreachableIsCbrWithReason() throws Exception {
        String id = createCall("L-1");

        event(id, "UNREACHABLE", "tidak ada token FCM")
                .andExpect(jsonPath("$.status").value("ENDED"))
                .andExpect(jsonPath("$.tag").value("CBR"))
                .andExpect(jsonPath("$.note").value("tidak ada token FCM"));
    }

    @Test
    void leavingBeforeAnsweringIsIgnoredButLeavingAfterAnsweringIsOthers() throws Exception {
        String id = createCall("L-1");
        event(id, "CUSTOMER_LEFT", null).andExpect(jsonPath("$.status").value("CREATED"));

        event(id, "CUSTOMER_JOINED", null);
        event(id, "CUSTOMER_LEFT", null)
                .andExpect(jsonPath("$.status").value("ENDED"))
                .andExpect(jsonPath("$.tag").value("OTHERS"));
    }

    @Test
    void eventsAreRecordedInOrder() throws Exception {
        String id = createCall("L-1");
        event(id, "AGENT_JOINED", null);
        event(id, "CUSTOMER_JOINED", null);

        send(get("/api/v1/calls/" + id))
                .andExpect(jsonPath("$.events[*].type")
                        .value(org.hamcrest.Matchers.contains("CREATED", "DISPATCHED", "AGENT_JOINED", "CUSTOMER_JOINED")));
    }

    @Test
    void unknownEventTypeAndUnknownCallAreRejected() throws Exception {
        String id = createCall("L-1");
        event(id, "EXPLODED", null).andExpect(status().isBadRequest());
        event("no-such-call", "CUSTOMER_JOINED", null).andExpect(status().isNotFound());
        send(get("/api/v1/calls/no-such-call")).andExpect(status().isNotFound());
    }

    // --- hasil ---

    @Test
    void resultStoresTagPtpAndTranscript() throws Exception {
        String id = createCall("L-1");
        event(id, "CUSTOMER_JOINED", null);

        send(post("/api/v1/calls/" + id + "/result").content(result("PTP", "2026-09-24")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("ENDED"))
                .andExpect(jsonPath("$.tag").value("PTP"))
                .andExpect(jsonPath("$.verified").value(true))
                .andExpect(jsonPath("$.ptpDate").value("2026-09-24"))
                .andExpect(jsonPath("$.note").value("catatan"))
                .andExpect(jsonPath("$.endedAt").value("2026-09-21T02:00:00Z"));

        send(get("/api/v1/calls/" + id).queryParam("includeTranscript", "true"))
                .andExpect(jsonPath("$.transcript.length()").value(2))
                .andExpect(jsonPath("$.transcript[0].seq").value(1))
                .andExpect(jsonPath("$.transcript[0].speaker").value("ai"))
                .andExpect(jsonPath("$.transcript[1].text").value("iya betul"))
                .andExpect(jsonPath("$.events[-1:].type").value("RESULT_RECEIVED"));
        send(get("/api/v1/calls/" + id)).andExpect(jsonPath("$.transcript").doesNotExist());
        verify(liveKit).deleteRoom("deskcall-" + id);
    }

    @Test
    void resultCanOnlyBeSubmittedOnce() throws Exception {
        String id = createCall("L-1");
        send(post("/api/v1/calls/" + id + "/result").content(result("CBC_NO_DEAL", null))).andExpect(status().isOk());

        send(post("/api/v1/calls/" + id + "/result").content(result("PTP", "2026-09-24")))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("RESULT_ALREADY_RECEIVED"));
        send(get("/api/v1/calls/" + id)).andExpect(jsonPath("$.tag").value("CBC_NO_DEAL"));
    }

    @Test
    void ptpNeedsDateAndOtherTagsMustNotHaveOne() throws Exception {
        String id = createCall("L-1");

        send(post("/api/v1/calls/" + id + "/result").content(result("PTP", null))).andExpect(status().isBadRequest());
        send(post("/api/v1/calls/" + id + "/result").content(result("UNK", "2026-09-24")))
                .andExpect(status().isBadRequest());
        send(post("/api/v1/calls/" + id + "/result").content(result("BOGUS", null))).andExpect(status().isBadRequest());
        send(get("/api/v1/calls/" + id)).andExpect(jsonPath("$.status").value("CREATED"));
    }

    @Test
    void resultFromAgentOverridesOthersSetByLeaveEvent() throws Exception {
        String id = createCall("L-1");
        event(id, "CUSTOMER_JOINED", null);
        event(id, "CUSTOMER_LEFT", null).andExpect(jsonPath("$.tag").value("OTHERS"));

        send(post("/api/v1/calls/" + id + "/result").content(result("PTP", "2026-09-22")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.tag").value("PTP"));
    }

    @Test
    void resultIsRejectedForFailedCall() throws Exception {
        doThrow(new LiveKitException("down")).when(liveKit).createRoom(anyString());
        send(post("/api/v1/calls").content(body("L-1"))).andExpect(status().isBadGateway());
        String id = calls.findAll().get(0).getCallUid();

        send(post("/api/v1/calls/" + id + "/result").content(result("CBC_NO_DEAL", null)))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("CALL_FAILED"));
    }

    // --- list ---

    @Test
    void listFiltersAndPaginates() throws Exception {
        String a = createCall("L-1");
        createCall("L-2");
        createCall("L-3");
        event(a, "CUSTOMER_DECLINED", null);

        send(get("/api/v1/calls").queryParam("externalLoanId", "L-2"))
                .andExpect(jsonPath("$.totalElements").value(1))
                .andExpect(jsonPath("$.items[0].externalLoanId").value("L-2"))
                .andExpect(jsonPath("$.items[0].events").doesNotExist());
        send(get("/api/v1/calls").queryParam("status", "CREATED"))
                .andExpect(jsonPath("$.totalElements").value(2));
        send(get("/api/v1/calls").queryParam("tag", "NSTD"))
                .andExpect(jsonPath("$.totalElements").value(1))
                .andExpect(jsonPath("$.items[0].callId").value(a));
        send(get("/api/v1/calls").queryParam("size", "2"))
                .andExpect(jsonPath("$.items.length()").value(2))
                .andExpect(jsonPath("$.totalElements").value(3))
                .andExpect(jsonPath("$.totalPages").value(2))
                .andExpect(jsonPath("$.items[0].externalLoanId").value("L-3")); // terbaru dulu
        send(get("/api/v1/calls").queryParam("size", "2").queryParam("page", "1"))
                .andExpect(jsonPath("$.items.length()").value(1));
    }

    @Test
    void listRejectsBadParameters() throws Exception {
        send(get("/api/v1/calls").queryParam("size", "0")).andExpect(status().isBadRequest());
        send(get("/api/v1/calls").queryParam("size", "101")).andExpect(status().isBadRequest());
        send(get("/api/v1/calls").queryParam("tag", "BOGUS")).andExpect(status().isBadRequest());
    }

    // --- sweeper ---

    @Test
    void unansweredCallExpiresToNstdAfterRingTimeout() throws Exception {
        String id = createCall("L-1");

        clock.advance(Duration.ofSeconds(44));
        assertThat(service.expireUnanswered()).isZero();
        send(get("/api/v1/calls/" + id)).andExpect(jsonPath("$.status").value("CREATED"));

        clock.advance(Duration.ofSeconds(2));
        assertThat(service.expireUnanswered()).isEqualTo(1);
        send(get("/api/v1/calls/" + id))
                .andExpect(jsonPath("$.status").value("ENDED"))
                .andExpect(jsonPath("$.tag").value("NSTD"))
                .andExpect(jsonPath("$.events[-1:].type").value("RING_TIMEOUT"));
        verify(liveKit).deleteRoom("deskcall-" + id);
        assertThat(service.expireUnanswered()).isZero(); // idempoten
    }

    @Test
    void answeredCallWithoutResultExpiresToOthers() throws Exception {
        String id = createCall("L-1");
        event(id, "CUSTOMER_JOINED", null);

        clock.advance(Duration.ofSeconds(899));
        assertThat(service.expireOverdue()).isZero();
        clock.advance(Duration.ofSeconds(2));
        assertThat(service.expireOverdue()).isEqualTo(1);

        send(get("/api/v1/calls/" + id))
                .andExpect(jsonPath("$.status").value("ENDED"))
                .andExpect(jsonPath("$.tag").value("OTHERS"));
    }

    @Test
    void answeredCallIsNotTouchedByRingTimeout() throws Exception {
        String id = createCall("L-1");
        event(id, "CUSTOMER_JOINED", null);

        clock.advance(Duration.ofSeconds(120));

        assertThat(service.expireUnanswered()).isZero();
        send(get("/api/v1/calls/" + id)).andExpect(jsonPath("$.status").value("ANSWERED"));
    }
}
