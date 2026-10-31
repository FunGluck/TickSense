package dev.ticksense;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.Locale;
import static org.junit.jupiter.api.Assertions.*;

class CollectorTest {
    @TempDir Path directory;
    private MetricSnapshot snapshot(String time) {
        return new MetricSnapshot(Instant.parse(time), 1234, 19.95, 12.5, 3, 1048576);
    }

    @Test void csvIsLocaleIndependent() {
        Locale previous = Locale.getDefault();
        try {
            Locale.setDefault(Locale.GERMANY);
            assertEquals("2026-10-31T23:59:59Z,1234,19.95,12.5,3,1048576",
                    snapshot("2026-10-31T23:59:59Z").toCsv());
            assertEquals("timestamp_utc,elapsed_ms,tps_1m,mspt_avg,players_online,jvm_heap_used_bytes", MetricSnapshot.HEADER);
        } finally { Locale.setDefault(previous); }
    }

    @Test void reopenAppendsWithoutDuplicateHeader() throws Exception {
        var sample = snapshot("2026-10-31T12:00:00Z");
        for (int i = 0; i < 2; i++) {
            try (var csv = new DailyCsvWriter(directory.resolve("nested"))) { csv.write(sample); }
        }
        assertEquals(java.util.List.of(MetricSnapshot.HEADER, sample.toCsv(), sample.toCsv()),
                Files.readAllLines(directory.resolve("nested/metrics-2026-10-31.csv")));
    }

    @Test void emptyExistingFileGetsHeader() throws Exception {
        Files.createFile(directory.resolve("metrics-2026-10-31.csv"));
        try (var csv = new DailyCsvWriter(directory)) { csv.write(snapshot("2026-10-31T12:00:00Z")); }
        assertEquals(2, Files.readAllLines(directory.resolve("metrics-2026-10-31.csv")).size());
    }

    @Test void rotatesBySnapshotUtcDay() throws Exception {
        var before = snapshot("2026-10-31T23:59:59.999Z");
        var after = snapshot("2026-11-01T00:00:00Z");
        try (var csv = new DailyCsvWriter(directory)) { csv.write(before); csv.write(after); }
        assertEquals(java.util.List.of(MetricSnapshot.HEADER, before.toCsv()), Files.readAllLines(directory.resolve("metrics-2026-10-31.csv")));
        assertEquals(java.util.List.of(MetricSnapshot.HEADER, after.toCsv()), Files.readAllLines(directory.resolve("metrics-2026-11-01.csv")));
    }

    @Test void fullQueueDropsNewestAndContinuesAfterDrain() throws Exception {
        var queue = new SnapshotQueue(1);
        var first = snapshot("2026-10-31T12:00:00Z");
        var second = snapshot("2026-10-31T12:00:01Z");
        assertTrue(queue.offer(first));
        assertFalse(queue.offer(second));
        assertEquals(1, queue.dropped());
        assertSame(first, queue.poll());
        assertTrue(queue.offer(second));
        assertSame(second, queue.poll());
        assertTrue(queue.isEmpty());
    }
}
