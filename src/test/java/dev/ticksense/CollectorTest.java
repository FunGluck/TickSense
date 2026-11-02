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
        return new MetricSnapshot(Instant.parse(time), 1234, 19.95, 12.5, 3, 1048576, 100, 200, 50, 2097152, 12, 345);
    }

    @Test void csvIsLocaleIndependent() {
        Locale previous = Locale.getDefault();
        try {
            Locale.setDefault(Locale.GERMANY);
            assertEquals("2026-10-31T23:59:59Z,1234,19.95,12.5,3,1048576,100,200,50,2097152,12,345",
                    snapshot("2026-10-31T23:59:59Z").toCsv());
            assertEquals("timestamp_utc,elapsed_ms,tps_1m,mspt_avg,players_online,jvm_heap_used_bytes,loaded_chunks,entities_total,block_entities_total,jvm_heap_committed_bytes,gc_collection_count,gc_collection_time_ms", MetricSnapshot.HEADER);
        } finally { Locale.setDefault(previous); }
    }

    @Test void reopenAppendsWithoutDuplicateHeader() throws Exception {
        var sample = snapshot("2026-10-31T12:00:00Z");
        for (int i = 0; i < 2; i++) {
            try (var csv = new DailyCsvWriter(directory.resolve("nested"))) { csv.write(sample); }
        }
        assertEquals(java.util.List.of(MetricSnapshot.HEADER, sample.toCsv(), sample.toCsv()),
                Files.readAllLines(directory.resolve("nested/metrics-v2-2026-10-31.csv")));
    }

    @Test void emptyExistingFileGetsHeader() throws Exception {
        Files.createFile(directory.resolve("metrics-v2-2026-10-31.csv"));
        try (var csv = new DailyCsvWriter(directory)) { csv.write(snapshot("2026-10-31T12:00:00Z")); }
        assertEquals(2, Files.readAllLines(directory.resolve("metrics-v2-2026-10-31.csv")).size());
    }

    @Test void rotatesBySnapshotUtcDay() throws Exception {
        var before = snapshot("2026-10-31T23:59:59.999Z");
        var after = snapshot("2026-11-01T00:00:00Z");
        try (var csv = new DailyCsvWriter(directory)) { csv.write(before); csv.write(after); }
        assertEquals(java.util.List.of(MetricSnapshot.HEADER, before.toCsv()), Files.readAllLines(directory.resolve("metrics-v2-2026-10-31.csv")));
        assertEquals(java.util.List.of(MetricSnapshot.HEADER, after.toCsv()), Files.readAllLines(directory.resolve("metrics-v2-2026-11-01.csv")));
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

    @Test void snapshotContainsTwelveColumnsInHeaderOrder() {
        var sample = snapshot("2026-10-31T12:00:00Z");
        assertEquals(100, sample.loadedChunks());
        assertEquals(200, sample.entitiesTotal());
        assertEquals(50, sample.blockEntitiesTotal());
        assertEquals(2097152, sample.heapCommittedBytes());
        assertEquals(12, sample.gcCollectionCount());
        assertEquals(345, sample.gcCollectionTimeMs());
        assertEquals(12, MetricSnapshot.HEADER.split(",", -1).length);
        assertEquals(12, sample.toCsv().split(",", -1).length);
    }

    @Test void legacyFileIsNeverModified() throws Exception {
        Path legacy = directory.resolve("metrics-2026-10-31.csv");
        String original = "timestamp_utc,elapsed_ms,tps_1m,mspt_avg,players_online,jvm_heap_used_bytes\nold-data\n";
        Files.writeString(legacy, original);
        try (var csv = new DailyCsvWriter(directory)) { csv.write(snapshot("2026-10-31T12:00:00Z")); }
        assertEquals(original, Files.readString(legacy));
        assertEquals(2, Files.readAllLines(directory.resolve("metrics-v2-2026-10-31.csv")).size());
    }

    @Test void incompatibleV2HeaderIsRejectedWithoutAppending() throws Exception {
        Path file = directory.resolve("metrics-v2-2026-10-31.csv");
        Files.writeString(file, "wrong,header\n");
        try (var csv = new DailyCsvWriter(directory)) {
            assertThrows(java.io.IOException.class, () -> csv.write(snapshot("2026-10-31T12:00:00Z")));
        }
        assertEquals("wrong,header\n", Files.readString(file));
    }

    @Test void incompleteTailIsRejectedWithoutChangingFile() throws Exception {
        Path file = directory.resolve("metrics-v2-2026-10-31.csv");
        String original = MetricSnapshot.HEADER + "\n2026-10-31T12:00:00Z,123";
        Files.writeString(file, original);
        try (var csv = new DailyCsvWriter(directory)) {
            assertThrows(java.io.IOException.class, () -> csv.write(snapshot("2026-10-31T12:00:00Z")));
        }
        assertEquals(original, Files.readString(file));
    }

    @Test void filesystemFailureIsPropagated() throws Exception {
        Path notDirectory = directory.resolve("blocked");
        Files.writeString(notDirectory, "keep");
        try (var csv = new DailyCsvWriter(notDirectory)) {
            assertThrows(java.io.IOException.class, () -> csv.write(snapshot("2026-10-31T12:00:00Z")));
        }
        assertEquals("keep", Files.readString(notDirectory));
    }
}

