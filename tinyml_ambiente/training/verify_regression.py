"""Compara a previsao Python com o header C++ exportado."""
import argparse
import json
import pickle
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--compiler", required=True)
    parser.add_argument("--zig", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    with (root / "models/regressor.pkl").open("rb") as file:
        artifact = pickle.load(file)
    frame = pd.read_csv(root / "data/synthetic/regression_windows.csv").tail(250)
    features = artifact["features"]
    expected = artifact["model"].predict(frame[features])
    with tempfile.TemporaryDirectory() as directory:
        directory = Path(directory)
        source = directory / "verify.cpp"
        source.write_text('#include <iostream>\n#include "regressor_data.h"\nint main(){float x[10]; while(std::cin>>x[0]){for(int i=1;i<10;i++)std::cin>>x[i]; std::cout<<regression_predict(x)<<"\\n";}}', encoding="utf-8")
        if args.zig:
            command = [args.compiler, "c++", "-O2", str(source), "-I", str(root / "models"), "-o", str(directory / "verify.exe")]
        else:
            command = [args.compiler, "-O2", str(source), "-I", str(root / "models"), "-o", str(directory / "verify.exe")]
        subprocess.run(command, check=True, capture_output=True)
        payload = "\n".join(" ".join(f"{value:.9f}" for value in row) for row in frame[features].to_numpy()) + "\n"
        result = subprocess.run([str(directory / "verify.exe")], input=payload, text=True, capture_output=True, check=True)
    actual = np.array([float(value) for value in result.stdout.split()])
    errors = np.abs(expected - actual)
    report = {"points": len(actual), "max_abs_error": float(errors.max()), "mean_abs_error": float(errors.mean()), "divergences_over_0_001": int((errors > .001).sum()), "compiler": args.compiler}
    (root / "reports/regression_export_verification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
