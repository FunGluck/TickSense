package dev.ticksense;

import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;

final class SnapshotQueue {
    private final ArrayBlockingQueue<MetricSnapshot> queue;
    private final AtomicLong dropped = new AtomicLong();

    SnapshotQueue(int capacity) { queue = new ArrayBlockingQueue<>(capacity); }

    boolean offer(MetricSnapshot snapshot) {
        if (queue.offer(snapshot)) return true;
        dropped.incrementAndGet();
        return false;
    }

    MetricSnapshot poll() throws InterruptedException { return queue.poll(200, TimeUnit.MILLISECONDS); }
    boolean isEmpty() { return queue.isEmpty(); }
    long dropped() { return dropped.get(); }
}
