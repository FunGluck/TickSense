# Анализ метрик TickSense

Здесь находится заготовка будущего Python-анализатора. Позже он будет читать метрики через pandas и строить графики через matplotlib. Сейчас программа только принимает путь к CSV и выводит его: файл не открывается, графики и ML не реализованы. Для запуска заготовки существующий CSV не требуется.

Все команды ниже выполняются из корня репозитория, где находятся `build.gradle.kts` и `analysis/`. Требуется установленный Python 3.

## Windows (PowerShell)

Создайте виртуальное окружение и установите зависимости:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r analysis/requirements.txt
```

Запустите заготовку (активация окружения не требуется):

```powershell
.\.venv\Scripts\python.exe analysis/analyze.py datasets/metrics-2026-11-01.csv
```

## Linux/macOS

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r analysis/requirements.txt
.venv/bin/python analysis/analyze.py datasets/metrics-2026-11-01.csv
```

Справка: `python analysis/analyze.py --help`. Путь к CSV — обязательный позиционный аргумент; относительный путь отсчитывается от текущего рабочего каталога. Пути с пробелами заключайте в кавычки.

Локальные выгрузки можно складывать в `datasets/`: его содержимое, CSV, логи и виртуальное окружение исключены из Git. Заготовка не импортирует pandas или matplotlib; зависимости подготовлены для следующих учебных задач.
