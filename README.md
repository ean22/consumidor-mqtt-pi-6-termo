# consumidor-mqtt-pi-6-termo - Ponte MQTT para MongoDB

Script Python que assina um tópico de um broker MQTT remoto e grava cada mensagem em uma coleção MongoDB remota.

## Configuração

1. Crie um ambiente virtual e instale as dependências:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Copie `.env.example` para `.env` e preencha os endereços, tópico e credenciais reais. O arquivo `.env` está no `.gitignore`.

3. Inicie a ponte:

   ```bash
   python bridge.py
   ```

Para validar a conversão de payloads sem conectar aos serviços remotos:

```bash
python -m unittest discover -s tests -v
```

`MQTT_TLS=true` habilita TLS com validação do certificado do broker (normalmente usado na porta 8883). Para um broker sem TLS, use `MQTT_TLS=false` e a porta adequada. Não use credenciais reais no `.env.example`.

Mensagens UTF-8 são armazenadas com `topic`, `payload`, `payload_data`, `received_at`, `data`, `qos` e `retain`. O campo `payload_data` contém um objeto/valor JSON quando o conteúdo é JSON válido, ou uma string quando não é. O campo `data` registra a data e hora UTC imediatamente antes da inserção no MongoDB. Payloads binários são armazenados em `payload_base64`.

O script confirma a entrega MQTT após a inserção no MongoDB. Isso reduz perda de mensagens em caso de falha de gravação; como MQTT e MongoDB não compartilham uma transação, uma interrupção no instante da confirmação pode causar reentrega e documento duplicado.
