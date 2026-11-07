# Проверка совместимости TickSense с Minecraft 26.x

Аудит официальных каталогов от 8 ноября 2026 года. Paper публикует сборки через [Fill](https://fill.papermc.io/v3/projects/paper) и [страницу загрузок](https://papermc.io/downloads/paper). Сборки Purpur проверены по [официальному API](https://api.purpurmc.org/v2/purpur). Для Paper 26.1 и новее требуется [Java 25](https://docs.papermc.io/paper/getting-started/).

| Minecraft | Ядро и сборка | Java сервера | JAR | Проверка |
|---|---|---:|---|---|
| 1.21.1 / 1.21.4 / 1.21.8 / 1.21.11 | Paper 133 / 232 / 60 / 132 | 21 | TickSense-0.8.1-pilot.jar | Прежние серверные испытания и побайтовое совпадение повторной сборки |
| 26.1.2 | Paper 74 Stable | 25 | Тот же JAR | Компиляция против API подтверждена, запуск ожидает EULA |
| 26.2 | Paper 135 Stable | 25 | Тот же JAR | Компиляция против API подтверждена, запуск ожидает EULA |
| 26.3 | Paper 244 Stable | 25 | Тот же JAR | Компиляция против API подтверждена, запуск ожидает EULA |
| 26.1.2 / 26.2 / 26.3 | Purpur 2592 / 2633 / 2657 | 25 | Кандидат — тот же JAR | Сборки доступны, API и запуск отдельно не проверены |
| 26.1.1 | Paper 29 Alpha | 25 | Вне основного набора | Доступна экспериментальная сборка, проверка не проводилась |
| 26.1.1 | Purpur | 25 | — | Официальный каталог вернул 404 |

## Сборка и API

Gradle использует toolchain Java 21 и `compileOnly` Paper API 1.21.1. `plugin.yml` сохраняет нижнюю границу `api-version: '1.21.1'`. На сервере 26.x Java 25 может исполнять байткод Java 21 (major 65). Отдельный Java 25 JAR по результатам компиляции не требуется. Подтверждение установки на 26.x зависит от серверной проверки.

Для каждого из трёх Paper JAR сверили SHA-256 из Fill и извлекли встроенные API и библиотеки. Все исходники TickSense успешно прошли `javac --release 21` на JDK 25 с classpath этих библиотек. Это проверяет сигнатуры TPS и MSPT (`getTPS()[0]`, `getAverageTickTime()`), онлайна, счётчиков чанков, сущностей и block entities, синхронного scheduler, жизненного цикла JavaPlugin и конфигурации Bukkit. Семантика этих методов на работающем сервере проверяется отдельно. JVM heap и GC по-прежнему читаются через стандартные MXBeans. Ротация, запись CSV v2 и `elapsed_ms` остаются реализацией TickSense без изменений.

Запускайте существующий Gradle Wrapper под JDK 21 через `JAVA_HOME`. Java 25 нужна процессу сервера. Сборка `gradlew.bat test build --rerun-tasks --offline` на Temurin 21.0.10 выполнила 13 Java-тестов. `build/libs/TickSense-0.8.1-pilot.jar` совпал с опубликованным артефактом по SHA-256 `ed112f0f1a3f360b61a00525c81eba0ffd9c50d7c2b9e979e70e3e7ebb2639ed`. Это подтверждает сохранение ранее испытанного бинарного файла. Повторных запусков 1.21.x в этой проверке не было.

## Серверная проверка 26.x

Из корня репозитория, с Java 25 на `PATH` и зависимостями `analysis/requirements.txt` в `.venv`:

```powershell
.\.venv\Scripts\python.exe scripts/paper_compatibility.py Prepare --series 26 --jar build/libs/TickSense-0.8.1-pilot.jar
```

Обе матрицы используют внешний каталог `TickSense-Compatibility` рядом с проектом. Для вложенного checkout `Development/TickSense/TickSense` это `Development/TickSense-Compatibility`. Paper 26.x занимает подпапки `paper-26.3`, `paper-26.2` и `paper-26.1.2`. Путь можно переопределить аргументом `--workdir`; каталог должен находиться вне репозитория. После отдельного принятия Minecraft EULA владельцем для каждого окружения добавьте в него `eula.txt` с `eula=true`. Harness проверяет файлы, но никогда не принимает EULA сам.

```powershell
.\.venv\Scripts\python.exe scripts/paper_compatibility.py Run --series 26 --jar build/libs/TickSense-0.8.1-pilot.jar
```

Последовательные тесты запускают пустой сервер дважды на локальном адресе, завершают командой `stop`, проверяют CSV v2 и сброс `elapsed_ms`, затем запускают существующий анализатор для HTML. Логи остаются в папках серверов, сводка 26.x — в `TickSense-Compatibility/results/26/`. Сводка 1.21.x остаётся в `results/`. Матрица 1.21.x остаётся режимом по умолчанию. Подключение игроков, управляемая нагрузка, UTC-ротация и накладные расходы этим smoke-тестом не покрываются.
