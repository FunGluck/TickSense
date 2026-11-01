"""Keep model fitting separate from evaluation predictions."""
import pandas as pd
from sklearn.ensemble import IsolationForest

FEATURES = ["mspt_avg", "players_online", "tps_1m"]


def train_model(training: pd.DataFrame) -> IsolationForest:
    model = IsolationForest(n_estimators=100, contamination=0.05, random_state=42)
    model.fit(training[FEATURES])
    return model


def predict_anomalies(model: IsolationForest, evaluation: pd.DataFrame) -> pd.DataFrame:
    result = evaluation.copy()
    result["ml_prediction"] = model.predict(result[FEATURES])
    result["anomaly_score"] = model.decision_function(result[FEATURES])
    result["ml_anomaly"] = result["ml_prediction"] == -1
    return result
