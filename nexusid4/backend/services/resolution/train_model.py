"""NexusID — Trained Logistic Regression Model + Calibration Report.

Trains an LR model on labelled data from the synthetic generator,
evaluates precision/recall, generates a standalone HTML calibration report.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from typing import Optional

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    precision_recall_curve, roc_curve, auc,
    precision_score, recall_score, f1_score,
    confusion_matrix, classification_report
)
import joblib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.models import (
    BusinessRecordDB, CandidatePairDB, SessionLocal, init_db
)
from backend.services.resolution.scoring import compute_features, score_pair, WEIGHTS


_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
MODEL_DIR = os.path.join(_PROJECT_ROOT, "saved_models")
REPORT_DIR = os.path.join(_PROJECT_ROOT, "docs", "calibration")


def build_labelled_dataset(db) -> tuple[np.ndarray, np.ndarray, list[dict]]:
    """Build feature matrix and labels from ground-truth data.

    Uses gt_id to determine true matches: if two records share the same gt_id,
    they are a true match.
    """
    records = db.query(BusinessRecordDB).all()
    record_map = {r.id: r for r in records}

    # Get all candidate pairs
    pairs = db.query(CandidatePairDB).filter(
        CandidatePairDB.score.isnot(None)
    ).all()

    X_rows = []
    y_rows = []
    metadata = []

    for pair in pairs:
        rec_a = record_map.get(pair.record_a_id)
        rec_b = record_map.get(pair.record_b_id)
        if not rec_a or not rec_b:
            continue

        features = compute_features(rec_a, rec_b)
        fv = [
            features.anchor_score,
            features.name_score,
            features.address_score,
            features.contact_score,
            features.date_proximity_score,
        ]
        X_rows.append(fv)

        # Ground truth: same gt_id = match
        is_match = (rec_a.gt_id and rec_b.gt_id and rec_a.gt_id == rec_b.gt_id)
        y_rows.append(1 if is_match else 0)

        metadata.append({
            "pair_id": pair.id,
            "score": pair.score,
            "decision": pair.decision,
            "gt_match": is_match,
            "name_a": rec_a.business_name[:30],
            "name_b": rec_b.business_name[:30],
        })

    return np.array(X_rows), np.array(y_rows), metadata


def train_model(X: np.ndarray, y: np.ndarray, seed: int = 42) -> dict:
    """Train a calibrated LR model and compute all metrics."""
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=seed, stratify=y
    )

    # Train base LR
    lr = LogisticRegression(
        C=1.0, max_iter=1000, random_state=seed,
        class_weight="balanced"
    )
    lr.fit(X_train, y_train)

    # Calibrate with Platt scaling
    calibrated = CalibratedClassifierCV(lr, cv=3, method="sigmoid")
    calibrated.fit(X_train, y_train)

    # Predictions
    y_proba_test = calibrated.predict_proba(X_test)[:, 1]
    y_proba_train = calibrated.predict_proba(X_train)[:, 1]

    # PR curve
    precision_vals, recall_vals, pr_thresholds = precision_recall_curve(y_test, y_proba_test)
    pr_auc = auc(recall_vals, precision_vals)

    # ROC curve
    fpr, tpr, roc_thresholds = roc_curve(y_test, y_proba_test)
    roc_auc = auc(fpr, tpr)

    # Find optimal thresholds
    # Auto-link: lowest threshold where precision >= 0.99
    auto_link_threshold = 0.88
    for i, (p, t) in enumerate(zip(precision_vals[:-1], pr_thresholds)):
        if p >= 0.99:
            auto_link_threshold = float(t)
            break

    # Review: highest threshold where recall >= 0.95
    review_threshold = 0.55
    for i in range(len(precision_vals) - 2, -1, -1):
        if recall_vals[i] >= 0.95 and pr_thresholds[i] < auto_link_threshold:
            review_threshold = float(pr_thresholds[i])
            break

    # Metrics at auto-link threshold
    y_pred_auto = (y_proba_test >= auto_link_threshold).astype(int)
    cm = confusion_matrix(y_test, y_pred_auto)
    tp = int(cm[1, 1]) if cm.shape[0] > 1 else 0
    fp = int(cm[0, 1]) if cm.shape[0] > 1 else 0
    fn = int(cm[1, 0]) if cm.shape[0] > 1 else 0
    tn = int(cm[0, 0])

    false_merge_rate = fp / max(tp + fp, 1)
    precision_at_auto = precision_score(y_test, y_pred_auto, zero_division=0)
    recall_at_auto = recall_score(y_test, y_pred_auto, zero_division=0)

    # Feature importances (LR coefficients)
    feature_names = ["anchor", "name", "address", "contact", "date_proximity"]
    coefs = lr.coef_[0].tolist()
    importances = {fn: round(c, 4) for fn, c in zip(feature_names, coefs)}

    # Calibration curve data
    from sklearn.calibration import calibration_curve
    fraction_positives, mean_predicted = calibration_curve(
        y_test, y_proba_test, n_bins=10, strategy="uniform"
    )

    # Save model
    os.makedirs(MODEL_DIR, exist_ok=True)
    model_path = os.path.join(MODEL_DIR, "lr_v2_calibrated.joblib")
    joblib.dump(calibrated, model_path)

    # Also save the base LR for SHAP-like explanations
    joblib.dump(lr, os.path.join(MODEL_DIR, "lr_v2_base.joblib"))

    metrics = {
        "model_version": "lr-calibrated-v2",
        "model_path": model_path,
        "train_size": len(X_train),
        "test_size": len(X_test),
        "positive_rate": float(y.mean()),
        "pr_auc": round(pr_auc, 4),
        "roc_auc": round(roc_auc, 4),
        "auto_link_threshold": round(auto_link_threshold, 4),
        "review_threshold": round(review_threshold, 4),
        "precision_at_auto": round(precision_at_auto, 4),
        "recall_at_auto": round(recall_at_auto, 4),
        "false_merge_rate": round(false_merge_rate, 4),
        "confusion_matrix": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "feature_importances": importances,
        "pr_curve": {
            "precision": precision_vals.tolist(),
            "recall": recall_vals.tolist(),
            "thresholds": pr_thresholds.tolist(),
        },
        "roc_curve": {
            "fpr": fpr.tolist(),
            "tpr": tpr.tolist(),
        },
        "calibration_curve": {
            "fraction_positives": fraction_positives.tolist(),
            "mean_predicted": mean_predicted.tolist(),
        },
        "trained_at": datetime.utcnow().isoformat(),
    }

    # Save metrics JSON
    metrics_save = {k: v for k, v in metrics.items()
                    if k not in ("pr_curve", "roc_curve", "calibration_curve")}
    metrics_json_path = os.path.join(MODEL_DIR, "v2_metrics.json")
    with open(metrics_json_path, "w") as f:
        json.dump(metrics_save, f, indent=2, default=str)

    return metrics


def generate_calibration_report(metrics: dict) -> str:
    """Generate a standalone HTML calibration report."""
    pr = metrics["pr_curve"]
    roc = metrics["roc_curve"]
    cal = metrics["calibration_curve"]
    cm = metrics["confusion_matrix"]
    imp = metrics["feature_importances"]

    # Build chart data as JSON for inline Plotly
    pr_data = json.dumps([{"x": r, "y": p} for p, r in zip(pr["precision"][:200], pr["recall"][:200])])
    roc_data = json.dumps([{"x": f, "y": t} for f, t in zip(roc["fpr"][:200], roc["tpr"][:200])])
    cal_data = json.dumps([{"x": m, "y": f} for m, f in zip(cal["mean_predicted"], cal["fraction_positives"])])
    imp_data = json.dumps([{"name": k, "value": abs(v)} for k, v in sorted(imp.items(), key=lambda x: abs(x[1]), reverse=True)])

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>NexusID — Model Calibration Report</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: 'Inter', system-ui, sans-serif; background: #0a0d14; color: #e6ebf5; padding: 40px; }}
  .header {{ text-align: center; margin-bottom: 40px; }}
  .header h1 {{ font-size: 28px; font-weight: 800; margin-bottom: 8px; }}
  .header p {{ color: #9ba6b8; font-size: 14px; }}
  .kpi-grid {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 16px; margin-bottom: 40px; }}
  .kpi {{ background: #11151f; border: 1px solid #1f2535; border-radius: 10px; padding: 20px; text-align: center; }}
  .kpi .value {{ font-size: 28px; font-weight: 700; font-family: 'JetBrains Mono', monospace; }}
  .kpi .label {{ font-size: 11px; color: #6b7488; text-transform: uppercase; letter-spacing: 1px; margin-top: 4px; }}
  .good {{ color: #2dd4a4; }}
  .warn {{ color: #f5a524; }}
  .bad {{ color: #f24c5c; }}
  .charts {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 40px; }}
  .chart-card {{ background: #11151f; border: 1px solid #1f2535; border-radius: 10px; padding: 20px; }}
  .chart-card h3 {{ font-size: 12px; color: #6b7488; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 16px; }}
  .cm-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; max-width: 300px; margin: 20px auto; }}
  .cm-cell {{ padding: 16px; border-radius: 8px; text-align: center; font-family: monospace; font-weight: 700; font-size: 20px; }}
  .cm-tp {{ background: rgba(45,212,164,0.15); color: #2dd4a4; }}
  .cm-tn {{ background: rgba(45,212,164,0.08); color: #2dd4a4; }}
  .cm-fp {{ background: rgba(242,76,92,0.15); color: #f24c5c; }}
  .cm-fn {{ background: rgba(245,165,36,0.15); color: #f5a524; }}
  .cm-label {{ font-size: 9px; display: block; margin-top: 4px; opacity: 0.7; }}
  .thresholds {{ background: #11151f; border: 1px solid #1f2535; border-radius: 10px; padding: 24px; margin-bottom: 40px; }}
  .threshold-bar {{ height: 32px; border-radius: 8px; display: flex; overflow: hidden; margin: 16px 0; }}
  .threshold-bar div {{ display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 600; }}
  .meta {{ text-align: center; color: #6b7488; font-size: 12px; margin-top: 40px; }}
</style>
</head>
<body>
<div class="header">
  <h1>NexusID Model Calibration Report</h1>
  <p>Model: {metrics['model_version']} · Trained: {metrics['trained_at'][:19]} · Dataset: {metrics['train_size'] + metrics['test_size']} pairs ({metrics['test_size']} held out)</p>
</div>

<div class="kpi-grid">
  <div class="kpi">
    <div class="value good">{metrics['pr_auc']}</div>
    <div class="label">PR-AUC</div>
  </div>
  <div class="kpi">
    <div class="value good">{metrics['roc_auc']}</div>
    <div class="label">ROC-AUC</div>
  </div>
  <div class="kpi">
    <div class="value {'good' if metrics['precision_at_auto'] >= 0.98 else 'warn'}">{metrics['precision_at_auto']}</div>
    <div class="label">Precision @ Auto-link</div>
  </div>
  <div class="kpi">
    <div class="value {'good' if metrics['false_merge_rate'] < 0.01 else 'bad'}">{metrics['false_merge_rate']}</div>
    <div class="label">False Merge Rate</div>
  </div>
  <div class="kpi">
    <div class="value">{metrics['recall_at_auto']}</div>
    <div class="label">Recall @ Auto-link</div>
  </div>
</div>

<div class="thresholds">
  <h3 style="font-size:12px;color:#6b7488;text-transform:uppercase;letter-spacing:1px;margin-bottom:12px;">Suggested Thresholds</h3>
  <div class="threshold-bar">
    <div style="width:{metrics['review_threshold']*100}%;background:rgba(107,116,136,0.3);color:#6b7488;">HOLD &lt; {metrics['review_threshold']:.2f}</div>
    <div style="width:{(metrics['auto_link_threshold']-metrics['review_threshold'])*100}%;background:rgba(245,165,36,0.3);color:#f5a524;">REVIEW {metrics['review_threshold']:.2f}–{metrics['auto_link_threshold']:.2f}</div>
    <div style="width:{(1-metrics['auto_link_threshold'])*100}%;background:rgba(45,212,164,0.3);color:#2dd4a4;">AUTO ≥ {metrics['auto_link_threshold']:.2f}</div>
  </div>
</div>

<div class="charts">
  <div class="chart-card">
    <h3>Precision-Recall Curve</h3>
    <div id="pr-chart"></div>
  </div>
  <div class="chart-card">
    <h3>ROC Curve</h3>
    <div id="roc-chart"></div>
  </div>
  <div class="chart-card">
    <h3>Calibration Plot</h3>
    <div id="cal-chart"></div>
  </div>
  <div class="chart-card">
    <h3>Feature Importances (|coefficient|)</h3>
    <div id="imp-chart"></div>
  </div>
</div>

<div class="chart-card" style="max-width:400px;margin:0 auto 40px;">
  <h3 style="font-size:12px;color:#6b7488;text-transform:uppercase;letter-spacing:1px;margin-bottom:16px;text-align:center;">Confusion Matrix @ Auto-link Threshold</h3>
  <div class="cm-grid">
    <div class="cm-cell cm-tn">{cm['tn']}<span class="cm-label">True Neg</span></div>
    <div class="cm-cell cm-fp">{cm['fp']}<span class="cm-label">False Pos (wrong merge)</span></div>
    <div class="cm-cell cm-fn">{cm['fn']}<span class="cm-label">False Neg (missed)</span></div>
    <div class="cm-cell cm-tp">{cm['tp']}<span class="cm-label">True Pos</span></div>
  </div>
</div>

<div class="meta">
  Generated by NexusID Calibration Pipeline · Positive rate: {metrics['positive_rate']:.3f} · Seed: 42
</div>

<script>
const layout = {{paper_bgcolor:'transparent',plot_bgcolor:'transparent',font:{{color:'#9ba6b8',size:11}},margin:{{t:10,b:40,l:50,r:20}},xaxis:{{gridcolor:'#1f2535'}},yaxis:{{gridcolor:'#1f2535'}}}};
const prData = {pr_data};
Plotly.newPlot('pr-chart',[{{x:prData.map(d=>d.x),y:prData.map(d=>d.y),type:'scatter',mode:'lines',line:{{color:'#2e7cff',width:2}},name:'PR'}}],{{...layout,xaxis:{{...layout.xaxis,title:'Recall'}},yaxis:{{...layout.yaxis,title:'Precision'}}}},{{responsive:true,displayModeBar:false}});
const rocData = {roc_data};
Plotly.newPlot('roc-chart',[{{x:rocData.map(d=>d.x),y:rocData.map(d=>d.y),type:'scatter',mode:'lines',line:{{color:'#2dd4a4',width:2}},name:'ROC'}},{{x:[0,1],y:[0,1],type:'scatter',mode:'lines',line:{{color:'#2a3142',dash:'dash'}},showlegend:false}}],{{...layout,xaxis:{{...layout.xaxis,title:'FPR'}},yaxis:{{...layout.yaxis,title:'TPR'}}}},{{responsive:true,displayModeBar:false}});
const calData = {cal_data};
Plotly.newPlot('cal-chart',[{{x:calData.map(d=>d.x),y:calData.map(d=>d.y),type:'scatter',mode:'lines+markers',line:{{color:'#f5a524',width:2}},marker:{{size:6}},name:'Model'}},{{x:[0,1],y:[0,1],type:'scatter',mode:'lines',line:{{color:'#2a3142',dash:'dash'}},showlegend:false}}],{{...layout,xaxis:{{...layout.xaxis,title:'Mean Predicted'}},yaxis:{{...layout.yaxis,title:'Fraction Positives'}}}},{{responsive:true,displayModeBar:false}});
const impData = {imp_data};
Plotly.newPlot('imp-chart',[{{y:impData.map(d=>d.name),x:impData.map(d=>d.value),type:'bar',orientation:'h',marker:{{color:['#2e7cff','#6ba8ff','#2dd4a4','#f5a524','#f24c5c']}}}}],{{...layout,xaxis:{{...layout.xaxis,title:'|Coefficient|'}},yaxis:{{...layout.yaxis,autorange:'reversed'}},margin:{{...layout.margin,l:100}}}},{{responsive:true,displayModeBar:false}});
</script>
</body>
</html>"""

    os.makedirs(REPORT_DIR, exist_ok=True)
    report_path = os.path.join(REPORT_DIR, "v2_calibration_report.html")
    with open(report_path, "w") as f:
        f.write(html)

    return report_path


