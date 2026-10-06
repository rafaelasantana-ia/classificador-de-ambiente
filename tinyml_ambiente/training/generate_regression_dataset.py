"""Gera sequências temporais coerentes para regressão de temperatura.

As sequências são sintéticas porque a coleta original não possui timestamps ou
identificador de sessão suficiente para construir um alvo futuro honesto.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

WINDOW = 10
HORIZON_STEPS = 30  # 30 leituras x 2 s = 60 s
SEQUENCES = 180
LENGTH = 50
FEATURES = [
    "temperatura_atual", "umidade_atual", "presenca_atual", "media_temperatura_janela",
    "media_umidade_janela", "variacao_temperatura", "variacao_umidade",
    "tendencia_temperatura", "tendencia_umidade", "quantidade_presenca_janela",
]


def build(seed=42):
    rng = np.random.default_rng(seed)
    readings = []
    scenarios = ("stable", "warm_slow", "warm_fast", "cool_slow", "cool_fast", "presence_in", "presence_long", "humidity_up", "humidity_down")
    for session in range(SEQUENCES):
        scenario = scenarios[session % len(scenarios)]
        temp = rng.uniform(22, 34)
        humidity = rng.uniform(45, 85)
        presence = int(rng.integers(0, 2))
        for step in range(LENGTH):
            noise_t, noise_h = rng.normal(0, 0.12), rng.normal(0, 0.55)
            if scenario == "warm_slow": temp += 0.06
            elif scenario == "warm_fast": temp += 0.16
            elif scenario == "cool_slow": temp -= 0.06
            elif scenario == "cool_fast": temp -= 0.16
            elif scenario == "humidity_up": humidity += 0.55
            elif scenario == "humidity_down": humidity -= 0.55
            elif scenario == "presence_in" and step > 12: presence = 1
            elif scenario == "presence_long": presence = 1 if step > 5 else 0
            if scenario in ("warm_slow", "warm_fast"): humidity += 0.08
            if scenario in ("cool_slow", "cool_fast"): humidity -= 0.08
            temp = float(np.clip(temp + noise_t, 20, 40))
            humidity = float(np.clip(humidity + noise_h, 40, 95))
            readings.append({"session_id": session, "step": step, "temperatura_c": round(temp, 2), "umidade_pct": round(humidity, 2), "presenca": presence, "cenario": scenario, "origem": "sintetico"})
    readings = pd.DataFrame(readings)
    windows = []
    for session_id, group in readings.groupby("session_id", sort=True):
        group = group.sort_values("step").reset_index(drop=True)
        for index in range(WINDOW - 1, LENGTH - HORIZON_STEPS):
            window = group.iloc[index - WINDOW + 1:index + 1]
            current = group.iloc[index]
            future = group.iloc[index + HORIZON_STEPS]
            temp_delta = float(window["temperatura_c"].iloc[-1] - window["temperatura_c"].iloc[0])
            humidity_delta = float(window["umidade_pct"].iloc[-1] - window["umidade_pct"].iloc[0])
            windows.append({"session_id": int(session_id), "step": int(current["step"]), **{
                "temperatura_atual": float(current["temperatura_c"]), "umidade_atual": float(current["umidade_pct"]), "presenca_atual": int(current["presenca"]),
                "media_temperatura_janela": float(window["temperatura_c"].mean()), "media_umidade_janela": float(window["umidade_pct"].mean()),
                "variacao_temperatura": temp_delta, "variacao_umidade": humidity_delta, "tendencia_temperatura": temp_delta / (WINDOW - 1), "tendencia_umidade": humidity_delta / (WINDOW - 1),
                "quantidade_presenca_janela": int(window["presenca"].sum()), "temp_future_60s": float(future["temperatura_c"]), "cenario": current["cenario"], "origem": "sintetico"}})
    windows = pd.DataFrame(windows)
    root = Path(__file__).resolve().parents[1]
    output = root / "data/synthetic/regression_windows.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    windows.to_csv(output, index=False, float_format="%.5f")
    (root / "reports").mkdir(exist_ok=True)
    summary = {"sequences": SEQUENCES, "sequence_length": LENGTH, "window": WINDOW, "horizon_steps": HORIZON_STEPS, "horizon_seconds": 60, "windows": len(windows), "origin": "sintetico", "scenarios": windows["cenario"].value_counts().to_dict(), "warning": "A coleta real não possui timestamps/sessões suficientes; não foi usada como sequência temporal."}
    (root / "reports/regression_dataset.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return windows


if __name__ == "__main__":
    print(json.dumps({"windows": len(build())}, ensure_ascii=False))
