"""Compila o header real e compara C++/sklearn em uma grade e nas fronteiras."""
import argparse
import json
import pickle
from pathlib import Path
import subprocess
import tempfile
import numpy as np
import pandas as pd
from preprocessing import FEATURES, label_rules

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--compiler', default='g++')
    parser.add_argument('--zig', action='store_true')
    args = parser.parse_args()
    artifact = pickle.loads(Path('models/model.pkl').read_bytes())
    if artifact['choice'] != 'tree': raise ValueError('Verificação exige árvore exportada.')
    tree = artifact['model'].tree_
    temps = list(range(51)); hums = list(range(101))
    for f, value in zip(tree.feature, tree.threshold):
        if f not in [0, 1]: continue
        v = np.float32(value)
        target = temps if f == 0 else hums
        target.extend([np.nextafter(v, np.float32(-np.inf)), v, np.nextafter(v, np.float32(np.inf))])
    X = np.array([(t,h,p) for t in temps for h in hums for p in [0,1]], dtype=np.float32)
    expected = artifact['model'].predict(X)
    header = Path('models/model_data.h').resolve().as_posix()
    rules_header = Path('models/rules_data.h').resolve().as_posix()
    source = f'#include "{header}"\n#include "{rules_header}"\n#include <stdio.h>\nint main() {{ float t,h,p; while(scanf("%f %f %f", &t,&h,&p)==3) printf("%d %d\\n",model_predict(t,h,p),rules_predict(t,h,p)); }}\n'
    with tempfile.TemporaryDirectory() as temp:
        src = Path(temp)/'verify.cpp'; exe = Path(temp)/'verify.exe'
        src.write_text(source, encoding='utf-8')
        command = [str(Path(args.compiler).resolve())] if args.zig else [args.compiler]
        if args.zig: command += ['c++']
        subprocess.run(command + ['-O2', str(src), '-o', str(exe)], check=True)
        payload = '\n'.join(' '.join(format(float(v), '.9g') for v in row) for row in X)+'\n'
        output = subprocess.run([str(exe)], input=payload, text=True, capture_output=True, check=True)
        compiled = np.fromstring(output.stdout, sep=' ', dtype=int).reshape(-1, 2)
        actual = compiled[:, 0]
        assert np.array_equal(expected, actual), 'C++ diverge do sklearn.'
        invalid = subprocess.run([str(exe)], input='-1 50 0\n25 101 1\n25 50 2\nnan 50 0\n', text=True, capture_output=True, check=True)
        assert np.array_equal(np.fromstring(invalid.stdout, sep=' ', dtype=int), [-1]*8)
    rules_path = Path('reports/verification_rules.json')
    rules_path.write_text(json.dumps(artifact['rules']), encoding='utf-8')
    labels, _ = label_rules(pd.DataFrame(X, columns=FEATURES), rules_path)
    compiled_rule_names = np.array(artifact['classes'])[compiled[:, 1]]
    assert np.array_equal(compiled_rule_names, labels.to_numpy()), 'Regras C++ divergem do Python.'
    names = np.array(artifact['classes'])[expected]
    mismatches = np.flatnonzero(names != labels.to_numpy())
    report = {'cpp_sklearn_points':len(X), 'cpp_sklearn_mismatches':int(np.sum(actual != expected)),
              'cpp_rule_mismatches':int(np.sum(compiled_rule_names != labels.to_numpy())),
              'invalid_readings_rejected':4, 'rule_disagreements':len(mismatches),
              'rule_agreement_fraction':float(np.mean(names == labels.to_numpy())),
              'examples':[{'features':X[i].tolist(), 'model':names[i], 'rule':labels.iloc[i]} for i in mismatches[:8]],
              'scope':'Grade de inteiros DHT11 mais limiares da árvore; não é acurácia em dados reais.'}
    Path('reports/export_verification.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    rules_path.unlink()
    print(json.dumps(report, indent=2, ensure_ascii=False))

if __name__ == '__main__': main()
