"""Analisa cobertura do domínio e gera regiões de decisão para presença 0/1."""
import json
import pickle
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from preprocessing import FEATURES, label_rules


def main():
    artifact = pickle.loads(Path("models/model.pkl").read_bytes())
    data = pd.read_csv("data/processed/dataset_treinamento.csv")
    temperatures = np.arange(20, 40.01, 0.25)
    humidities = np.arange(40, 95.01, 0.5)
    rows, regions = [], []
    for presence in (0, 1):
        points = np.array([(temperature, humidity, presence) for temperature in temperatures for humidity in humidities], dtype=np.float32)
        predictions = np.asarray(artifact["classes"])[artifact["model"].predict(points)]
        for name in artifact["classes"]:
            count = int(np.sum(predictions == name))
            rows.append({"presenca": presence, "classe": name, "count": count, "percent": count / len(points) * 100})
        grid_temp, grid_hum = np.meshgrid(temperatures, humidities)
        grid_pred = predictions.reshape(len(temperatures), len(humidities)).T
        plt.figure(figsize=(7, 4.5)); cmap = plt.get_cmap("viridis", len(artifact["classes"]))
        encoded = np.vectorize({name: i for i, name in enumerate(artifact["classes"])}.get)(grid_pred)
        plt.pcolormesh(grid_temp, grid_hum, encoded, cmap=cmap, shading="auto"); plt.colorbar(ticks=range(len(artifact["classes"])), label="Classe")
        plt.yticks([40, 60, 70, 80, 90, 95]); plt.xlabel("Temperatura (°C)"); plt.ylabel("Umidade (%)"); plt.title(f"Regiões de decisão · presença={presence}"); plt.tight_layout(); plt.savefig(f"reports/decision_regions_presence_{presence}.png", dpi=150); plt.close()

    data["temp_band"] = pd.cut(data["temperatura_c"], [19.99, 25, 30, 35, 40], labels=["20-25", "25-30", "30-35", "35-40"])
    data["humidity_band"] = pd.cut(data["umidade_pct"], [39.99, 60, 70, 80, 90, 100], labels=["40-60", "60-70", "70-80", "80-90", "90-100"])
    coverage = data.groupby(["temp_band", "humidity_band", "presenca"], observed=False).size().reset_index(name="samples")
    coverage["low_coverage"] = coverage["samples"] < 5
    coverage.to_csv("reports/coverage_regions.csv", index=False)
    low = coverage[coverage["low_coverage"]]
    Path("reports/coverage_analysis.json").write_text(json.dumps({"grid_points": len(temperatures) * len(humidities) * 2, "predictions": rows, "low_coverage_regions": low.to_dict(orient="records"), "note": "Baixa cobertura indica regiões com poucas combinações no treinamento; não é métrica de erro."}, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(json.dumps({"grid_points": len(temperatures) * len(humidities) * 2, "low_coverage_regions": len(low)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
