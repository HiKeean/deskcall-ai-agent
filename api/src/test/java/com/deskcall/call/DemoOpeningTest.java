package com.deskcall.call;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.time.Instant;

import com.deskcall.livekit.LiveKitClient;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

/** discloseAi=false (pembuka demo) hanya boleh kalau environment mengizinkan. */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class DemoOpeningTest {

    @Autowired MockMvc mvc;
    @Autowired ObjectMapper mapper;
    @Autowired CallRepository calls;
    @Autowired CallEventRepository events;
    @Autowired CallTurnRepository turns;
    @MockitoBean LiveKitClient liveKit;

    static String body(String extra) {
        return """
                {"externalLoanId":"D-%s","customerName":"Budi","aiName":"Albert","companyName":"KlarFinance",
                 "installmentAmount":1000,"penaltyAmount":0,"dueDate":"2026-09-18","birthDate":"1990-08-17"%s}
                """.formatted(System.nanoTime(), extra);
    }

    @BeforeEach
    void setUp() {
        turns.deleteAll();
        events.deleteAll();
        calls.deleteAll();
        when(liveKit.url()).thenReturn("wss://livekit.test");
        when(liveKit.createAgentDispatch(anyString(), anyString(), anyString())).thenReturn("AD_1");
        when(liveKit.issueCustomerToken(anyString(), anyString(), anyString()))
                .thenReturn(new LiveKitClient.CustomerToken("jwt", Instant.parse("2026-09-21T02:05:00Z")));
    }

    @Test
    void undisclosedOpeningIsRejectedByDefault() throws Exception {
        mvc.perform(post("/api/v1/calls").header("X-API-Key", "test-key").contentType(MediaType.APPLICATION_JSON)
                        .content(body(",\"discloseAi\":false")))
                .andExpect(status().isBadRequest());
        assertThat(calls.count()).isZero();
    }

    @Test
    void defaultAndExplicitTrueDoNotAddTheFlag() throws Exception {
        for (String extra : new String[]{"", ",\"discloseAi\":true"}) {
            mvc.perform(post("/api/v1/calls").header("X-API-Key", "test-key").contentType(MediaType.APPLICATION_JSON)
                    .content(body(extra))).andExpect(status().isCreated());
        }
        ArgumentCaptor<String> metadata = ArgumentCaptor.forClass(String.class);
        verify(liveKit, org.mockito.Mockito.times(2)).createAgentDispatch(anyString(), anyString(), metadata.capture());
        for (String m : metadata.getAllValues()) {
            assertThat(mapper.readTree(m).has("disclose_ai")).isFalse();
        }
    }
}
