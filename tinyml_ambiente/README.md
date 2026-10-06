# TinyML de monitoramento ambiental — Pico W

Pipeline executado com a planilha original e as regras fornecidas pelo usuário. Modelo escolhido: **Decision Tree**, profundidade 4, 17 nós. O modelo é uma aproximação das regras, não uma descoberta de classes reais. Para operação que deva respeitar exatamente os limites informados, use a alternativa de regras em C++ incluída no firmware.

## Executar no computador

Abra o terminal na pasta `tinyml_ambiente`. Ambiente validado: Python 3.14, NumPy 2.5.1, pandas 3.0.3, scikit-learn 1.9.0 e openpyxl 3.1.5. As versões estão fixadas em `requirements.txt`.

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe training/preprocessing.py
.venv\Scripts\python.exe training/train.py --rules data/rules.json
.venv\Scripts\python.exe training/evaluate.py
```

Os caminhos padrão são relativos à pasta do projeto. `--data caminho.xlsx` ou `--data caminho.csv` altera a fonte. O treinamento é determinístico com seed 42. Alterar dependências pode modificar resultados. Não carregue pickle de fontes desconhecidas.

## Dados e limpeza

A planilha tem uma coluna `Unnamed: 0` contendo texto do console: `MPY: soft reboot`, cabeçalho `temperatura,umidade,ir` e 235 medições. O parser extrai esse CSV e descarta a mensagem de reinicialização. Também aceita Excel/CSV tabular, normaliza nomes equivalentes e converte valores numéricos.

- 235 medições válidas; nenhuma medição ausente ou fora dos limites de limpeza.
- 156 repetições de features; 79 combinações únicas após deduplicação.
- Temperatura: mínimo 24, máximo 33, média 27,20 °C.
- Umidade: mínimo 51, máximo 98, média 67,20%.
- Presença: 23 medições presentes e 212 ausentes.

Limites de limpeza: temperatura finita em [0,50] °C, umidade finita em [0,100]%, IR/presença binários. São limites de admissibilidade dos dados; não são os limiares de alerta. Linhas inválidas são removidas e contabilizadas. Se IR e presença coexistirem, devem ser consistentes; inconsistências interrompem o pipeline. Relatórios completos: `reports/data_audit.json` e `reports/training.json`. Dados limpos: `data/clean.csv`.

Entradas, nesta ordem: `temperatura_c`, `umidade_pct`, `presenca`. `IR=0` vira `presenca=1`; `IR=1` vira `presenca=0`. Preferimos a coluna presença quando disponível. IR bruto não entra como quarta feature.

## Classes sintéticas

`data/rules.json` preserva as prioridades informadas: a primeira regra satisfeita vence.

1. `critico`: temperatura >=35 OU umidade >=90 OU (presença e temperatura >=32) OU (presença e umidade >=85).
2. `alerta`: temperatura >=30 OU umidade >=80.
3. `presenca`: presença detectada, sem condição anterior.
4. `normal`: demais casos.

Nos registros originais: normal=135, crítico=50, alerta=45, presença=5. Nas combinações únicas: alerta=31, crítico=24, normal=21, presença=3. Isso limita muito a avaliação de presença.

Nenhuma saída, nome da classe ou variável derivada da saída é entrada. As classes são explicitamente derivadas das próprias medições por escolha do usuário: o problema é imitação de regras. Assim, **não é possível demonstrar aprendizado além dessas regras com este dataset**. Para aprender estados ambientais reais, será necessário coletar rótulos independentes, por exemplo situações observadas e anotadas.

## Comparação e separação

Deduplicamos antes da separação para impedir que a mesma combinação apareça em treino e teste. Split estratificado fixo: 59 amostras únicas para treino e 20 para teste. Dentro do treino, validação cruzada estratificada de 2 folds, limitada pelas duas amostras de presença disponíveis. Normalização de Logistic Regression e MLP ocorre dentro de cada fold através de `Pipeline`; a árvore e o forest usam unidades físicas sem escalonamento. A seleção usa somente validação do treino; o holdout é avaliado depois da escolha, sem retreinar com ele.

Sem timestamps ou identificador de sessão, este split não elimina correlação temporal entre medições próximas e não demonstra desempenho em outra sala/sessão. Para isso, colete novas sessões e reserve uma sessão inteira para teste.

Médias dos folds de validação (tamanhos pickle são dos estimadores, sem o envelope de metadados):

| Modelo | Accuracy | Precision macro | Recall macro | F1 macro | Pickle (bytes) | Dados numéricos estimados (bytes) |
|---|---:|---:|---:|---:|---:|---:|
| Logistic Regression | 0,7282 | 0,6388 | 0,6845 | 0,6132 | 1256 | 88 |
| Decision Tree | 0,8644 | 0,7339 | 0,7838 | 0,7280 | 2750 | 272 |
| Random Forest (32 árvores) | 0,8126 | 0,7558 | 0,8677 | 0,7564 | 53341 | 7008 |
| MLP (8,4) | 0,9155 | 0,6919 | 0,7143 | 0,7014 | 36478 | 376 |
| Constante (baseline) | 0,3897 | 0,0974 | 0,2500 | 0,1402 | 483 | 4 |

Os números de bytes numéricos usam float32 e representações compactas teóricas (árvores: 16 bytes/nó); excluem código, strings, runtime e workspace. Pickle não estima RAM/flash embarcada. Cada modelo tem matriz de confusão e precision/recall/F1 por classe obtidos de previsões fora do fold em `reports/training.json`. Avisos de classe nunca prevista são preservados no relatório.

A árvore é escolhida quando seu F1 macro fica até 0,03 abaixo do melhor candidato. O forest supera a árvore em apenas 0,0285, com 32 árvores e 438 nós. A árvore usa até 4 comparações por inferência. Logistic Regression exige escalonamento e produtos escalares; o MLP tem 88 parâmetros, 72 multiplicações de pesos e ativações por inferência, além do escalonamento. São comparações de custo estrutural, não benchmarks de latência no hardware. Se outro dataset selecionar um modelo diferente de árvore, o script informa que a exportação embarcada adicional é necessária e remove o header anterior.

Teste reservado da árvore: accuracy, precision macro, recall macro e F1 macro = 1,0 em 20 medições únicas. Matriz (linhas reais, colunas previstas; ordem alerta, crítico, normal, presença):

```text
8 0 0 0
0 6 0 0
0 0 5 0
0 0 0 1
```

Há apenas uma amostra de presença no teste. O acerto de 100% nesse conjunto pequeno não comprova generalização.

## Exportação e equivalência

`models/model.pkl` contém estimador, nomes de features/classes e regras; `models/holdout.npz` preserva treino e teste para avaliação reproduzível. `models/model_data.h` contém a árvore real exportada em C++, com 1173 bytes de código-fonte UTF-8. Esse tamanho **não é o tamanho do binário**. `models/rules_data.h` contém a alternativa determinística, gerada das mesmas regras do treinamento.

O pacote `model.pkl` completo ocupa 3343 bytes no computador. A compilação real do firmware da árvore para Pico W foi concluída: **301480 bytes de flash (14,4%) e 69152 bytes de RAM estática (26,4%)** no orçamento informado pelo PlatformIO. Esses valores incluem core Arduino, sensores, serial e atuadores; não são apenas o modelo. RAM dinâmica e stack devem ser observadas no teste físico.

O modelo usa float32 em unidades físicas e nenhum escalonamento. O firmware faz o mesmo, incluindo inversão do IR e rejeição de leituras inválidas. Limiares da árvore são exportados com precisão completa e comparados como double para preservar a comparação do sklearn com entradas float32.

Para verificar o código C++ realmente compilado, use um compilador disponível:

```powershell
python training/verify_export.py --compiler g++
```

Nesta execução foi usado Zig 0.13.0, instalado localmente para validação:

```powershell
python -m pip install ziglang==0.13.0 --target .tools
python training/verify_export.py --compiler .tools/ziglang/zig.exe --zig
```

Resultado registrado em `reports/export_verification.json`: 13.224 entradas, incluindo grade inteira [0,50] × [0,100] × {0,1} e valores imediatamente ao redor de limiares; nenhuma divergência entre C++ e sklearn, nenhuma divergência entre regras C++ e Python e quatro casos inválidos rejeitados.

A árvore divergiu das regras em 3101 desses casos (23,45%). A grade inclui regiões não representadas na coleta e não deve ser interpretada como accuracy real. Exemplo relevante: sem presença, temperatura=35 e umidade=60 resulta em `alerta` pela árvore, mas `critico` pelas regras. Não houve coleta de temperatura >=35; uma árvore não consegue inferir um limiar ausente. **Para aplicar exatamente a política fornecida, use as regras diretas.**

Não há `.tflite` nem INT8: a MLP não foi selecionada. A exportação C++ evita TensorFlow Lite Micro, tensor arena e bibliotecas ML. O RP2040 dispõe de 264 kB de SRAM e o Pico W de 2 MB de flash; a árvore de 17 nós é estruturalmente pequena para esse hardware. O orçamento completo depende também do firmware e bibliotecas, e o resumo da compilação deve ser consultado antes de gravar.

## Firmware

`firmware/main.cpp` é um projeto Arduino-Pico em C++, com configuração PlatformIO. Ele lê DHT11 a cada 2 segundos, converte IR ativo em nível baixo, executa inferência, imprime classe na serial a 115200, acende LED e gera tom de 2 kHz no buzzer para `alerta`/`critico`. Leituras inválidas suspendem inferência, desligam atuadores e imprimem erro.

Pinagem da montagem física validada (numeração GPIO):

| Componente | GPIO |
|---|---:|
| DHT11 DATA | 2 |
| IR OUT | 14 |
| LED externo | 16 |
| Buzzer | 17 |

Use LED com resistor, GND comum e sinais GPIO compatíveis com 3,3 V. O exemplo usa buzzer passivo; para buzzer ativo, troque `tone/noTone` por nível lógico e use estágio de acionamento se necessário. Este código substitui o firmware MicroPython ao ser gravado; o ambiente `.micropico` original não foi alterado. Nenhuma gravação automática na placa é feita.

```powershell
python -m pip install platformio==6.2.0
python -m platformio run -d firmware -e picow
python -m platformio run -d firmware -e picow --target upload
python -m platformio device monitor --baud 115200
```

Para operar pelas regras exatas, selecione o ambiente já configurado:

```powershell
python -m platformio run -d firmware -e picow_rules
python -m platformio run -d firmware -e picow_rules --target upload
```

O ambiente `picow` executa a árvore; `picow_rules` define `USE_EXACT_RULES=1`. A plataforma está fixada no commit `5d4561a05e3b212660ac6fdd3fbfb328d1988aa1`; core usado: `fd65f6d4ab168d4bb181a3709738fe353ac93585`. Os artefatos de build ficam em `firmware/.pio/build/<ambiente>/`. Sensor, serial, LED e buzzer precisam de teste físico; verificação do C++ no computador não valida a ligação elétrica.

Ambos os ambientes compilaram com sucesso. Foram incluídos `firmware/dist/tinyml_tree.uf2` e `firmware/dist/exact_rules.uf2`. A versão de regras usa 301528 bytes de flash e 69152 bytes de RAM estática. O `tinyml_tree.uf2` foi recompilado com a pinagem validada acima: GP2 (DHT11), GP14 (IR), GP16 (LED) e GP17 (buzzer). O `exact_rules.uf2` não foi recompilado nesta correção e mantém a pinagem anterior. Tamanhos e SHA256 da compilação original estão em `reports/firmware_build.json`; o relatório não foi atualizado nesta correção. O tamanho UF2 inclui encapsulamento e difere da ocupação de flash.

Para gravar um UF2 já compilado: confira primeiro os GPIOs da montagem validada, segure BOOTSEL ao conectar o Pico W por USB e copie **um** dos arquivos UF2 para a unidade RPI-RP2. A placa reinicia com o firmware escolhido. Para outra ligação de pinos, altere `main.cpp` e recompile. Gravar C++ substitui a instalação MicroPython e seus arquivos na placa; preserve o que precisar antes de gravar. Após novo treinamento, recompile os firmwares: os UF2 distribuídos correspondem ao modelo e às regras desta execução.

## Recomendação

Para o experimento TinyML, use **Decision Tree exportada em C++**: melhor equilíbrio de F1 macro, transparência, tamanho e inferência simples; a MLP não teve vantagem em macro F1. Para operação com os limites atuais, use **as regras exatas** já incluídas. Colete mais presença, casos próximos aos limiares e sessões independentes antes de confiar no modelo fora desta coleta.

Referências: [RP2040/Pico](https://www.raspberrypi.com/products/raspberry-pi-pico/), [Pico W](https://datasheets.raspberrypi.com/picow/pico-w-datasheet.pdf), [integração oficial Arduino-Pico com PlatformIO](https://arduino-pico.readthedocs.io/en/latest/platformio.html), [biblioteca DHT da Adafruit](https://github.com/adafruit/DHT-sensor-library).
## Evolução reproduzível

O dataset original permanece em `data/dataset.xlsx` e `data/clean.csv`. A versão expandida é gerada deterministically em `data/dataset_expanded.csv` por `training/generate_dataset.py`: 620 linhas, 235 reais e 385 sintéticas, balanceadas em 155 por classe e com 463 combinações únicas. A coluna `origem` identifica a procedência. Dados sintéticos ampliam a cobertura, mas não substituem medições reais.

Execute o fluxo completo a partir desta pasta:

```powershell
python training/pipeline.py
```

O pipeline gera dataset, modelo, headers C++, métricas por classe, matriz de confusão, comparação regras×modelo em 20 mil entradas e relatórios em `reports/`. Para verificar a equivalência C++ com um compilador disponível, use `python training/pipeline.py --compiler g++`.

O firmware mantém as últimas 10 leituras em arrays fixos, calcula média e tendência e transmite JSON por linha a 115200 baud. Entradas fora de temperatura [20, 39,8] °C ou umidade [40, 98] % são marcadas como `ood: true` e classificadas pelas regras determinísticas. O ambiente PlatformIO `picow_benchmark` imprime média, mínimo, máximo de inferência e RAM livre a cada 10 leituras.

Limitações: os rótulos continuam derivados das regras fornecidas, parte importante do dataset é sintética, não há timestamps de sessão na coleta original, e o benchmark precisa ser observado fisicamente no hardware. O projeto continua sendo uma prova de conceito acadêmica de TinyML, não um sistema industrial validado.

## Avaliação metodológica atual

O dataset expandido agora possui 1.000 registros, 844 combinações únicas, 235 registros `real` e 765 `sintetico`, distribuídos em 250 exemplos por classe. As 156 duplicatas de combinação presentes na coleta original são preservadas no arquivo bruto, mas removidas antes da separação treino/validação/teste. A divisão atual usa 70% treino, 15% validação e 15% teste, com validação cruzada estratificada de 5 folds no treino. O arquivo `data/processed/test_generalization.csv` contém 240 combinações não usadas no treinamento.

Foram retreinados Logistic Regression, Decision Tree, Random Forest, MLP e baseline. A árvore foi escolhida por F1 Macro, recall crítico, estabilidade e custo embarcado, não apenas por accuracy. O teste final da árvore apresentou accuracy de aproximadamente 99,2%, F1 Macro de 99,3% e recall crítico de 97,1%. O conjunto de generalização sintético apresentou 100%, mas esse resultado deve ser interpretado com cautela: seus rótulos também foram gerados pelas mesmas regras determinísticas.

Relatórios adicionais: `reports/dataset_analysis.md`, `reports/model_comparison.csv`, `reports/model_evaluation.md`, `reports/generalization_test.csv`, `reports/classification_report.csv`, `reports/tree_depth_sweep.csv`, `reports/confusion_matrix.png`, `reports/decision_regions_presence_0.png`, `reports/decision_regions_presence_1.png` e `reports/coverage_analysis.json`.
