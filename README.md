# Classificador de ambiente

Projeto de monitoramento ambiental com Raspberry Pi Pico W, DHT11, sensor infravermelho e TinyML. Classifica as condições em **normal**, **presença**, **alerta** e **crítico**, com LED e buzzer como indicadores.

## Interface web em React

```powershell
cd tinyml_ambiente/web
npm install
npm run dev
```

Abra http://127.0.0.1:5173. O painel oferece gráficos da coleta expandida, reprodução, filtros, exportação CSV, comparação de modelos e um simulador da árvore e das regras exatas.

Para acompanhar a placa via USB, use Chrome ou Edge, feche outros monitores seriais, clique em **Conectar Pico W** e selecione a porta USB da placa. A conexão usa 115200 baud e a saída do firmware incluído.

```powershell
npm test
npm run build
```

Mais detalhes em [tinyml_ambiente/web/README.md](tinyml_ambiente/web/README.md).

## Firmware e treinamento

- `tinyml_ambiente/firmware/`: firmware C++ e configuração PlatformIO.
- `tinyml_ambiente/training/`: limpeza, treinamento, avaliação e verificação da exportação.
- `tinyml_ambiente/data/`: planilha original, dados limpos e regras.
- `tinyml_ambiente/models/`: modelo exportado e artefatos de avaliação.
- `tinyml_ambiente/reports/`: relatórios reproduzíveis do experimento.

Pinagem: DHT11 GP2, infravermelho GP14, LED GP16 e buzzer GP17.

O modelo selecionado é uma Decision Tree de profundidade 4 e 25 nós. As classes derivam de regras definidas; a árvore aproxima essas regras e pode divergir em condições pouco representadas na coleta. O teste reservado expandido contém 116 combinações únicas e não comprova generalização para novas sessões.

Consulte [a documentação técnica](tinyml_ambiente/README.md) antes de gravar os UF2: ela descreve a pinagem e as diferenças entre os binários distribuídos.
