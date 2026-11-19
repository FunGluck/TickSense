"""Local, trusted Isolation Forest artifacts and their compatibility metadata."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PureWindowsPath
import platform
import re

import joblib
import numpy as np
import pandas as pd
import scipy
import sklearn
from sklearn.ensemble import IsolationForest
from sklearn.utils.validation import check_is_fitted
from sklearn.exceptions import NotFittedError

if __package__:
    from .isolation import FEATURES
else:
    from isolation import FEATURES


FEATURE_SCHEMA = 1


def environment():
    return dict(python=platform.python_version(), scikit_learn=sklearn.__version__,
                numpy=np.__version__, pandas=pd.__version__, scipy=scipy.__version__,
                joblib=joblib.__version__)


def sha256(stream):
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


def artifact_paths(path):
    path = Path(path)
    if re.match(r"^[a-z][a-z0-9+.-]+:", str(path), re.I) or PureWindowsPath(path).drive.startswith("\\\\"):
        raise ValueError("Укажите локальный доверенный файл модели")
    path = path.resolve()
    if PureWindowsPath(path).drive.startswith("\\\\") or path.suffix != ".joblib":
        raise ValueError("Укажите локальный доверенный файл с расширением .joblib")
    sidecar = path.with_suffix(".metadata.json")
    if PureWindowsPath(sidecar.resolve()).drive.startswith("\\\\"):
        raise ValueError("Метаданные модели должны храниться локально")
    return path, sidecar


def require_new_artifact(path):
    paths = artifact_paths(path)
    if any(item.exists() for item in paths):
        raise ValueError("Версия уже существует. Укажите новое имя файла модели")
    return paths


def save_model(path, model, *, server_id, training, validation, quality, dataset):
    path, sidecar = require_new_artifact(path)
    details = dict(format_version=1, version=path.stem,
                   trained_at_utc=datetime.now(timezone.utc).isoformat(),
                   server_id=server_id, model_type="IsolationForest", parameters=model.get_params(),
                   features=FEATURES, feature_schema_version=FEATURE_SCHEMA, csv_version=2,
                   preprocessing="identity", environment=environment(), training=training,
                   validation=validation, data_quality=quality, dataset=dataset)
    created = []
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            created.append(path)
            joblib.dump(model, stream, compress=3)
        with path.open("rb") as stream:
            details["sha256"] = sha256(stream)
        with sidecar.open("x", encoding="utf-8") as stream:
            created.append(sidecar)
            json.dump(details, stream, ensure_ascii=False, allow_nan=False, indent=2)
            stream.write("\n")
    except Exception:
        for item in reversed(created):
            item.unlink()
        raise
    return details


def load_model(path):
    """Accept only artifacts from a trusted source; the digest is not authentication."""
    path, sidecar = artifact_paths(path)
    details = json.loads(sidecar.read_text(encoding="utf-8"))
    if not isinstance(details, dict) or details.get("format_version") != 1:
        raise ValueError("Неподдерживаемый формат метаданных модели")
    if (details.get("feature_schema_version") != FEATURE_SCHEMA or details.get("csv_version") != 2
            or details.get("preprocessing") != "identity"):
        raise ValueError("Несовместимая версия схемы признаков модели")
    if details.get("features") != FEATURES:
        raise ValueError("Несовместимый состав или порядок признаков модели")
    versions = details.get("environment")
    if not isinstance(versions, dict):
        raise ValueError("В метаданных отсутствуют версии окружения")
    mismatches = [f"{key}: модель {(versions or {}).get(key)}, среда {value}"
                  for key, value in environment().items()
                  if versions.get(key) != value]
    if mismatches:
        raise ValueError("Несовместимое окружение модели. " + "; ".join(mismatches))
    try:
        training_end = pd.Timestamp(details["training"]["end_utc"])
        validation_end = pd.Timestamp(details["validation"]["end_utc"])
        if (not all(isinstance(details[key], str) and details[key] for key in
                    ("version", "server_id", "trained_at_utc"))
                or details["model_type"] != "IsolationForest"
                or not isinstance(details["parameters"], dict)
                or not isinstance(details["training"]["measurements"], int)
                or pd.isna(training_end) or pd.isna(validation_end)
                or training_end.utcoffset() != timezone.utc.utcoffset(None)
                or validation_end.utcoffset() != timezone.utc.utcoffset(None)
                or training_end >= validation_end):
            raise ValueError
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("Неполные или некорректные метаданные модели") from error
    with path.open("rb") as stream:
        if sha256(stream) != details.get("sha256"):
            raise ValueError("Контрольная сумма модели не совпадает с метаданными")
        stream.seek(0)
        try:
            model = joblib.load(stream)
        except Exception as error:
            raise ValueError("Не удалось прочитать артефакт модели") from error
    if (not isinstance(model, IsolationForest) or list(getattr(model, "feature_names_in_", ())) != FEATURES
            or model.get_params() != details["parameters"]):
        raise ValueError("Артефакт модели не соответствует метаданным")
    try:
        check_is_fitted(model)
    except NotFittedError as error:
        raise ValueError("Артефакт не содержит обученную модель") from error
    return model, details
