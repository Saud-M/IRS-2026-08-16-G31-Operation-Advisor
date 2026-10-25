"""Supervised Scenario Classification Suite.

Trains and evaluates:
1. k-Nearest Neighbors (KNN, k=5) - Distance-weighted baseline.
2. Decision Tree Classifier - Depth-bounded for interpretable rule extraction.
3. Random Forest Classifier - 100-tree ensemble for robust multi-class diagnosis.
4. Multi-Layer Perceptron (MLP) - Neural network comparator.

Provides evaluation metrics: Macro F1-score, Precision, Recall, and Confusion Matrix.
"""

from dataclasses import dataclass
import os
import pickle
from typing import Dict, Any, List, Tuple, Optional
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import KNeighborsClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.metrics import classification_report, f1_score, precision_score, recall_score, confusion_matrix


FEATURE_COLUMNS = [
    "PT-101",
    "LT-101",
    "LT-102",
    "TT-101",
    "FT-101",
    "DP-101",
    "ST-101",
    "PCV-101_pos",
    "LCV-101_pos",
    "LCV-102_pos",
    "V102_scrubber_level",
    "compressor_power_kw",
    "surge_margin_pct",
]


@dataclass
class ModelEvaluation:
    model_name: str
    macro_f1: float
    precision: float
    recall: float
    confusion_matrix: List[List[int]]
    report: Dict[str, Any]


class ScenarioClassifierSuite:
    """Supervised learning suite for oil and gas scenario classification."""

    def __init__(self, random_state: int = 42):
        self.random_state = random_state
        self.scaler = StandardScaler()
        self.classes_: List[str] = []

        self.models: Dict[str, Any] = {
            "knn": KNeighborsClassifier(n_neighbors=5, weights="distance"),
            "decision_tree": DecisionTreeClassifier(max_depth=7, random_state=random_state),
            "random_forest": RandomForestClassifier(n_estimators=100, max_depth=10, random_state=random_state),
            "mlp": MLPClassifier(hidden_layer_sizes=(64, 32), max_iter=150, early_stopping=True, random_state=random_state),
        }
        self.evaluations: Dict[str, ModelEvaluation] = {}
        self.is_fitted = False

    def prepare_data(self, df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Split telemetry dataframe into train (70%), validation (15%), and test (15%) sets."""
        X = df[FEATURE_COLUMNS].copy().fillna(0.0).values
        if "fault_active" in df.columns:
            y = np.where(df["fault_active"] == 1, df["scenario_label"].values, "NOMINAL")
        else:
            y = df["scenario_label"].values

        self.classes_ = sorted(list(np.unique(y)))

        # Split: 70% train, 30% temp
        X_train, X_temp, y_train, y_temp = train_test_split(
            X, y, test_size=0.30, random_state=self.random_state, stratify=y
        )
        # Split temp: 50% val (15% total), 50% test (15% total)
        X_val, X_test, y_val, y_test = train_test_split(
            X_temp, y_temp, test_size=0.50, random_state=self.random_state, stratify=y_temp
        )

        # Fit scaler on training set
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_val_scaled = self.scaler.transform(X_val)
        X_test_scaled = self.scaler.transform(X_test)

        return X_train_scaled, y_train, X_val_scaled, y_val, X_test_scaled, y_test

    def train(self, df: pd.DataFrame) -> Dict[str, ModelEvaluation]:
        """Train all classifier models and score against the unseen test set."""
        X_train, y_train, X_val, y_val, X_test, y_test = self.prepare_data(df)

        self.evaluations.clear()

        for name, model in self.models.items():
            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)

            macro_f1 = f1_score(y_test, y_pred, average="macro")
            precision = precision_score(y_test, y_pred, average="macro", zero_division=0)
            recall = recall_score(y_test, y_pred, average="macro", zero_division=0)
            cm = confusion_matrix(y_test, y_pred, labels=self.classes_).tolist()
            report = classification_report(y_test, y_pred, output_dict=True, zero_division=0)

            self.evaluations[name] = ModelEvaluation(
                model_name=name,
                macro_f1=round(float(macro_f1), 4),
                precision=round(float(precision), 4),
                recall=round(float(recall), 4),
                confusion_matrix=cm,
                report=report,
            )

        self.is_fitted = True
        return self.evaluations

    def predict(self, feature_dict: Dict[str, Any], model_name: str = "random_forest") -> Dict[str, Any]:
        """Predict scenario class and probabilities for a single live telemetry reading."""
        if not self.is_fitted:
            raise RuntimeError("Classifier suite must be trained before predicting.")

        model = self.models.get(model_name)
        if model is None:
            raise ValueError(f"Unknown model: {model_name}. Available: {list(self.models.keys())}")

        # Construct vector
        vec = np.array([[feature_dict.get(col, 0.0) for col in FEATURE_COLUMNS]])
        vec_scaled = self.scaler.transform(vec)

        pred_class = model.predict(vec_scaled)[0]
        probs = model.predict_proba(vec_scaled)[0]

        prob_dict = {cls_name: round(float(p), 4) for cls_name, p in zip(model.classes_, probs)}

        return {
            "predicted_scenario": pred_class,
            "confidence": round(float(np.max(probs)), 4),
            "probabilities": prob_dict,
            "model_used": model_name,
        }

    def get_feature_importances(self) -> Dict[str, float]:
        """Extract Gini feature importance from the fitted Random Forest."""
        if not self.is_fitted:
            return {}
        rf = self.models["random_forest"]
        importances = rf.feature_importances_
        return {
            col: round(float(imp), 4)
            for col, imp in sorted(zip(FEATURE_COLUMNS, importances), key=lambda x: x[1], reverse=True)
        }

    def save(self, filepath: str) -> None:
        """Serialize models and scaler to disk."""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "wb") as f:
            pickle.dump({
                "models": self.models,
                "scaler": self.scaler,
                "classes": self.classes_,
                "evaluations": self.evaluations,
            }, f)

    def load(self, filepath: str) -> None:
        """Deserialize trained models from disk."""
        with open(filepath, "rb") as f:
            data = pickle.load(f)
        self.models = data["models"]
        self.scaler = data["scaler"]
        self.classes_ = data["classes"]
        self.evaluations = data.get("evaluations", {})
        self.is_fitted = True
