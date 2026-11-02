package dev.ticksense;

import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.scheduler.BukkitTask;
import org.bukkit.plugin.java.JavaPlugin;

import java.io.InputStream;
import java.lang.management.ManagementFactory;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.logging.Level;
import java.util.logging.Logger;

public final class TickSensePlugin extends JavaPlugin {
    private record Session(SnapshotQueue queue, long interval, long startNanos) {}
    private volatile Session session;
    private volatile boolean stopping;
    private Thread worker;
    private BukkitTask task;
    private long ticks;

    @Override public void onEnable() {
        stopping = false;
        ticks = 0;
        Path folder = getDataFolder().toPath().toAbsolutePath().normalize();
        Logger logger = getLogger();
        worker = new Thread(() -> collectToDisk(folder, logger), "TickSense-CSV");
        worker.setDaemon(true);
        worker.start();
        var memory = ManagementFactory.getMemoryMXBean();
        var collectors = ManagementFactory.getGarbageCollectorMXBeans();
        task = getServer().getScheduler().runTaskTimer(this, () -> {
            Session current = session;
            if (current == null || stopping) return;
            if (++ticks < current.interval()) return;
            ticks = 0;
            long loadedChunks = 0;
            long entitiesTotal = 0;
            long blockEntitiesTotal = 0;
            // Only world-level counts: no entity/chunk enumeration or chunk loading.
            for (var world : getServer().getWorlds()) {
                loadedChunks += world.getChunkCount();
                entitiesTotal += world.getEntityCount();
                blockEntitiesTotal += world.getTileEntityCount();
            }
            var heap = memory.getHeapMemoryUsage();
            var gc = GcMetrics.read(collectors);
            current.queue().offer(new MetricSnapshot(Instant.now(),
                    (System.nanoTime() - current.startNanos()) / 1_000_000,
                    getServer().getTPS()[0], getServer().getAverageTickTime(),
                    getServer().getOnlinePlayers().size(), heap.getUsed(),
                    loadedChunks, entitiesTotal, blockEntitiesTotal, heap.getCommitted(),
                    gc.collectionCount(), gc.collectionTimeMs()));
        }, 1L, 1L);
    }

    private void collectToDisk(Path folder, Logger logger) {
        try {
            Files.createDirectories(folder);
            Path configPath = folder.resolve("config.yml");
            if (!Files.exists(configPath)) {
                try (InputStream defaults = TickSensePlugin.class.getResourceAsStream("/config.yml")) {
                    if (defaults == null) throw new IllegalStateException("Missing default config.yml");
                    Files.copy(defaults, configPath);
                }
            }
            var config = new YamlConfiguration();
            config.load(configPath.toFile());
            if (!config.getBoolean("collection.enabled", true)) return;
            long interval = config.getLong("collection.interval-ticks", 200);
            int capacity = config.getInt("storage.queue-capacity", 1024);
            if (interval <= 0 || capacity <= 0) throw new IllegalArgumentException("Interval and capacity must be positive");
            Path directory = folder.resolve(config.getString("storage.directory", "data")).normalize();
            if (!directory.startsWith(folder) || directory.equals(folder))
                throw new IllegalArgumentException("storage.directory must be inside the plugin folder");
            SnapshotQueue queue = new SnapshotQueue(capacity);
            session = new Session(queue, interval, System.nanoTime());
            long lastReport = System.nanoTime();
            long reportedDrops = 0;
            try (DailyCsvWriter csv = new DailyCsvWriter(directory)) {
                while (!stopping || !queue.isEmpty()) {
                    MetricSnapshot snapshot = queue.poll();
                    if (snapshot != null) csv.write(snapshot);
                    if (System.nanoTime() - lastReport >= 30_000_000_000L) {
                        long total = queue.dropped();
                        if (total != reportedDrops) logger.warning("Dropped snapshots (queue full): " + total);
                        reportedDrops = total;
                        lastReport = System.nanoTime();
                    }
                }
            } finally {
                if (queue.dropped() > 0) logger.warning("Session dropped snapshots: " + queue.dropped());
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            logger.warning("CSV worker interrupted; pending snapshots may be lost");
        } catch (Exception e) {
            logger.log(Level.SEVERE, "Metrics collection stopped", e);
        } finally { session = null; }
    }

    @Override public void onDisable() {
        if (task != null) task.cancel();
        stopping = true;
        if (worker == null) return;
        try {
            worker.join(3000);
            if (worker.isAlive()) {
                getLogger().warning("CSV shutdown exceeded 3 seconds; pending snapshots may be lost");
                worker.interrupt();
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            worker.interrupt();
        }
    }
}
