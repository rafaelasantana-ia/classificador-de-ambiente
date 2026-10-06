"""Pipeline único: expansão, limpeza, treinamento, comparação e verificação."""
import argparse
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
    if args.compiler:
        run([python, str(root / "training/verify_export.py"), "--compiler", args.compiler])
    print("Pipeline concluído. Consulte reports/.")


if __name__ == "__main__":
    main()
