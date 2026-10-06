"""Treina e exporta a previsao temporal de temperatura para o Pico W."""
import json
import pickle
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.ensemble import RandomForestRegressor
from sklearn.tree import DecisionTreeRegressor

WINDOW = 10
HORIZON_SECONDS = 60
FEATURES = [
    "temperatura_atual", "umidade_atual", "presenca_atual", "media_temperatura_janela",
    "media_umidade_janela", "variacao_temperatura", "variacao_umidade",
    "tendencia_temperatura", "tendencia_umidade", "quantidade_presenca_janela",
]
TARGET = "temp_future_60s"


def metrics(y_true, y_pred):
    return {"mae": float(mean_absolute_error(y_true, y_pred)),
            "rmse": float(mean_squared_error(y_true, y_pred) ** 0.5),
            "r2": float(r2_score(y_true, y_pred))}


def split_by_session(frame):
    sessions = sorted(frame.session_id.unique())
    train_end, val_end = int(len(sessions) * .6), int(len(sessions) * .8)
    parts = [frame.session_id.isin(sessions[:train_end]),
             frame.session_id.isin(sessions[train_end:val_end]),
             frame.session_id.isin(sessions[val_end:])]
    return [frame.loc[mask].reset_index(drop=True) for mask in parts]


def export_header(model, report, path):
    weights = np.asarray(model.coef_, dtype=float).reshape(-1)
    bias = float(model.intercept_)
    values = ", ".join(f"{value:.9g}f" for value in weights)
    text = f'''#pragma once
// Gerado por training/train_regression.py. Nao edite manualmente.
#include <math.h>

constexpr int REGRESSION_FEATURE_COUNT = {len(FEATURES)};
constexpr float REGRESSION_WEIGHTS[REGRESSION_FEATURE_COUNT] = {{{values}}};
constexpr float REGRESSION_BIAS = {bias:.9g}f;
constexpr float REGRESSION_MAE = {report["test"]["mae"]:.6f}f;
constexpr float REGRESSION_RMSE = {report["test"]["rmse"]:.6f}f;
constexpr int REGRESSION_HORIZON_SECONDS = {HORIZON_SECONDS};

inline float regression_predict(const float features[REGRESSION_FEATURE_COUNT]) {{
  float result = REGRESSION_BIAS;
  for (int i = 0; i < REGRESSION_FEATURE_COUNT; ++i) result += REGRESSION_WEIGHTS[i] * features[i];
  return result;
}}
'''
    path.write_text(text, encoding="utf-8")


def main():
    root = Path(__file__).resolve().parents[1]
    frame = pd.read_csv(root / "data/synthetic/regression_windows.csv")
    train, validation, test = split_by_session(frame)
    x_train, y_train = train[FEATURES], train[TARGET]
    x_val, y_val = validation[FEATURES], validation[TARGET]
    x_test, y_test = test[FEATURES], test[TARGET]

    models = {
        "baseline_atual": None,
        "baseline_tendencia": None,
        "linear": LinearRegression(),
        "ridge": Ridge(alpha=1.0),
        "arvore": DecisionTreeRegressor(max_depth=4, min_samples_leaf=4, random_state=42),
        "floresta": RandomForestRegressor(n_estimators=32, max_depth=6, min_samples_leaf=3, random_state=42, n_jobs=-1),
    }
    rows, fitted = [], {}
    for name, model in models.items():
        if model is None:
            val_pred = validation["temperatura_atual"].to_numpy() if name == "baseline_atual" else validation["temperatura_atual"].to_numpy() + validation["tendencia_temperatura"].to_numpy() * 30
            test_pred = test["temperatura_atual"].to_numpy() if name == "baseline_atual" else test["temperatura_atual"].to_numpy() + test["tendencia_temperatura"].to_numpy() * 30
        else:
            model.fit(x_train, y_train)
            fitted[name] = model
            val_pred, test_pred = model.predict(x_val), model.predict(x_test)
        val_metrics, test_metrics = metrics(y_val, val_pred), metrics(y_test, test_pred)
        rows.append({"modelo": name, "tipo": "baseline" if model is None else "regressor", **{"validacao_" + k: v for k, v in val_metrics.items()}, **{"teste_" + k: v for k, v in test_metrics.items()}})

    comparison = pd.DataFrame(rows).sort_values("validacao_mae")
    best_mae = float(comparison.loc[comparison.modelo.isin(fitted), "validacao_mae"].min())
    eligible = comparison[(comparison.modelo.isin(fitted)) & (comparison.validacao_mae <= best_mae * 1.05)]
    preference = {"linear": 0, "ridge": 1, "arvore": 2, "floresta": 3}
    selected_name = sorted(eligible.modelo, key=lambda value: preference[value])[0]
    selected = fitted[selected_name]
    selected_test = selected.predict(x_test)
    report = {
        "task": "regressao_temporal_temperatura",
        "model": selected_name,
        "features": FEATURES,
        "target": TARGET,
        "window_readings": WINDOW,
        "horizon_seconds": HORIZON_SECONDS,
        "split": "por sessao temporal: 60% treino, 20% validacao, 20% teste",
        "samples": {"total": len(frame), "train": len(train), "validation": len(validation), "test": len(test), "sessions": frame.session_id.nunique()},
        "selection_rule": "menor MAE de validacao; entre modelos ate 5% do melhor, escolhe o mais simples exportavel",
        "test": metrics(y_test, selected_test),
        "comparison": rows,
        "warning": "As janelas sao sinteticas e coerentes; a coleta real nao tem timestamps/sessoes para formar alvo futuro.",
    }
    reports = root / "reports"
    reports.mkdir(exist_ok=True)
    comparison.to_csv(reports / "regression_comparison.csv", index=False)
    (reports / "regression.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    (reports / "regression_evaluation.md").write_text("# Regressao temporal\n\n" + json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    with (root / "models/regressor.pkl").open("wb") as file:
        pickle.dump({"model": selected, "features": FEATURES, "target": TARGET, "horizon_seconds": HORIZON_SECONDS, "report": report}, file)
    export_header(selected, report, root / "models/regressor_data.h")

    pred = selected_test
    pd.DataFrame({"real": y_test, "previsto": pred, "erro": y_test.to_numpy() - pred, "session_id": test.session_id, "step": test.step}).to_csv(reports / "regression_test.csv", index=False)
    plt.figure(figsize=(9, 4)); plt.plot(y_test.to_numpy()[:180], label="Real"); plt.plot(pred[:180], label="Previsto +60s"); plt.legend(); plt.ylabel("Temperatura (°C)"); plt.tight_layout(); plt.savefig(reports / "regression_real_vs_predicted.png", dpi=140); plt.close()
    plt.figure(figsize=(7, 4)); plt.hist(y_test.to_numpy() - pred, bins=25); plt.xlabel("Erro (°C)"); plt.ylabel("Frequência"); plt.tight_layout(); plt.savefig(reports / "regression_residuals.png", dpi=140); plt.close()
    print(json.dumps({"model": selected_name, "samples": len(frame), "test": report["test"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
