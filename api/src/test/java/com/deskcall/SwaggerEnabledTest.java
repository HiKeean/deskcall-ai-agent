package com.deskcall;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.deskcall.livekit.LiveKitClient;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

/** Swagger dinyalakan (DESKCALL_SWAGGER_ENABLED=true di app): spec menampilkan endpoint panggilan dan skema X-API-Key. */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@TestPropertySource(properties = {"springdoc.api-docs.enabled=true", "springdoc.swagger-ui.enabled=true"})
class SwaggerEnabledTest {

    @Autowired MockMvc mvc;
    @MockitoBean LiveKitClient liveKit;

    @Test
    void docsListCallEndpointsAndApiKeyScheme() throws Exception {
        mvc.perform(get("/v3/api-docs")).andExpect(status().isOk())
                .andExpect(jsonPath("$.paths['/api/v1/calls']").exists())
                .andExpect(jsonPath("$.components.securitySchemes.apiKey.name").value("X-API-Key"));
    }
}
