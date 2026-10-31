package dev.ticksense;

import java.io.BufferedWriter;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.time.LocalDate;
import java.time.ZoneOffset;

final class DailyCsvWriter implements AutoCloseable {
    private final Path directory;
    private BufferedWriter writer;
    private LocalDate day;

    DailyCsvWriter(Path directory) { this.directory = directory; }

    void write(MetricSnapshot snapshot) throws IOException {
        LocalDate nextDay = snapshot.timestamp().atOffset(ZoneOffset.UTC).toLocalDate();
        if (!nextDay.equals(day)) {
            close();
            Files.createDirectories(directory);
            Path file = directory.resolve("metrics-" + nextDay + ".csv");
            boolean empty = !Files.exists(file) || Files.size(file) == 0;
            writer = Files.newBufferedWriter(file, StandardCharsets.UTF_8,
                    StandardOpenOption.CREATE, StandardOpenOption.APPEND);
            day = nextDay;
            if (empty) { writer.write(MetricSnapshot.HEADER); writer.write('\n'); }
        }
        writer.write(snapshot.toCsv());
        writer.write('\n');
        writer.flush();
    }

    @Override public void close() throws IOException {
        if (writer != null) {
            try { writer.close(); } finally { writer = null; day = null; }
        }
    }
}
