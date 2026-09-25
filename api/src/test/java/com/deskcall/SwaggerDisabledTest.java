package com.deskcall;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.deskcall.livekit.LiveKitClient;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

/** Default (produksi): Swagger mati, spec dan UI tidak terekspos. */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class SwaggerDisabledTest {

    @Autowired MockMvc mvc;
    @MockitoBean LiveKitClient liveKit;

    @Test
    void docsAreNotExposedByDefault() throws Exception {
        mvc.perform(get("/v3/api-docs")).andExpect(status().isNotFound());
        mvc.perform(get("/swagger-ui/index.html")).andExpect(status().isNotFound());
    }
}
