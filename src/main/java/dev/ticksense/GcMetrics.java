package dev.ticksense;

import java.lang.management.GarbageCollectorMXBean;

/** JVM lifetime counters, independently summed over collectors that support each counter. */
record GcMetrics(long collectionCount, long collectionTimeMs) {
    static GcMetrics read(Iterable<? extends GarbageCollectorMXBean> collectors) {
        long count = 0;
        long time = 0;
        boolean hasCount = false;
        boolean hasTime = false;
        for (GarbageCollectorMXBean collector : collectors) {
            long collectorCount = collector.getCollectionCount();
            long collectorTime = collector.getCollectionTime();
            if (collectorCount >= 0) { count += collectorCount; hasCount = true; }
            if (collectorTime >= 0) { time += collectorTime; hasTime = true; }
        }
        return new GcMetrics(hasCount ? count : -1, hasTime ? time : -1);
    }
}
