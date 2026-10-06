"""Compara o modelo exportado com as regras determinísticas em uma grade ampla."""
import argparse
import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

from preprocessing import FEATURES, label_rules


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="models/model.pkl")
    parser.add_argument("--rules", default="data/rules.json")
    parser.add_argument("--samples", type=int, default=20000)
    args = parser.parse_args()
    artifact = pickle.loads(Path(args.model).read_bytes())
    rng = np.random.default_rng(42)
    grid = np.column_stack([
        rng.uniform(0, 50, args.samples),
        rng.uniform(0, 100, args.samples),
        rng.integers(0, 2, args.samples),
    ]).astype(np.float32)
    values = pd.DataFrame(grid, columns=FEATURES)
    rules, _ = label_rules(values, args.rules)
    model_names = np.asarray(artifact["classes"])[artifact["model"].predict(grid)]
    different = model_names != rules.to_numpy()
    by_pair = {}
    for model_name, rule_name in zip(model_names[different], rules.to_numpy()[different]):
        key = f"{model_name} -> {rule_name}"
        by_pair[key] = by_pair.get(key, 0) + 1
    report = {
        "samples": args.samples,
        "divergences": int(different.sum()),
        "divergence_percent": float(different.mean() * 100),
        "agreement_percent": float((~different).mean() * 100),
        "divergences_by_pair": dict(sorted(by_pair.items(), key=lambda item: -item[1])),
        "examples": [
            {**{key: float(value) for key, value in zip(FEATURES, grid[i])}, "model": model_names[i], "rules": rules.iloc[i]}
            for i in np.flatnonzero(different)[:25]
        ],
        "interpretation": "Divergências são esperadas em regiões pouco representadas; regras determinísticas continuam sendo o fallback de segurança.",
    }
    Path("reports").mkdir(exist_ok=True)
    Path("reports/rules_comparison.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
