"""Pipeline único: expansão, limpeza, treinamento, comparação e verificação."""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from generate_dataset import generate


def run(command):
    print("$", " ".join(map(str, command)))
    subprocess.run(command, check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--compiler", default=None)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    python = sys.executable
    generate(root / "data/dataset_expanded.csv", root / "data/rules.json")
    run([python, str(root / "training/train.py"), "--data", "data/dataset_expanded.csv", "--rules", "data/rules.json"])
    run([python, str(root / "training/compare_rules.py")])
    run([python, str(root / "training/coverage.py")])
    run([python, str(root / "training/generate_regression_dataset.py")])
    run([python, str(root / "training/train_regression.py")])
    shutil.copyfile(root / "data/dataset_expanded.csv", root / "web/src/data/clean.csv")
    shutil.copyfile(root / "reports/training.json", root / "web/src/data/training.json")
    shutil.copyfile(root / "reports/regression.json", root / "web/src/data/regression.json")
    shutil.copyfile(root / "data/rules.json", root / "web/src/data/rules.json")
    compiler = args.compiler
    zig = root / ".tools/ziglang/zig.exe"
    if compiler:
        run([python, str(root / "training/verify_export.py"), "--compiler", compiler])
        run([python, str(root / "training/verify_regression.py"), "--compiler", compiler])
    elif zig.exists():
        run([python, str(root / "training/verify_export.py"), "--compiler", str(zig), "--zig"])
        run([python, str(root / "training/verify_regression.py"), "--compiler", str(zig), "--zig"])
    print("Pipeline concluído. Consulte reports/.")


if __name__ == "__main__":
    main()
