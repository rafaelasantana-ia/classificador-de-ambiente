"""Gera um dataset expandido e reproduzível sem apagar a coleta original."""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from preprocessing import label_rules


TARGETS = {"normal": 155, "presenca": 155, "alerta": 155, "critico": 155}


def generate(output: Path, rules_path: Path, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    original = pd.read_csv(Path("data/clean.csv"))
    original["classe"], _ = label_rules(original, rules_path)
    original["origem"] = "real"
    existing = original["classe"].value_counts().to_dict()
    needed = {key: max(0, value - int(existing.get(key, 0))) for key, value in TARGETS.items()}
    rows = []
    attempts = 0
    while sum(needed.values()) and attempts < 2_000_000:
        attempts += 1
        row = {
            "temperatura_c": round(float(rng.uniform(20, 40)), 1),
            "umidade_pct": round(float(rng.uniform(40, 95)), 1),
            "presenca": int(rng.integers(0, 2)),
        }
        label, _ = label_rules(pd.DataFrame([row]), rules_path)
        wanted = label.iloc[0]
        if needed.get(wanted, 0) <= 0:
            continue
        row.update({"classe": wanted, "origem": "sintetico"})
        rows.append(row)
        needed[wanted] -= 1
    if sum(needed.values()):
        raise RuntimeError("Não foi possível balancear o dataset dentro do limite de tentativas.")

    expanded = pd.concat([original, pd.DataFrame(rows)], ignore_index=True)
    expanded = expanded.sample(frac=1, random_state=seed).reset_index(drop=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    expanded.to_csv(output, index=False, float_format="%.1f")
    report = {
        "seed": seed,
        "rows": len(expanded),
        "origin_counts": expanded["origem"].value_counts().to_dict(),
        "class_counts": expanded["classe"].value_counts().to_dict(),
        "feature_unique": int(expanded[["temperatura_c", "umidade_pct", "presenca"]].drop_duplicates().shape[0]),
        "synthetic_note": "A parte sintética amplia a cobertura de cenários; não substitui coleta real nem validação industrial.",
    }
    Path("reports").mkdir(exist_ok=True)
    Path("reports/dataset_expanded.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return expanded


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/dataset_expanded.csv")
    parser.add_argument("--rules", default="data/rules.json")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    frame = generate(Path(args.output), Path(args.rules), args.seed)
    print(json.dumps({"rows": len(frame), "classes": frame["classe"].value_counts().to_dict()}, ensure_ascii=False))
