# Configurar a nuvem

O firmware classifica na placa e envia a leitura atual a cada 10 segundos por HTTPS. O painel consulta o histórico a cada 10 segundos. Não depende de serial nem de um computador ligado. O banco registra a hora de recebimento em UTC. O painel converte para o horário local.

## 1. Criar a tabela

No projeto Supabase, abra **SQL Editor → New query**, cole o conteúdo de `supabase/migrations/202610030001_readings.sql` e clique **Run**. O script pode ser repetido.

Este projeto de demonstração permite leitura pública das medições de `pico-01` para quem tem acesso à URL e à chave pública. Escritas públicas são bloqueadas por RLS e permissões; somente a API de ingestão grava dados. Para uso privado, configure login e substitua a política de leitura pública por uma política por usuário.

## 2. Configurar a credencial do Pico

Abra o arquivo local `.secrets/device.env`: ele contém `PICO_DEVICE_TOKEN=...`.

No Supabase, em **Edge Functions → Secrets**, adicione:

- Nome: `PICO_DEVICE_TOKEN`
- Valor: apenas o texto depois do `=` no arquivo.

Esse valor já foi configurado no `tinyml_ambiente/firmware/secrets.h` local. Ambos os arquivos são ignorados pelo Git. `SUPABASE_URL` e `SUPABASE_SERVICE_ROLE_KEY` são variáveis padrão do ambiente de Edge Functions, utilizadas somente no servidor; não coloque a chave administrativa na placa ou no React.

Para outro checkout, copie `secrets.example.h` para `secrets.h`, preencha Wi-Fi, URL da função e gere um token aleatório de pelo menos 32 caracteres. Configure o mesmo token nos Secrets da função.

## 3. Publicar a API

1. Abra **Edge Functions → Deploy a new function → Via Editor**.
2. Nomeie a função **`ingest-reading`**.
3. Substitua o conteúdo de `index.ts` pelo arquivo `supabase/functions/ingest-reading/index.ts` deste projeto.
4. Clique **Deploy function**.
5. Nas configurações da função, desative **Verify JWT / Enforce JWT verification**. A função usa sua própria autenticação por `x-device-token`; o token do Pico não é um JWT do Supabase.

Endpoint: `https://qvfzhuejfmkmtjlfckru.supabase.co/functions/v1/ingest-reading`.

Teste no painel com método POST, header `x-device-token` contendo o token local, `Content-Type: application/json` e body:

```json
{"temperatura_c":27,"umidade_pct":65,"presenca":0,"classe":"normal","classifier":"tree"}
```

O sucesso retorna HTTP 201 e `{"ok":true}`. Esse teste insere uma leitura no banco.

## 4. Gravar e visualizar

O firmware Wi-Fi preparado para este computador fica em `.secrets/pico_wifi.uf2` e contém suas credenciais; não publique esse arquivo.

Segure **BOOTSEL** ao conectar o Pico W e copie esse UF2 para a unidade **RPI-RP2**. Gravar substitui o firmware instalado. O código usa DHT11 GP2, IR GP14, LED GP16 e buzzer GP17.

Após reiniciar, alimente a placa normalmente por USB, sem BOOTSEL. Ela conecta ao Wi-Fi, sincroniza a hora por NTP e começa a enviar leituras válidas quando a nuvem estiver configurada. No painel React, selecione **Nuvem · Supabase** no seletor de fonte dos dados.

Para recompilar:

```powershell
python -m platformio run -d tinyml_ambiente/firmware -e picow_cloud
```

Saída: `tinyml_ambiente/firmware/.pio/build/picow_cloud/firmware.uf2`. O ambiente `picow_cloud_rules` aplica regras exatas, em vez da árvore.

## Comportamento e limites

- Leituras e atuadores continuam sem Wi-Fi. As requisições HTTPS podem atrasar o próximo ciclo; o timeout de resposta é 4 segundos.
- Reconexão Wi-Fi é tentada a cada 30 segundos. Os dados coletados offline não são armazenados nem reenviados.
- NTP e certificado válido são necessários para HTTPS. A raiz GTS Root R4 foi obtida de `https://pki.goog/repo/certs/gtsr4.pem`. Se a cadeia de certificados do serviço mudar, atualize a raiz e recompile.
- `CLOUD_HTTP=201` na serial é sucesso; `401` indica token incorreto, `404` função inexistente, `503` configuração ausente e `502` falha de gravação. A serial é opcional e serve apenas para diagnóstico.
- O painel mostra a hora da última leitura recebida; histórico disponível não significa que a placa continua online.
- Sem os passos no Supabase e a gravação física, ainda não há fluxo completo de ponta a ponta.

Referências: [Editor de Edge Functions](https://supabase.com/docs/guides/functions/quickstart-dashboard), [Secrets](https://supabase.com/docs/guides/functions/secrets), [autenticação de funções](https://supabase.com/docs/guides/functions/auth).
