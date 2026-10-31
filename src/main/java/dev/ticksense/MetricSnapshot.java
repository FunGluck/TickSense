package dev.ticksense;

import java.time.Instant;

public record MetricSnapshot(Instant timestamp, long elapsedMs, double tps1m,
                             double msptAvg, int playersOnline, long heapUsedBytes) {
    public static final String HEADER = "timestamp_utc,elapsed_ms,tps_1m,mspt_avg,players_online,jvm_heap_used_bytes";

    public String toCsv() {
        return timestamp + "," + elapsedMs + "," + Double.toString(tps1m) + ","
                + Double.toString(msptAvg) + "," + playersOnline + "," + heapUsedBytes;
    }
}
