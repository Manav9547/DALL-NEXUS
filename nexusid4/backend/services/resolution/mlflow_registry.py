"""NexusID — MLflow Model Registry.

Tracks model versions, metrics, and artifacts in MLflow.
Falls back to local joblib files when MLflow is not available.
Supports hot-reload: changing the active model version at runtime
without restart via Redis pub/sub or in-memory signal.
"""

from __future__ import annotations

import json
import os
import time
import threading
from datetime import datetime
from typing import Any, Optional

import joblib

# ─── Configuration ───────────────────────────────────────────────────────────

MLFLOW_URI = os.getenv("MLFLOW_TRACKING_URI", "")
MLFLOW_ENABLED = bool(MLFLOW_URI)
EXPERIMENT_NAME = "nexusid-resolution"

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
LOCAL_MODEL_DIR = os.path.join(_PROJECT_ROOT, "saved_models")


# ─── MLflow Client ───────────────────────────────────────────────────────────

def _get_mlflow():
    """Get MLflow client, or None."""
    if not MLFLOW_ENABLED:
        return None
    try:
        import mlflow
        mlflow.set_tracking_uri(MLFLOW_URI)
        mlflow.set_experiment(EXPERIMENT_NAME)
        return mlflow
    except ImportError:
        return None


# ─── Model Registry ─────────────────────────────────────────────────────────

