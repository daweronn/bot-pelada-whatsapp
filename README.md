# ⚽ Bot da Pelada (WhatsApp + Evolution API)

Bot pra gerenciar a pelada dentro do grupo de WhatsApp. **Fase 1 (atual): cadastro de jogadores com overall de 1 a 10.** Sorteio de times e votações vêm nas próximas fases.

## Comandos

| Comando | Quem pode | O que faz |
|---|---|---|
| `.cadastro @pessoa 8` | só admin | cadastra/atualiza jogador com nota 1–10 |
| `.cadastro 5511999999999 8 João` | só admin | mesmo, por número e com nome |
| `.remover @pessoa` | só admin | remove jogador |
| `.jogadores` | todos | lista os cadastrados (ordenado por overall) |
| `.ajuda` | todos | ajuda |

> A nota pode vir com traço também: `.cadastro @pessoa - 8`.
> O nome é opcional; se não passar, mantém o que já tinha (ou usa o número).

## Como rodar (Windows)

```powershell
cd C:\Programas\scripts-python\whatsapp-pelada-bot
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

copy .env.example .env   # depois edite o .env
```

Edite o `.env` com a URL/instância/apikey da sua Evolution e os `ADMIN_NUMBERS`
(números que podem cadastrar, só dígitos com DDI+DDD).

Suba o servidor:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Conectar na Evolution API

O bot é um **webhook**: a Evolution te avisa quando chega mensagem, o bot responde.

1. Sua Evolution precisa enxergar o servidor. Em dev, exponha a porta 8000 com
   um túnel (ex.: `ngrok http 8000`) e pegue a URL pública `https://...`.
2. Configure o webhook da instância apontando pra `https://SUA-URL/webhook`,
   habilitando o evento **MESSAGES_UPSERT**. Via API:

   ```bash
   curl -X POST "$EVOLUTION_BASE_URL/webhook/set/$INSTANCE" \
     -H "apikey: $API_KEY" -H "Content-Type: application/json" \
     -d '{
       "webhook": {
         "enabled": true,
         "url": "https://SUA-URL/webhook",
         "events": ["MESSAGES_UPSERT"]
       }
     }'
   ```

   > Em algumas versões da Evolution, ative `webhookByEvents`; aí a chamada vira
   > `https://SUA-URL/webhook/messages-upsert`. O servidor aceita os dois formatos.

3. (Opcional) Defina `WEBHOOK_TOKEN` no `.env` e adicione `?token=SEUTOKEN`
   na URL do webhook pra proteger o endpoint.

## Testar a lógica sem WhatsApp

```powershell
.\.venv\Scripts\python.exe -m tests.test_commands
```

## Estrutura

```
app/
  config.py     # variáveis de ambiente / admins
  db.py         # SQLite (repositório de jogadores)
  evolution.py  # envia mensagens via Evolution API
  messages.py   # interpreta o payload do webhook
  commands.py   # comandos (.cadastro, .remover, .jogadores, .ajuda)
  main.py       # servidor FastAPI (webhook)
tests/
  test_commands.py
```

## Próximas fases
- [ ] Sorteio de times equilibrado por overall
- [ ] Abrir votação (presença / melhor da pelada)
- [ ] Finalizar votação e mostrar resultado
