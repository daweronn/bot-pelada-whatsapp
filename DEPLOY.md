# Deploy na VPS (Contabo + EasyPanel)

## Visão geral

```
WhatsApp  ──>  Evolution API  ──(webhook)──>  Bot da Pelada  ──(REST)──>  Evolution API  ──>  WhatsApp
                (container)                     (este container)
                                                     │
                                                     └── SQLite em volume /data  (persiste)
```

Os dois rodam como serviços no EasyPanel, na mesma VPS.

---

## 1. Subir o código

O EasyPanel builda a imagem a partir do **Dockerfile** que já está no projeto.
Duas opções:

- **GitHub (recomendado):** suba esta pasta para um repositório e, no EasyPanel,
  crie um serviço **App** → *Source: GitHub* → selecione o repo → *Build: Dockerfile*.
- **Sem GitHub:** crie o App com *Build: Dockerfile* e use o método de upload do
  EasyPanel (ou um repositório Git da própria VPS).

Porta interna do container: **8000** (o EasyPanel detecta pelo `EXPOSE`).

---

## 2. Banco de dados na VPS (sua pergunta)

O bot usa **SQLite**, que é um **arquivo** (`pelada.db`). Pra esse arquivo não
sumir quando o container reiniciar ou você fizer um redeploy, ele precisa ficar
num **Volume** (disco persistente do EasyPanel), não dentro do container.

No serviço do bot, em **Mounts → Add Mount → Volume**:

| Campo | Valor |
|---|---|
| Name | `pelada-data` |
| Mount path | `/data` |

E garanta a env `DB_PATH=/data/pelada.db` (já é o padrão do Dockerfile).

Resultado: o `pelada.db` vive no volume `pelada-data`. Redeploys, restarts e
atualizações **não apagam** os jogadores. Só apaga se você remover o volume.

> Backup: dá pra copiar o arquivo via terminal do EasyPanel
> (`docker cp <container>:/data/pelada.db ./`) ou snapshot da Contabo.
> SQLite aguenta tranquilo o volume de um grupo de pelada. (Se um dia precisar de
> várias réplicas do bot, aí sim trocaríamos por Postgres — não é o caso agora.)

---

## 3. Variáveis de ambiente (no painel do EasyPanel → Environment)

| Variável | Exemplo | Observação |
|---|---|---|
| `EVOLUTION_BASE_URL` | `http://evolution:8080` | URL da Evolution. Se ela é outro serviço no mesmo projeto EasyPanel, use o **nome interno do serviço** (sem HTTPS). Senão, a URL pública. |
| `EVOLUTION_INSTANCE` | `pelada` | nome da sua instância |
| `EVOLUTION_API_KEY` | `xxxxx` | apikey global ou da instância |
| `ADMIN_NUMBERS` | `5511888888888` | **o outro número** que pode cadastrar (DDI+DDD, só dígitos). Pode ter vários separados por vírgula. |
| `ALLOWED_GROUP_JID` | `12036...@g.us` | opcional: trava o bot num grupo só |
| `WEBHOOK_TOKEN` | `umsegredo` | opcional, protege o webhook |
| `DB_PATH` | `/data/pelada.db` | já default; deixe assim |

### Sobre os dois números

- **Número da instância** (o WhatsApp conectado na Evolution): cadastra
  automaticamente. Quando *você* digita `.cadastro ...` desse número, a Evolution
  manda como `fromMe` e o bot aceita. **Não precisa colocar em lugar nenhum.**
- **Outro número:** é só adicionar em `ADMIN_NUMBERS`. Esse não precisa ser admin
  do grupo nem nada — basta o número bater.

---

## 4. Apontar o webhook da Evolution para o bot

Descubra a URL do bot:
- **Domínio público** que o EasyPanel deu ao serviço: `https://bot.seudominio.com`
- **ou interno** (se Evolution e bot estão no mesmo projeto): `http://NOME-DO-SERVICO-DO-BOT:8000`

Configure o webhook na instância (evento **MESSAGES_UPSERT**):

```bash
curl -X POST "$EVOLUTION_BASE_URL/webhook/set/$EVOLUTION_INSTANCE" \
  -H "apikey: $EVOLUTION_API_KEY" -H "Content-Type: application/json" \
  -d '{
    "webhook": {
      "enabled": true,
      "url": "https://bot.seudominio.com/webhook",
      "events": ["MESSAGES_UPSERT"]
    }
  }'
```

> Se usou `WEBHOOK_TOKEN`, a url vira `.../webhook?token=umsegredo`.
> Se a sua Evolution estiver com `webhookByEvents` ligado, ela chama
> `.../webhook/messages-upsert` — o bot aceita os dois formatos.

---

## 5. Testar

1. Veja os logs do serviço no EasyPanel — deve aparecer
   `Banco inicializado em /data/pelada.db` e a lista de `Admins`.
2. No grupo, mande `.ajuda` → o bot responde.
3. `.cadastro @fulano 8` (do número da instância ou do admin) → confirma o cadastro.
4. `.jogadores` → lista.

### Checklist se não responder
- A Evolution consegue **alcançar** a URL do bot? (teste o webhook)
- O evento **MESSAGES_UPSERT** está habilitado?
- `EVOLUTION_BASE_URL/INSTANCE/API_KEY` corretos? (o bot loga falha de envio)
- Mandou comando com o **ponto** na frente? (`.cadastro`, não `cadastro`)
