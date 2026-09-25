package com.deskcall.config;

import io.swagger.v3.oas.models.Components;
import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Info;
import io.swagger.v3.oas.models.security.SecurityRequirement;
import io.swagger.v3.oas.models.security.SecurityScheme;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/** Dokumentasi Swagger UI (aktif hanya bila DESKCALL_SWAGGER_ENABLED=true); tombol Authorize mengisi X-API-Key. */
@Configuration
public class OpenApiConfig {

    private static final String SCHEME = "apiKey";

    @Bean
    public OpenAPI deskcallOpenApi() {
        return new OpenAPI()
                .info(new Info().title("deskcall API").version("v1")
                        .description("Call system AI desk collection. Kontrak lengkap: docs/API.md"))
                .components(new Components().addSecuritySchemes(SCHEME, new SecurityScheme()
                        .type(SecurityScheme.Type.APIKEY).in(SecurityScheme.In.HEADER).name(ApiKeyFilter.HEADER)))
                .addSecurityItem(new SecurityRequirement().addList(SCHEME));
    }
}
