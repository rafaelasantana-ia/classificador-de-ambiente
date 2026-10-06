"""Gera dataset sintético estratificado e conjunto independente de generalização."""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from preprocessing import FEATURES, label_rules, load_data

TARGET_PER_CLASS = 250
CLASSES = ("normal", "presenca", "alerta", "critico")


def _candidate(rng, index):
    temp_ranges = [(20, 24), (25, 29), (30, 34), (35, 40)]
    humidity_ranges = [(40, 59), (60, 69), (70, 79), (80, 89), (90, 95)]
    if index % 3 == 0:
        temp = rng.choice([29, 29.2, 29.6, 29.9, 30, 30.1, 30.4, 31, 34, 34.5, 34.9, 35, 35.1, 35.5, 36])
        humidity = rng.choice([78, 78.5, 79, 79.8, 80, 80.2, 81, 88, 89, 89.5, 90, 90.5, 91, 92])
    else:
        temp_low, temp_high = temp_ranges[index % len(temp_ranges)]
        hum_low, hum_high = humidity_ranges[(index // len(temp_ranges)) % len(humidity_ranges)]
        temp = rng.uniform(temp_low, temp_high + 1e-6)
        humidity = rng.uniform(hum_low, hum_high + 1e-6)
    return {"temperatura_c": round(float(temp), 1), "umidade_pct": round(float(humidity), 1), "presenca": int(index % 2)}


def _make_synthetic(original, rules_path, seed):
    rng = np.random.default_rng(seed)
    counts = original["classe"].value_counts().to_dict()
    needed = {name: max(0, TARGET_PER_CLASS - int(counts.get(name, 0))) for name in CLASSES}
    used = set(map(tuple, original[FEATURES].round(1).to_numpy()))
    rows, attempts = [], 0
    while sum(needed.values()) and attempts < 3_000_000:
        attempts += 1
        row = _candidate(rng, attempts)
        key = tuple(row[name] for name in FEATURES)
        if key in used:
            continue
        label, _ = label_rules(pd.DataFrame([row]), rules_path)
        name = str(label.iloc[0])
        if needed.get(name, 0) <= 0:
            continue
        row.update({"classe": name, "origem": "sintetico"})
        rows.append(row)
        used.add(key)
        needed[name] -= 1
    if sum(needed.values()):
        raise RuntimeError(f"Não foi possível preencher as classes: {needed}")
    return pd.DataFrame(rows)


def _generalization(train, rules_path, seed):
    rng = np.random.default_rng(seed + 1)
    used = set(map(tuple, train[FEATURES].round(1).to_numpy()))
    rows = []
    for index in range(240):
        for attempt in range(1000):
            row = _candidate(rng, index + 17 * attempt)
            key = tuple(row[name] for name in FEATURES)
            if key not in used:
                break
        label, _ = label_rules(pd.DataFrame([row]), rules_path)
        row.update({"classe": str(label.iloc[0]), "origem": "sintetico_generalizacao"})
        rows.append(row)
        used.add(key)
    return pd.DataFrame(rows)


def generate(output: Path, rules_path: Path, seed: int = 42) -> pd.DataFrame:
    root = output.parents[1]
    real, audit = load_data(root / "data/dataset.xlsx")
    real["classe"], _ = label_rules(real, rules_path)
    real["origem"] = "real"
    synthetic = _make_synthetic(real, rules_path, seed)
    combined = pd.concat([real, synthetic], ignore_index=True).sample(frac=1, random_state=seed).reset_index(drop=True)
    generalization = _generalization(combined, rules_path, seed)
    raw_dir, synthetic_dir, processed_dir = root / "data/raw", root / "data/synthetic", root / "data/processed"
    for folder in (raw_dir, synthetic_dir, processed_dir, root / "reports"):
        folder.mkdir(parents=True, exist_ok=True)
    real.to_csv(raw_dir / "dados_reais.csv", index=False, float_format="%.1f")
    synthetic.to_csv(synthetic_dir / "dados_sinteticos.csv", index=False, float_format="%.1f")
    combined.to_csv(processed_dir / "dataset_treinamento.csv", index=False, float_format="%.1f")
    combined.to_csv(output, index=False, float_format="%.1f")
    generalization.to_csv(processed_dir / "test_generalization.csv", index=False, float_format="%.1f")
    generalization.to_csv(root / "data/test_generalization.csv", index=False, float_format="%.1f")
    report = {
        "original_rows": len(real), "expanded_rows": len(combined), "generalization_rows": len(generalization),
        "unique_combinations": int(combined[FEATURES].drop_duplicates().shape[0]),
        "exact_duplicate_rows": int(combined.duplicated().sum()), "feature_duplicate_rows": int(combined.duplicated(FEATURES).sum()),
        "class_counts": combined["classe"].value_counts().reindex(CLASSES, fill_value=0).to_dict(),
        "origin_counts": combined["origem"].value_counts().to_dict(),
        "ranges": {feature: [float(combined[feature].min()), float(combined[feature].max())] for feature in FEATURES[:2]},
        "presence_counts": combined["presenca"].value_counts().sort_index().to_dict(),
        "synthetic_label_warning": "Rótulos são derivados de regras determinísticas; dados sintéticos ampliam cobertura, mas não comprovam comportamento industrial.",
        "audit_original": audit,
    }
    serialized_report = json.dumps(report, indent=2, ensure_ascii=False)
    (root / "reports/dataset_analysis.json").write_text(serialized_report, encoding="utf-8")
    (root / "reports/dataset_expanded.json").write_text(serialized_report, encoding="utf-8")
    (root / "reports/dataset_analysis.md").write_text(
        f"# Análise do dataset\n\n"
        f"- Original: {len(real)} registros.\n- Expandido: {len(combined)} registros.\n"
        f"- Generalização independente: {len(generalization)} registros.\n"
        f"- Combinações únicas: {report['unique_combinations']}.\n"
        f"- Duplicatas de combinação removidas no treinamento: {report['feature_duplicate_rows']}.\n"
        f"- Classes: {report['class_counts']}.\n- Origens: {report['origin_counts']}.\n"
        f"- Temperatura: {report['ranges']['temperatura_c']} °C; umidade: {report['ranges']['umidade_pct']} %.\n\n"
        f"Os dados sintéticos são identificados por `origem=sintetico`. Os rótulos são derivados das regras determinísticas da prova de conceito.\n",
        encoding="utf-8",
    )
    return combined


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/dataset_expanded.csv")
    parser.add_argument("--rules", default="data/rules.json")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    frame = generate(Path(args.output), Path(args.rules), args.seed)
    print(json.dumps({"rows": len(frame), "classes": frame["classe"].value_counts().to_dict()}, ensure_ascii=False))
