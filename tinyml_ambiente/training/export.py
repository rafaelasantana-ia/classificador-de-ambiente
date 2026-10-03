"""Exporta árvore sem normalização para inferência sem bibliotecas ML."""
import json
import numpy as np

def export_tree(model, classes, path):
    tree = model.tree_
    lines = ['#pragma once', '#include <math.h>', '// Ordem: temperatura C, umidade %, presenca (1 = presente).',
             f'constexpr int MODEL_CLASS_COUNT = {len(classes)};',
             'static const char* const MODEL_CLASSES[] = {' + ','.join(json.dumps(str(c), ensure_ascii=True) for c in classes) + '};',
             'inline int model_predict(float temperatura, float umidade, float presenca) {',
             '  const float x[3] = {temperatura, umidade, presenca};',
             '  if (!isfinite(temperatura) || !isfinite(umidade) || temperatura < 0 || temperatura > 50 || umidade < 0 || umidade > 100 || (presenca != 0 && presenca != 1)) return -1;']
    def visit(node, depth):
        indent = '  ' * depth
        if tree.children_left[node] < 0:
            lines.append(f'{indent}return {np.argmax(tree.value[node][0])};')
        else:
            # Double threshold preserves sklearn's float32-input comparison exactly.
            lines.append(f'{indent}if ((double)x[{tree.feature[node]}] <= {tree.threshold[node]:.17g}) {{')
            visit(tree.children_left[node], depth+1)
            lines.append(indent + '} else {')
            visit(tree.children_right[node], depth+1)
            lines.append(indent + '}')
    visit(0, 1)
    lines.append('}')
    path.write_text('\n'.join(lines)+'\n', encoding='utf-8')

def export_rules(rules, classes, path):
    operators = {'ge':'>=', 'gt':'>', 'le':'<=', 'lt':'<', 'eq':'=='}
    features = {'temperatura_c':'temperatura', 'umidade_pct':'umidade', 'presenca':'presenca'}
    lines = ['#pragma once', '// Inclua model_data.h antes deste arquivo.',
             'inline int rules_predict(float temperatura, float umidade, float presenca) {',
             '  if (!isfinite(temperatura) || !isfinite(umidade) || temperatura < 0 || temperatura > 50 || umidade < 0 || umidade > 100 || (presenca != 0 && presenca != 1)) return -1;']
    for rule in rules['rules']:
        op = ' || ' if rule.get('mode','any') == 'any' else ' && '
        condition = op.join(f'({features[f]} {operators[o]} {float(v):.17g})' for f,o,v in rule['conditions'])
        lines.append(f'  if ({condition}) return {list(classes).index(rule["class"])};')
    lines += [f'  return {list(classes).index(rules["default"])};', '}']
    path.write_text('\n'.join(lines)+'\n', encoding='utf-8')
