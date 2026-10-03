"""Comparação via CV no treino; teste reservado até a escolha final."""
import argparse
import json
import pickle
import warnings
import hashlib
import platform
from importlib.metadata import version
from pathlib import Path
import numpy as np
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_validate, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.dummy import DummyClassifier
from sklearn.metrics import classification_report, confusion_matrix
from preprocessing import FEATURES, load_data, label_rules
from export import export_tree, export_rules

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', default='data/dataset.xlsx')
    parser.add_argument('--rules', required=True, help='Regras sintéticas fornecidas pelo usuário.')
    args = parser.parse_args()
    np.random.seed(42)
    data, audit = load_data(args.data)
    labels, rules = label_rules(data, args.rules)
    audit['classes_all_measurements'] = labels.value_counts().to_dict()
    # Repetições das mesmas features nunca aparecem em ambos os conjuntos.
    data = data.drop_duplicates().reset_index(drop=True)
    labels, _ = label_rules(data, args.rules)
    encoder = LabelEncoder().fit(labels)
    y = encoder.transform(labels)
    counts = np.bincount(y)
    if len(counts) < 2 or counts.min() < 3:
        raise ValueError(f'Necessárias >=2 classes e >=3 medições únicas por classe; contagens: {dict(zip(encoder.classes_, counts.tolist()))}')
    test_n = max(len(counts), int(np.ceil(len(y)*0.25)))
    if len(y)-test_n < 2*len(counts): raise ValueError('Poucas medições únicas para treino/teste.')
    train, test = train_test_split(np.arange(len(y)), test_size=test_n, random_state=42, stratify=y)
    X = data[FEATURES].to_numpy(dtype=np.float32)
    folds = min(5, int(np.bincount(y[train]).min()))
    if folds < 2: raise ValueError('Poucas amostras no treino para CV.')
    cv = StratifiedKFold(folds, shuffle=True, random_state=42)
    candidates = {
        'logistic':make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, class_weight='balanced', random_state=42)),
        'tree':DecisionTreeClassifier(max_depth=4, min_samples_leaf=2, class_weight='balanced', random_state=42),
        'forest':RandomForestClassifier(n_estimators=32, max_depth=4, min_samples_leaf=2, class_weight='balanced', random_state=42),
        'mlp':make_pipeline(StandardScaler(), MLPClassifier(hidden_layer_sizes=(8,4), max_iter=3000, random_state=42)),
        'dummy':DummyClassifier(strategy='most_frequent')}
    results = {}
    scoring = {'accuracy':'accuracy', 'precision_macro':'precision_macro', 'recall_macro':'recall_macro', 'f1_macro':'f1_macro'}
    for name, model in candidates.items():
        with warnings.catch_warnings(record=True) as caught:
            score = cross_validate(model, X[train], y[train], cv=cv, scoring=scoring, error_score='raise')
            model.fit(X[train], y[train])
            oof = cross_val_predict(model, X[train], y[train], cv=cv)
        results[name] = {k:float(np.mean(score['test_'+k])) for k in scoring}
        results[name]['warnings'] = sorted(set(str(w.message) for w in caught))
        results[name]['pickle_bytes'] = len(pickle.dumps(model))
        results[name]['cv_classification'] = classification_report(y[train], oof, labels=np.arange(len(counts)), target_names=encoder.classes_, output_dict=True, zero_division=0)
        results[name]['cv_confusion_matrix'] = confusion_matrix(y[train], oof, labels=np.arange(len(counts))).tolist()
        estimator = model.steps[-1][1] if hasattr(model, 'steps') else model
        if name == 'tree':
            results[name]['nodes'] = estimator.tree_.node_count
            results[name]['estimated_numeric_bytes'] = estimator.tree_.node_count * 16
        elif name == 'forest':
            nodes = sum(t.tree_.node_count for t in estimator.estimators_)
            results[name]['nodes'] = nodes
            results[name]['estimated_numeric_bytes'] = nodes * 16
        elif name == 'mlp':
            results[name]['parameters'] = sum(a.size for a in estimator.coefs_ + estimator.intercepts_)
            results[name]['estimated_numeric_bytes'] = 4 * results[name]['parameters'] + 24
        elif name == 'logistic':
            results[name]['estimated_numeric_bytes'] = 4 * (estimator.coef_.size + estimator.intercept_.size) + 24
        else: results[name]['estimated_numeric_bytes'] = 4
        results[name]['deployment'] = {'logistic':'Escalonamento + produtos escalares; exportação adicional necessária.',
            'tree':f'C++ direto, <= {model.get_depth() if name=="tree" else 4} comparações por inferência.',
            'forest':'32 árvores; maior custo e exportação adicional necessária.',
            'mlp':'3x8 + 8x4 + 4xclasses MACs, escalonamento e ativações; conversão adicional necessária.',
            'dummy':'Classe constante; referência.'}[name]
    best = max((n for n in candidates if n!='dummy'), key=lambda n:results[n]['f1_macro'])
    choice = 'tree' if results['tree']['f1_macro'] >= results[best]['f1_macro']-0.03 else best
    model = candidates[choice]
    prediction = model.predict(X[test])
    for folder in ['models', 'reports']: Path(folder).mkdir(exist_ok=True)
    artifact = {'model':model, 'features':FEATURES, 'classes':encoder.classes_.tolist(), 'rules':rules,
                'choice':choice, 'synthetic_labels':True}
    Path('models/model.pkl').write_bytes(pickle.dumps(artifact))
    np.savez('models/holdout.npz', X=X[test], y=y[test], train_X=X[train], train_y=y[train])
    if choice == 'tree':
        export_tree(model, encoder.classes_, Path('models/model_data.h'))
        export_rules(rules, encoder.classes_, Path('models/rules_data.h'))
    else:
        Path('models/model_data.h').unlink(missing_ok=True)
        print('Modelo superior não é árvore: exportação embarcada ainda necessária; não use firmware como modelo final.')
    report = {'synthetic_labels':True, 'limitation':'Aprende regras fornecidas, não demonstra descoberta de estados ambientais.',
              'python':platform.python_version(),
              'dependencies':{name:version(name) for name in ['numpy','pandas','scikit-learn','openpyxl']},
              'data_sha256':hashlib.sha256(Path(args.data).read_bytes()).hexdigest(),
              'rules_sha256':hashlib.sha256(Path(args.rules).read_bytes()).hexdigest(),
              'data_audit':audit, 'cv':results, 'selected':choice, 'folds':folds,
              'train_unique':len(train), 'test_unique':len(test),
              'holdout':classification_report(y[test], prediction, labels=np.arange(len(counts)), target_names=encoder.classes_, output_dict=True, zero_division=0),
              'confusion_matrix':confusion_matrix(y[test], prediction, labels=np.arange(len(counts))).tolist(),
              'split_warning':'Sem timestamps/sessões: split estratificado não mede generalização para novas sessões.',
              'header_bytes':Path('models/model_data.h').stat().st_size if choice=='tree' else None}
    Path('reports/training.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(report, indent=2, ensure_ascii=False))

if __name__ == '__main__': main()
