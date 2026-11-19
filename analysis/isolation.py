"""Keep model fitting separate from evaluation predictions."""
import pandas as pd
from sklearn.ensemble import IsolationForest

FEATURES = ["mspt_avg", "players_online", "tps_1m"]


def eligible_rows(frame: pd.DataFrame) -> pd.Series:
    return frame[FEATURES].notna().all(axis=1) & frame[FEATURES].abs().lt(float("inf")).all(axis=1)


def train_model(training: pd.DataFrame) -> IsolationForest:
    model = IsolationForest(n_estimators=100, contamination=0.05, random_state=42)
    model.fit(training[FEATURES])
    return model


def predict_anomalies(model: IsolationForest, evaluation: pd.DataFrame) -> pd.DataFrame:
    result = evaluation.copy()
    valid = eligible_rows(result)
    features = result.loc[valid, FEATURES]
    if valid.all() and not features.empty:
        result["ml_prediction"] = model.predict(features)
        result["anomaly_score"] = model.decision_function(features)
        result["ml_anomaly"] = result["ml_prediction"] == -1
    else:
        result["ml_prediction"] = pd.Series(pd.NA, index=result.index, dtype="Int8")
        result["anomaly_score"] = float("nan")
        if not features.empty:
            result.loc[valid, "ml_prediction"] = model.predict(features)
            result.loc[valid, "anomaly_score"] = model.decision_function(features)
        result["ml_anomaly"] = result["ml_prediction"].eq(-1)
    return result
