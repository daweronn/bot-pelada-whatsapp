# Deploy na VPS (Contabo + EasyPanel)

## Visão geral

```
WhatsApp  ──>  Evolution API  ──(webhook)──>  Bot da Pelada  ──(REST)──>  Evolution API  ──>  WhatsApp
                (container)                     (este container)
                                                     │
                                                     └── Postgres do Supabase Cloud
                                                         (schema `pelada.*`)
```

A Evolution e o bot rodam como serviços no EasyPanel, na mesma VPS. O banco é o
**Supabase Cloud** — o mesmo do resto do Clipou —, não roda na VPS.

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

## 2. Banco de dados

O bot usa o **Postgres do Supabase Cloud**, no schema `pelada.*`. Não há volume,
não há arquivo local, não há estado dentro do container — pode destruir e recriar
o serviço à vontade que nada se perde.

A conexão vem da env `DATABASE_URL` (string do **pooler** do Supabase). O pool é
aberto no boot do processo; `DATABASE_POOL_MAX` (default `5`) limita as conexões.

> As tabelas do schema `pelada.*` são criadas por migration no Supabase, não pelo
> bot. Ele assume que já existem.

---

## 3. Variáveis de ambiente (no painel do EasyPanel → Environment)

**Obrigatórias** — faltando qualquer uma, o processo não sobe (erro explícito no log):

| Variável | Exemplo | Observação |
|---|---|---|
| `DATABASE_URL` | `postgresql://postgres.<ref>:<senha>@aws-1-sa-east-1.pooler.supabase.com:6543/postgres` | string do pooler do Supabase |
| `EVOLUTION_BASE_URL` | `http://evolution:8080` | URL da Evolution. Se ela é outro serviço no mesmo projeto EasyPanel, use o **nome interno do serviço** (sem HTTPS). Senão, a URL pública. |
| `EVOLUTION_INSTANCE` | `pelada` | nome da sua instância |
| `EVOLUTION_API_KEY` | `xxxxx` | apikey global ou da instância |
| `WEBHOOK_TOKEN` | `umsegredo` | **protege o webhook — sem ele o endpoint aceitaria comando forjado de qualquer origem** |

**Opcionais:**

| Variável | Default | Observação |
|---|---|---|
| `DATABASE_POOL_MAX` | `5` | conexões simultâneas no pooler |
| `DEFAULT_OVERALL` | `5` | nota de quem entra na lista sem cadastro |
| `DEBUG_PAYLOAD` | desligado | `1` loga o payload cru da Evolution (contém telefone e texto das mensagens) |

### Quem é admin

Admin **não** é configurado por variável de ambiente e **não** é o admin do grupo
no WhatsApp. É uma linha na tabela `pelada.admins`, casando `grupo_id` com a
`identity_key` da pessoa (telefone canônico). Mandar do próprio número da
instância (`fromMe`) **não** dá permissão nenhuma.

Do mesmo modo, o bot só responde em grupo que exista em `pelada.grupos` com
`wa_group_jid` batendo e `ativo = true`. Grupo desconhecido: silêncio total. É
assim que um número atende várias arenas sem se misturar.

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

> A url **precisa** levar o token: `.../webhook?token=umsegredo`. Sem ele o bot
> responde 401 e ignora a mensagem.
> Se a sua Evolution estiver com `webhookByEvents` ligado, ela chama
> `.../webhook/messages-upsert` — o bot aceita os dois formatos.

---

## 5. Testar

1. `GET /` no domínio do bot → `{"status":"ok","instance":"<sua instância>"}`.
   Se o container está em restart loop, o log diz qual variável obrigatória faltou.
2. No grupo, mande `.ajuda` → o bot responde.
3. `.cadastro @fulano 8` (de um número que esteja em `pelada.admins`) → confirma o cadastro.
4. `.jogadores` → lista.

### Checklist se não responder
- A Evolution consegue **alcançar** a URL do bot? (teste o webhook)
- A URL do webhook está com `?token=` correto? (sem ele: 401 silencioso)
- O evento **MESSAGES_UPSERT** está habilitado?
- O grupo está em `pelada.grupos` com `ativo = true` e o `wa_group_jid` certo?
- Quem mandou o comando está em `pelada.admins` daquele grupo?
- `EVOLUTION_BASE_URL/INSTANCE/API_KEY` corretos? (o bot loga falha de envio)
- Mandou comando com o **ponto** na frente? (`.cadastro`, não `cadastro`)
