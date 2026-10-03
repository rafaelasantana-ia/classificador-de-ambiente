# Ambiente — interface React

Na pasta `tinyml_ambiente/web`, execute:

```powershell
npm install
npm run dev
```

Abra http://127.0.0.1:5173. Para compilar: `npm run build`; para visualizar a compilação: `npm run preview`. Verificações da classificação e parser serial: `npm test`.

A visão geral carrega as 235 medições reais de `data/clean.csv`, oferece reprodução a cada dois segundos, gráficos, filtros e exportação CSV. O eixo horizontal é a ordem de aquisição: os registros não têm timestamps. A reprodução é uma visualização da coleta, não uma conexão com o hardware.

O simulador implementa a árvore de `models/model_data.h` com entradas float32 e compara seu resultado com `data/rules.json`. A página do modelo exibe as métricas do relatório de treinamento.

## Leituras da placa

Use Chrome ou Edge no computador e abra a aplicação em localhost ou HTTPS. Conecte o Pico W via USB, feche outros monitores seriais e clique em **Conectar Pico W**. Selecione a porta na janela do navegador. A conexão usa 115200 baud e interpreta a saída atual do firmware:

```text
T=24.0 U=70.0 IR=0 presenca=1 classe=presenca
```

Diagnósticos são ignorados; erros de sensor geram um aviso. A tela preserva a última leitura válida. O painel mantém até 1000 leituras USB em memória; exporte antes de recarregar. Não envia comandos nem altera o firmware. A classe TinyML no modo USB é a classe informada pelo firmware (também pode ser a saída de regras se a placa usar `picow_rules`).

## Atualizar a coleta e o treinamento

Os dados são cópias locais para permitir uma aplicação estática. Após executar novamente o pipeline, copie `data/clean.csv`, `data/rules.json` e `reports/training.json` para `web/src/data/` e recompile. Se a árvore for retreinada, atualize `tree()` em `src/model.js` conforme o novo `models/model_data.h`. A árvore atual tem 17 nós e profundidade 4.

A interface usa Google Fonts com fontes locais de fallback. Nenhum dado de sensor é enviado a um servidor.
