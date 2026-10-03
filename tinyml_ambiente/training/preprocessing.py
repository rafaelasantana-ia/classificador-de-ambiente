"""Limpeza compartilhada; presença é sempre 1 - IR bruto."""
import io
import json
import unicodedata
from pathlib import Path
import numpy as np
import pandas as pd

FEATURES = ['temperatura_c', 'umidade_pct', 'presenca']

def normalize(name):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(name).lower().strip()) if not unicodedata.combining(c))

def load_data(path):
    path = Path(path)
    raw = pd.read_excel(path) if path.suffix.lower() == '.xlsx' else pd.read_csv(path)
    original_columns = list(raw.columns)
    discarded_log = 0
    if raw.shape[1] == 1:
        lines = raw.iloc[:, 0].dropna().astype(str).tolist()
        start = next((i for i, line in enumerate(lines) if 'temperatura' in normalize(line) and ',' in line), None)
        if start is None:
            raise ValueError('Cabeçalho CSV não encontrado no log.')
        discarded_log = start
        raw = pd.read_csv(io.StringIO('\n'.join(lines[start:])), on_bad_lines='error')
    aliases = {'temperatura':'temperatura_c', 'temperature':'temperatura_c', 'temp':'temperatura_c',
               'umidade':'umidade_pct', 'humidity':'umidade_pct', 'ir':'ir', 'sensor_ir':'ir', 'presenca':'presenca'}
    raw = raw.rename(columns={c: aliases.get(normalize(c), normalize(c)) for c in raw})
    if raw.columns.duplicated().any():
        raise ValueError('Colunas equivalentes duplicadas.')
    for c in ['temperatura_c', 'umidade_pct']:
        if c not in raw: raise ValueError(f'Coluna ausente: {c}')
    if 'presenca' not in raw and 'ir' not in raw:
        raise ValueError('É necessário IR ou presença.')
    for c in FEATURES + ['ir']:
        if c in raw: raw[c] = pd.to_numeric(raw[c], errors='coerce')
    if 'presenca' not in raw: raw['presenca'] = 1 - raw['ir']
    valid = (raw.temperatura_c.between(0, 50) & raw.umidade_pct.between(0, 100)
             & raw.presenca.isin([0, 1]))
    if 'ir' in raw:
        valid &= raw.ir.isin([0, 1])
        if ((raw.presenca != 1 - raw.ir) & valid).any():
            raise ValueError('IR e presença discordam; corrija a fonte.')
    clean = raw.loc[valid, FEATURES].astype(np.float32).copy()
    report = {'original_columns': original_columns, 'source_columns': list(raw.columns), 'measurements': len(raw), 'discarded_log_lines': discarded_log,
              'invalid_rows': int((~valid).sum()), 'valid_rows': len(clean),
              'duplicate_features': int(clean.duplicated().sum()), 'unique_features': len(clean.drop_duplicates()),
              'statistics': clean.describe().to_dict(), 'presence_counts': clean.presenca.value_counts().to_dict()}
    return clean, report

def label_rules(data, path):
    """JSON ordenado: primeira regra satisfeita vence; sem eval de código."""
    rules = json.loads(Path(path).read_text(encoding='utf-8'))
    if not rules.get('rules') or 'default' not in rules: raise ValueError('Informe rules e default.')
    labels = pd.Series(str(rules['default']), index=data.index)
    assigned = pd.Series(False, index=data.index)
    operations = {'ge':lambda a,b:a>=b, 'gt':lambda a,b:a>b, 'le':lambda a,b:a<=b,
                  'lt':lambda a,b:a<b, 'eq':lambda a,b:a==b}
    for rule in rules['rules']:
        mode = rule.get('mode', 'any')
        if mode not in ['any', 'all']: raise ValueError('mode deve ser any ou all.')
        conditions = []
        for condition in rule['conditions']:
            f, op, value = condition
            if f not in FEATURES or op not in operations: raise ValueError('Condição inválida.')
            conditions.append(operations[op](data[f], float(value)))
        if not conditions: raise ValueError('Regra sem condições.')
        mask = pd.concat(conditions, axis=1)
        mask = mask.any(axis=1) if mode == 'any' else mask.all(axis=1)
        labels.loc[mask & ~assigned] = str(rule['class'])
        assigned |= mask
    return labels, rules

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', default='data/dataset.xlsx')
    args = parser.parse_args()
    data, report = load_data(args.data)
    Path('reports').mkdir(exist_ok=True)
    data.to_csv('data/clean.csv', index=False)
    Path('reports/data_audit.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(report, indent=2, ensure_ascii=False))
