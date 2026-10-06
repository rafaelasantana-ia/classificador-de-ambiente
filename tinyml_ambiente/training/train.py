"""Treina, compara e exporta modelos sem vazamento entre combinações."""
import argparse
import csv
import hashlib
import json
import pickle
import platform
import warnings
from importlib.metadata import version
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import StratifiedKFold, cross_val_predict, cross_validate, train_test_split
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier

from export import export_rules, export_tree
from preprocessing import FEATURES, label_rules, load_data

SEED = 42
SCORING = {"accuracy": "accuracy", "precision_macro": "precision_macro", "recall_macro": "recall_macro", "f1_macro": "f1_macro"}


def metrics(model, X, y, labels, names):
    prediction = model.predict(X)
    report = classification_report(y, prediction, labels=labels, target_names=names, output_dict=True, zero_division=0)
    return {
        "accuracy": float(report["accuracy"]), "precision_macro": float(report["macro avg"]["precision"]),
        "recall_macro": float(report["macro avg"]["recall"]), "f1_macro": float(report["macro avg"]["f1-score"]),
        "classification": report, "confusion_matrix": confusion_matrix(y, prediction, labels=labels).tolist(),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data/dataset_expanded.csv")
    parser.add_argument("--rules", required=True)
    args = parser.parse_args()
    np.random.seed(SEED)
    data, audit = load_data(args.data)
    labels, rules = label_rules(data, args.rules)
    before = len(data)
    duplicate_mask = data.duplicated(FEATURES, keep="first")
    data = data.loc[~duplicate_mask].reset_index(drop=True)
    labels = labels.loc[~duplicate_mask].reset_index(drop=True)
    audit.update({"rows_before_deduplication": before, "duplicate_feature_rows_removed": int(duplicate_mask.sum()), "rows_after_deduplication": len(data), "classes_all_measurements": labels.value_counts().to_dict()})
    encoder = LabelEncoder().fit(labels)
    y = encoder.transform(labels)
    class_ids = np.arange(len(encoder.classes_))
    X = data[FEATURES].to_numpy(dtype=np.float32)
    indices = np.arange(len(y))
    train_val, test = train_test_split(indices, test_size=0.15, random_state=SEED, stratify=y)
    train, validation = train_test_split(train_val, test_size=0.15 / 0.85, random_state=SEED, stratify=y[train_val])
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    candidates = {
        "logistic": make_pipeline(StandardScaler(), LogisticRegression(max_iter=3000, class_weight="balanced", random_state=SEED)),
        "tree": DecisionTreeClassifier(max_depth=4, min_samples_split=8, min_samples_leaf=3, class_weight="balanced", random_state=SEED),
        "forest": RandomForestClassifier(n_estimators=32, max_depth=6, min_samples_leaf=3, class_weight="balanced", random_state=SEED, n_jobs=-1),
        "mlp": make_pipeline(StandardScaler(), MLPClassifier(hidden_layer_sizes=(8, 4), max_iter=3000, random_state=SEED)),
        "dummy": DummyClassifier(strategy="most_frequent"),
    }
    results, comparison_rows, classification_rows = {}, [], []
    for name, candidate in candidates.items():
        with warnings.catch_warnings(record=True) as caught:
            scores = cross_validate(candidate, X[train], y[train], cv=cv, scoring=SCORING, error_score="raise")
            oof = cross_val_predict(candidate, X[train], y[train], cv=cv)
        candidate.fit(X[train], y[train])
        estimator = candidate.steps[-1][1] if hasattr(candidate, "steps") else candidate
        result = {metric: float(np.mean(scores[f"test_{metric}"])) for metric in SCORING}
        result["cv_std"] = {metric: float(np.std(scores[f"test_{metric}"])) for metric in SCORING}
        result["warnings"] = sorted(set(str(item.message) for item in caught))
        result["cv_classification"] = classification_report(y[train], oof, labels=class_ids, target_names=encoder.classes_, output_dict=True, zero_division=0)
        result["cv_confusion_matrix"] = confusion_matrix(y[train], oof, labels=class_ids).tolist()
        result["validation"] = metrics(candidate, X[validation], y[validation], class_ids, encoder.classes_)
        result["test"] = metrics(candidate, X[test], y[test], class_ids, encoder.classes_)
        result["pickle_bytes"] = len(pickle.dumps(candidate))
        if name == "tree":
            result.update({"nodes": estimator.tree_.node_count, "depth": estimator.get_depth(), "estimated_numeric_bytes": estimator.tree_.node_count * 16})
        elif name == "forest":
            nodes = sum(tree.tree_.node_count for tree in estimator.estimators_)
            result.update({"nodes": nodes, "estimated_numeric_bytes": nodes * 16})
        elif name == "mlp":
            parameters = sum(array.size for array in estimator.coefs_ + estimator.intercepts_)
            result.update({"parameters": parameters, "estimated_numeric_bytes": 4 * parameters + 24})
        elif name == "logistic":
            result["estimated_numeric_bytes"] = 4 * (estimator.coef_.size + estimator.intercept_.size) + 24
        else:
            result["estimated_numeric_bytes"] = 4
        results[name] = result
        comparison_rows.append({"model": name, "cv_f1_macro": result["f1_macro"], "cv_f1_std": result["cv_std"]["f1_macro"], "cv_recall_macro": result["recall_macro"], "validation_f1_macro": result["validation"]["f1_macro"], "test_f1_macro": result["test"]["f1_macro"], "estimated_bytes": result["estimated_numeric_bytes"]})
        test_matrix = np.asarray(result["test"]["confusion_matrix"])
        for class_index, (class_name, class_metrics) in enumerate(result["test"]["classification"].items()):
            if class_name in encoder.classes_:
                classification_rows.append({"model": name, "split": "test", "class": class_name, **{key: class_metrics[key] for key in ("precision", "recall", "f1-score", "support")}, "false_negatives": int(test_matrix[class_index, :].sum() - test_matrix[class_index, class_index])})

    tree_grid = []
    for depth in (2, 3, 4, 5, 6, 8, 10):
        candidate = DecisionTreeClassifier(max_depth=depth, min_samples_split=8, min_samples_leaf=3, class_weight="balanced", random_state=SEED)
        score = cross_validate(candidate, X[train], y[train], cv=cv, scoring=SCORING)
        sweep_oof = cross_val_predict(candidate, X[train], y[train], cv=cv)
        sweep_report = classification_report(y[train], sweep_oof, labels=class_ids, target_names=encoder.classes_, output_dict=True, zero_division=0)
        candidate.fit(X[train], y[train])
        tree_grid.append({"depth": depth, "nodes": candidate.tree_.node_count, "cv_accuracy": float(np.mean(score["test_accuracy"])), "cv_f1_macro": float(np.mean(score["test_f1_macro"])), "cv_f1_std": float(np.std(score["test_f1_macro"])), "cv_recall_critico": float(sweep_report.get("critico", {}).get("recall", 0)), "estimated_bytes": candidate.tree_.node_count * 16})

    best = max((name for name in candidates if name != "dummy"), key=lambda name: (results[name]["f1_macro"], results[name]["recall_macro"]))
    choice = "tree" if results["tree"]["f1_macro"] >= results[best]["f1_macro"] - 0.03 else best
    model = candidates[choice]
    model.fit(X[train_val], y[train_val])
    selected_test = metrics(model, X[test], y[test], class_ids, encoder.classes_)
    generalization_path = Path("data/processed/test_generalization.csv")
    generalization, _ = load_data(generalization_path)
    generalization_labels, _ = label_rules(generalization, args.rules)
    gx = generalization[FEATURES].to_numpy(dtype=np.float32)
    gy = encoder.transform(generalization_labels)
    generalization_metrics = metrics(model, gx, gy, class_ids, encoder.classes_)
    generalization_prediction = model.predict(gx)
    generalization_rows = []
    for row, real_label, predicted_label in zip(generalization.to_dict("records"), generalization_labels, encoder.inverse_transform(generalization_prediction)):
        generalization_rows.append({**{feature: row[feature] for feature in FEATURES}, "real": str(real_label), "prevista": str(predicted_label), "acertou": str(real_label) == str(predicted_label)})

    for folder in (Path("models"), Path("reports")): folder.mkdir(exist_ok=True)
    artifact = {"model": model, "features": FEATURES, "classes": encoder.classes_.tolist(), "rules": rules, "choice": choice, "synthetic_labels": True, "training_domain": {feature: [float(X[:, i].min()), float(X[:, i].max())] for i, feature in enumerate(FEATURES[:2])}}
    Path("models/model.pkl").write_bytes(pickle.dumps(artifact))
    np.savez("models/holdout.npz", X=X[test], y=y[test], train_X=X[train_val], train_y=y[train_val])
    if choice == "tree":
        export_tree(model, encoder.classes_, Path("models/model_data.h"))
        export_rules(rules, encoder.classes_, Path("models/rules_data.h"))

    pd.DataFrame(comparison_rows).to_csv("reports/model_comparison.csv", index=False)
    pd.DataFrame(classification_rows).to_csv("reports/classification_report.csv", index=False)
    pd.DataFrame(tree_grid).to_csv("reports/tree_depth_sweep.csv", index=False)
    pd.DataFrame(selected_test["confusion_matrix"], index=encoder.classes_, columns=encoder.classes_).to_csv("reports/confusion_matrix.csv")
    pd.DataFrame(generalization_rows).to_csv("reports/generalization_test.csv", index=False)
    plt.figure(figsize=(5, 4)); plt.imshow(selected_test["confusion_matrix"], cmap="Blues"); plt.colorbar(); plt.xticks(class_ids, encoder.classes_, rotation=35); plt.yticks(class_ids, encoder.classes_); plt.xlabel("Prevista"); plt.ylabel("Real"); plt.tight_layout(); plt.savefig("reports/confusion_matrix.png", dpi=150); plt.close()

    report = {"synthetic_labels": True, "limitation": "Rótulos derivados de regras; a expansão não equivale a novas medições reais.", "python": platform.python_version(), "dependencies": {name: version(name) for name in ["numpy", "pandas", "scikit-learn", "openpyxl"]}, "data_sha256": hashlib.sha256(Path(args.data).read_bytes()).hexdigest(), "rules_sha256": hashlib.sha256(Path(args.rules).read_bytes()).hexdigest(), "data_audit": audit, "cv": results, "selected": choice, "folds": 5, "train_unique": len(train_val), "validation_unique": len(validation), "test_unique": len(test), "holdout": selected_test, "generalization": generalization_metrics, "generalization_rows": len(generalization), "confusion_matrix": selected_test["confusion_matrix"], "tree_depth_sweep": tree_grid, "selection_policy": "F1 macro e recall crítico, com preferência por árvore quando a diferença é pequena e o custo embarcado é menor.", "split_warning": "Combinações idênticas foram removidas antes do split; generalização usa arquivo separado.", "header_bytes": Path("models/model_data.h").stat().st_size if choice == "tree" else None}
    Path("reports/training.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    Path("reports/model_evaluation.md").write_text(f"# Avaliação\n\nModelo selecionado: **{choice}**\n\n- Treino/validação/teste: {len(train_val)}/{len(validation)}/{len(test)} combinações únicas.\n- Generalização independente: {len(generalization)} entradas.\n- Accuracy no teste: {selected_test['accuracy']:.4f}.\n- F1 Macro no teste: {selected_test['f1_macro']:.4f}.\n- Recall crítico no teste: {selected_test['classification'].get('critico', {}).get('recall', 0):.4f}.\n\nOs rótulos são derivados das regras da prova de conceito.\n", encoding="utf-8")
    print(json.dumps({"selected": choice, "test": selected_test, "generalization": generalization_metrics}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
