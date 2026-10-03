import json
import pickle
import numpy as np
from sklearn.metrics import classification_report, confusion_matrix

if __name__ == '__main__':
    # Carregue somente artefatos pickle locais confiáveis.
    with open('models/model.pkl', 'rb') as f: artifact = pickle.load(f)
    data = np.load('models/holdout.npz')
    assert not set(map(tuple, data['X'])) & set(map(tuple, data['train_X'])), 'Features repetidas entre treino/teste.'
    prediction = artifact['model'].predict(data['X'])
    classes = artifact['classes']
    print(classification_report(data['y'], prediction, labels=np.arange(len(classes)), target_names=classes, zero_division=0))
    print('Matriz (linhas=reais, colunas=previstas):')
    print(confusion_matrix(data['y'], prediction, labels=np.arange(len(classes))))
    print('Classes sintéticas:', artifact['synthetic_labels'])
