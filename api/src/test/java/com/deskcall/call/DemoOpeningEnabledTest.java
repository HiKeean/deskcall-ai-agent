package com.deskcall.call;

import static com.deskcall.call.DemoOpeningTest.body;
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

import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

/** Environment demo (DESKCALL_ALLOW_DEMO_OPENING=true): discloseAi=false diteruskan ke agent. */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@TestPropertySource(properties = "deskcall.call.allow-undisclosed-opening=true")
class DemoOpeningEnabledTest {

    @Autowired MockMvc mvc;
    @Autowired ObjectMapper mapper;
    @MockitoBean LiveKitClient liveKit;

    @Test
    void undisclosedOpeningIsPassedToTheAgent() throws Exception {
        when(liveKit.url()).thenReturn("wss://livekit.test");
        when(liveKit.createAgentDispatch(anyString(), anyString(), anyString())).thenReturn("AD_1");
        when(liveKit.issueCustomerToken(anyString(), anyString(), anyString()))
                .thenReturn(new LiveKitClient.CustomerToken("jwt", Instant.parse("2026-09-21T02:05:00Z")));

        mvc.perform(post("/api/v1/calls").header("X-API-Key", "test-key").contentType(MediaType.APPLICATION_JSON)
                .content(body(",\"discloseAi\":false"))).andExpect(status().isCreated());

        ArgumentCaptor<String> metadata = ArgumentCaptor.forClass(String.class);
        verify(liveKit).createAgentDispatch(anyString(), anyString(), metadata.capture());
        JsonNode meta = mapper.readTree(metadata.getValue());
        assertThat(meta.path("disclose_ai").asBoolean(true)).isFalse();
    }
}