def run_training():
    """Full training pipeline."""
    print("=" * 50)
    print("NexusID Model Training Pipeline")
    print("=" * 50)

    init_db()
    db = SessionLocal()

    print("[1/4] Building labelled dataset...")
    X, y, meta = build_labelled_dataset(db)
    print(f"  {len(X)} pairs, {y.sum()} positives ({y.mean()*100:.1f}%)")

    if len(X) < 50:
        print("ERROR: Not enough data to train. Run the pipeline first.")
        return None

    print("[2/4] Training calibrated LR model...")
    t0 = time.time()
    metrics = train_model(X, y)
    print(f"  Trained in {time.time()-t0:.1f}s")

    print("[3/4] Metrics:")
    print(f"  PR-AUC:           {metrics['pr_auc']}")
    print(f"  ROC-AUC:          {metrics['roc_auc']}")
    print(f"  Precision@auto:   {metrics['precision_at_auto']}")
    print(f"  Recall@auto:      {metrics['recall_at_auto']}")
    print(f"  False merge rate: {metrics['false_merge_rate']}")
    print(f"  Auto-link thresh: {metrics['auto_link_threshold']}")
    print(f"  Review thresh:    {metrics['review_threshold']}")
    print(f"  Feature importances: {metrics['feature_importances']}")

    print("[4/4] Generating calibration report...")
    report_path = generate_calibration_report(metrics)
    print(f"  Report: {report_path}")

    # Save metrics JSON
    metrics_path = os.path.join(MODEL_DIR, "v2_metrics.json")
    # Remove numpy arrays for JSON serialization
    metrics_save = {k: v for k, v in metrics.items()
                    if k not in ("pr_curve", "roc_curve", "calibration_curve")}
    with open(metrics_path, "w") as f:
        json.dump(metrics_save, f, indent=2, default=str)

    db.close()
    print(f"\n✅ Model trained and saved to {metrics['model_path']}")
    return metrics


if __name__ == "__main__":
    run_training()