class ModelRegistry:
    """Unified model registry that uses MLflow or local storage.

    Tracks:
    - Model versions with metrics (PR-AUC, ROC-AUC, FMR, thresholds)
    - Training artifacts (model files, calibration reports)
    - Active model version for serving
    - Hot-reload signals for zero-downtime model updates
    """

    def __init__(self):
        self._mlflow = _get_mlflow()
        self._active_version: str = "weighted-linear-v1"
        self._active_model: Optional[Any] = None
        self._versions: dict[str, dict] = {}
        self._lock = threading.Lock()

        # Load existing local model if available
        self._load_local_state()

    def _load_local_state(self):
        """Load state from local storage."""
        metrics_path = os.path.join(LOCAL_MODEL_DIR, "v2_metrics.json")
        if os.path.exists(metrics_path):
            with open(metrics_path) as f:
                metrics = json.load(f)
            version = metrics.get("model_version", "lr-calibrated-v2")
            self._versions[version] = metrics
            self._active_version = version

        model_path = os.path.join(LOCAL_MODEL_DIR, "lr_v2_calibrated.joblib")
        if os.path.exists(model_path):
            try:
                self._active_model = joblib.load(model_path)
            except Exception:
                pass

    def register_model(self, version: str, model_object: Any, metrics: dict,
                       artifacts: Optional[dict] = None) -> dict:
        """Register a new model version.

        In production: logs to MLflow with metrics, parameters, and artifacts.
        Locally: saves joblib + metrics JSON.
        """
        registration = {
            "version": version,
            "registered_at": datetime.utcnow().isoformat(),
            "metrics": metrics,
        }

        if self._mlflow:
            try:
                import mlflow
                with mlflow.start_run(run_name=f"model-{version}"):
                    # Log metrics
                    for key, value in metrics.items():
                        if isinstance(value, (int, float)):
                            mlflow.log_metric(key, value)

                    # Log model
                    mlflow.sklearn.log_model(model_object, "model")

                    # Log artifacts
                    if artifacts:
                        for name, path in artifacts.items():
                            if os.path.exists(path):
                                mlflow.log_artifact(path)

                    run_id = mlflow.active_run().info.run_id
                    registration["mlflow_run_id"] = run_id

                    # Register model
                    model_uri = f"runs:/{run_id}/model"
                    mlflow.register_model(model_uri, "nexusid-resolution")
            except Exception as e:
                registration["mlflow_error"] = str(e)

        # Always save locally as backup
        os.makedirs(LOCAL_MODEL_DIR, exist_ok=True)
        model_path = os.path.join(LOCAL_MODEL_DIR, f"{version}.joblib")
        joblib.dump(model_object, model_path)

        metrics_save = {k: v for k, v in metrics.items()
                        if not isinstance(v, (list, dict)) or k in ("confusion_matrix", "feature_importances")}
        metrics_save["model_version"] = version
        with open(os.path.join(LOCAL_MODEL_DIR, f"{version}_metrics.json"), "w") as f:
            json.dump(metrics_save, f, indent=2, default=str)

        with self._lock:
            self._versions[version] = {**metrics, "registered_at": registration["registered_at"]}

        registration["mode"] = "mlflow" if self._mlflow else "local"
        return registration

    def promote_model(self, version: str) -> dict:
        """Promote a model version to active serving.

        In production with Redis: publishes a hot-reload signal so all
        API workers pick up the new model without restart.
        """
        if version not in self._versions:
            # Try loading from disk
            model_path = os.path.join(LOCAL_MODEL_DIR, f"{version}.joblib")
            if not os.path.exists(model_path):
                return {"error": f"Model version {version} not found"}

        with self._lock:
            old_version = self._active_version
            self._active_version = version

            # Load the model object
            model_path = os.path.join(LOCAL_MODEL_DIR, f"{version}.joblib")
            if os.path.exists(model_path):
                try:
                    self._active_model = joblib.load(model_path)
                except Exception as e:
                    return {"error": f"Failed to load model: {e}"}

        # Signal hot-reload via Redis if available
        try:
            from backend.services.resolution.redis_layer import model_cache
            model_cache.set_active_version(version)
        except Exception:
            pass

        # MLflow: transition to Production stage
        if self._mlflow:
            try:
                import mlflow
                client = mlflow.tracking.MlflowClient()
                client.transition_model_version_stage(
                    name="nexusid-resolution",
                    version=version,
                    stage="Production",
                )
            except Exception:
                pass

        return {
            "promoted": version,
            "previous": old_version,
            "mode": "mlflow" if self._mlflow else "local",
        }

    def rollback_model(self, to_version: Optional[str] = None) -> dict:
        """Rollback to a previous model version."""
        if to_version:
            return self.promote_model(to_version)

        # Rollback to weighted-linear-v1 (the safe default)
        with self._lock:
            old = self._active_version
            self._active_version = "weighted-linear-v1"
            self._active_model = None

        return {"rolled_back_from": old, "active": "weighted-linear-v1"}

    def get_active_model(self) -> tuple[str, Optional[Any]]:
        """Get the active model version and object."""
        with self._lock:
            return self._active_version, self._active_model

    def predict(self, features: list[float]) -> float:
        """Run prediction using the active model.

        Falls back to weighted linear if no trained model is loaded.
        """
        _, model = self.get_active_model()

        if model and hasattr(model, "predict_proba"):
            import numpy as np
            proba = model.predict_proba(np.array([features]))[0][1]
            return float(proba)
        else:
            # Weighted linear fallback
            weights = [0.40, 0.25, 0.20, 0.10, 0.05]
            score = sum(w * f for w, f in zip(weights, features))
            return max(0.0, min(1.0, score))

    def list_versions(self) -> list[dict]:
        """List all registered model versions."""
        versions = []
        for v, metrics in self._versions.items():
            versions.append({
                "version": v,
                "pr_auc": metrics.get("pr_auc"),
                "roc_auc": metrics.get("roc_auc"),
                "false_merge_rate": metrics.get("false_merge_rate"),
                "registered_at": metrics.get("registered_at"),
                "is_active": v == self._active_version,
            })
        return versions

    @property
    def stats(self) -> dict:
        return {
            "mode": "mlflow" if self._mlflow else "local",
            "mlflow_uri": MLFLOW_URI or None,
            "active_version": self._active_version,
            "model_loaded": self._active_model is not None,
            "versions_registered": len(self._versions),
        }


# ─── Singleton ───────────────────────────────────────────────────────────────

registry = ModelRegistry()
