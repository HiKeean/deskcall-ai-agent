package com.deskcall;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import org.junit.jupiter.api.Test;
import org.springframework.core.io.Resource;
import org.springframework.core.io.support.PathMatchingResourcePatternResolver;

/**
 * Penjaga: di SQL Server, nama tanpa prefix schema jatuh ke schema default login (dbo) dan mencemari schema
 * klarfinance. H2 di test TIDAK mendeteksi ini (kejadian 2026-09-21), jadi kita periksa teks migrasinya.
 */
class MigrationSchemaQualificationTest {

    private static final Pattern TARGET = Pattern.compile(
            "(?i)\\b(?:CREATE\\s+(?:UNIQUE\\s+)?(?:(?:NON)?CLUSTERED\\s+)?(?:TABLE|VIEW|SEQUENCE)"
                    + "|ALTER\\s+TABLE|DROP\\s+(?:TABLE|VIEW|SEQUENCE)(?:\\s+IF\\s+EXISTS)?"
                    + "|REFERENCES|CREATE\\s+(?:UNIQUE\\s+)?(?:(?:NON)?CLUSTERED\\s+)?INDEX\\s+\\w+\\s+ON"
                    + "|INSERT\\s+INTO|UPDATE|DELETE\\s+FROM)\\s+([^\\s(]+)");

    @Test
    void everyObjectInMigrationsIsQualifiedWithDeskcallSchema() throws Exception {
        Resource[] migrations = new PathMatchingResourcePatternResolver().getResources("classpath:db/migration/*.sql");
        assertThat(migrations).isNotEmpty();

        List<String> offenders = new ArrayList<>();
        for (Resource migration : migrations) {
            String sql = new String(migration.getInputStream().readAllBytes(), StandardCharsets.UTF_8)
                    .replaceAll("(?m)--.*$", ""); // buang komentar
            Matcher m = TARGET.matcher(sql);
            while (m.find()) {
                String target = m.group(1);
                if (!target.toLowerCase().startsWith("deskcall.")) {
                    offenders.add(migration.getFilename() + ": " + m.group().trim());
                }
            }
        }
        assertThat(offenders).as("objek tanpa prefix `deskcall.` akan jatuh ke dbo di SQL Server").isEmpty();
    }

    @Test
    void guardActuallyCatchesUnqualifiedNames() {
        Matcher m = TARGET.matcher("CREATE TABLE calls (id BIGINT);\nCREATE INDEX ix ON calls (id);");
        List<String> targets = new ArrayList<>();
        while (m.find()) {
            targets.add(m.group(1));
        }
        assertThat(targets).containsExactly("calls", "calls");
    }
}
