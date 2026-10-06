# Análise do dataset

- Original: 235 registros.
- Expandido: 1000 registros.
- Generalização independente: 240 registros.
- Combinações únicas: 844.
- Duplicatas de combinação removidas no treinamento: 156.
- Classes: {'normal': 250, 'presenca': 250, 'alerta': 250, 'critico': 250}.
- Origens: {'sintetico': 765, 'real': 235}.
- Temperatura: [20.0, 40.0] °C; umidade: [40.3, 98.0] %.

Os dados sintéticos são identificados por `origem=sintetico`. Os rótulos são derivados das regras determinísticas da prova de conceito.
