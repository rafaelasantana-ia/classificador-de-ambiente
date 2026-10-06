"""Compara o modelo selecionado com as regras em uma grade do domínio."""
import argparse
import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, f1_score

from preprocessing import FEATURES, label_rules


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="models/model.pkl")
    parser.add_argument("--rules", default="data/rules.json")
    parser.add_argument("--samples", type=int, default=20000)
    args = parser.parse_args()
    artifact = pickle.loads(Path(args.model).read_bytes())
    rng = np.random.default_rng(42)
    values = np.column_stack([rng.uniform(20, 40, args.samples), rng.uniform(40, 95, args.samples), rng.integers(0, 2, args.samples)]).astype(np.float32)
    frame = pd.DataFrame(values, columns=FEATURES)
    rules_labels, _ = label_rules(frame, args.rules)
    model_names = np.asarray(artifact["classes"])[artifact["model"].predict(values)]
    different = model_names != rules_labels.to_numpy()
    report = {"samples": args.samples, "domain": {"temperature": [20, 40], "humidity": [40, 95], "presence": [0, 1]}, "accuracy_model_vs_rules": float(accuracy_score(rules_labels, model_names)), "f1_macro_model_vs_rules": float(f1_score(rules_labels, model_names, average="macro")), "divergences": int(different.sum()), "divergence_percent": float(different.mean() * 100), "classification_report": classification_report(rules_labels, model_names, labels=artifact["classes"], output_dict=True, zero_division=0), "examples": []}
    report["examples"] = [{**{key: float(value) for key, value in zip(FEATURES, values[i])}, "model": model_names[i], "rules": rules_labels.iloc[i]} for i in np.flatnonzero(different)[:25]]
    Path("reports").mkdir(exist_ok=True)
    Path("reports/rules_comparison.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("samples", "accuracy_model_vs_rules", "f1_macro_model_vs_rules", "divergences", "divergence_percent")}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
