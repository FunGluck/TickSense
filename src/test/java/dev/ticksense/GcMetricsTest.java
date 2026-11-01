package dev.ticksense;

import java.lang.management.GarbageCollectorMXBean;
import java.util.List;
import javax.management.ObjectName;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class GcMetricsTest {
    private record Collector(long count, long time) implements GarbageCollectorMXBean {
        public long getCollectionCount() { return count; }
        public long getCollectionTime() { return time; }
        public String getName() { return "test"; }
        public boolean isValid() { return true; }
        public String[] getMemoryPoolNames() { return new String[0]; }
        public ObjectName getObjectName() { return null; }
    }

    @Test void sumsSupportedCountersIndependently() {
        assertEquals(new GcMetrics(7, 30), GcMetrics.read(List.of(
                new Collector(2, 10), new Collector(-1, 20), new Collector(5, -1))));
    }

    @Test void unavailableIsNotZero() {
        assertEquals(new GcMetrics(-1, -1), GcMetrics.read(List.of(new Collector(-1, -1))));
        assertEquals(new GcMetrics(-1, -1), GcMetrics.read(List.of()));
        assertEquals(new GcMetrics(0, 0), GcMetrics.read(List.of(new Collector(0, 0))));
        assertEquals(new GcMetrics(-1, 0), GcMetrics.read(List.of(new Collector(-1, 0))));
    }

    @Test void unavailableCountersSerializeAsSentinels() {
        var gc = GcMetrics.read(List.of(new Collector(-1, -1)));
        var sample = new MetricSnapshot(java.time.Instant.EPOCH, 0, 20, 1, 0, 100,
                0, 0, 0, 200, gc.collectionCount(), gc.collectionTimeMs());
        assertTrue(sample.toCsv().endsWith(",200,-1,-1"));
    }
}
