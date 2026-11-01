package dev.ticksense;

import java.time.Instant;

public record MetricSnapshot(Instant timestamp, long elapsedMs, double tps1m,
                             double msptAvg, int playersOnline, long heapUsedBytes,
                             long loadedChunks, long entitiesTotal, long blockEntitiesTotal,
                             long heapCommittedBytes, long gcCollectionCount, long gcCollectionTimeMs) {
    public static final String HEADER = "timestamp_utc,elapsed_ms,tps_1m,mspt_avg,players_online,jvm_heap_used_bytes,loaded_chunks,entities_total,block_entities_total,jvm_heap_committed_bytes,gc_collection_count,gc_collection_time_ms";

    public String toCsv() {
        return timestamp + "," + elapsedMs + "," + Double.toString(tps1m) + ","
                + Double.toString(msptAvg) + "," + playersOnline + "," + heapUsedBytes
                + "," + loadedChunks + "," + entitiesTotal + "," + blockEntitiesTotal
                + "," + heapCommittedBytes + "," + gcCollectionCount + "," + gcCollectionTimeMs;
    }
}
