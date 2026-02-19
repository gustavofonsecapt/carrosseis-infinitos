

## Roteiro role-aware com capacidade real do template

### Problema

O prompt atual envia constraints genéricas para a OpenAI sem distinguir quais slots cada role (cover/body/cta) realmente usa. Resultado: o cover recebe body/bullets, o CTA recebe texto longo, e os body slides nao adaptam entre bullets vs paragrafo conforme o template.

Alem disso, a familia `premium_editorial_v1` usa nomes de slot diferentes dos layouts classicos (ex: `title` em vez de `headline`, `cta_title` em vez de `headline` no CTA). O prompt precisa refletir isso.

---

### 1. Nova funcao: `derive_slot_capabilities` em `app/utils/slots.py`

Adicionar funcao que analisa um slot_schema e retorna feature flags:

```text
def derive_slot_capabilities(slot_schema) -> dict:
    slots = slot_schema.get("slots", {})
    return {
        "supports_title": "title" in slots or "headline" in slots,
        "supports_subtitle": "subtitle" in slots or "subhead" in slots,
        "supports_kicker": "kicker" in slots,
        "supports_body": "body" in slots,
        "supports_bullets": "bullets" in slots,
        "supports_cta_title": "cta_title" in slots,
        "supports_cta_body": "cta_body" in slots,
        "supports_cta_button": "cta_button" in slots,
        "supports_brand": "brand" in slots,
        "supports_number": "number" in slots,
        "supports_image": "image" in slots,
        "title_key": "title" if "title" in slots else "headline",
        "subtitle_key": "subtitle" if "subtitle" in slots else "subhead",
        "bullets_strategy": True if ("bullets" in slots and slots["bullets"].get("max_items", 0) >= 3) else False,
        "body_strategy": True if ("body" in slots and slots["body"].get("max_chars", 0) >= 100) else False,
    }
```

Tambem adicionar `build_role_schema` que gera a descricao de campos permitidos por role:

```text
def build_role_schema(role, caps, slot_schema) -> str:
    # Para cover: so title/subtitle/kicker/brand/number
    # Para body: title + (bullets OU body) + brand/number
    # Para cta: cta_title + cta_button + (cta_body se existir) + brand
```

---

### 2. Refatorar `_build_carousel_prompt` em `outline_service.py`

Mudancas:

- Usar `derive_slot_capabilities` para cada role (cover, body, cta)
- Gerar o JSON schema de exemplo **dinamicamente** com base nos slots reais
- Instruir explicitamente quais campos sao **proibidos** por role:

```text
COVER (slide 1):
  Campos OBRIGATORIOS: title (max 68), subtitle (max 90), brand (max 32)
  Campos OPCIONAIS: kicker (max 32), number (max 10)
  PROIBIDO: body, bullets, cta_title, cta_button, cta_body

BODY (slides 2-7):
  Campos OBRIGATORIOS: title (max 68)
  Estrategia: USE BULLETS (3-5 itens, max 48 chars/item) — o template e bullets-first
  Campos OPCIONAIS: brand, number
  PROIBIDO: cta_title, cta_button, cta_body, subtitle

CTA (slide 8):
  Campos OBRIGATORIOS: cta_title (max 50), cta_button (max 20)
  Campos OPCIONAIS: cta_body (max 180), brand
  PROIBIDO: body, bullets, subtitle, kicker
```

- O JSON de exemplo deve usar os nomes reais dos slots (title vs headline conforme a familia)

---

### 3. Refatorar `_build_stories_prompt`

Mesma logica:
- Frame 1: headline curto + brand (hook)
- Frames 2-9: headline + support (curtos)
- Frame 10 (CTA): headline + cta + trigger_word + brand

---

### 4. Atualizar `_parse_response` para limpar slots proibidos

Apos receber o JSON da OpenAI e antes do enforce_slot_limits, adicionar um passo de **sanitizacao por role**:

```text
def _strip_forbidden_slots(entry, role, caps):
    if role == "cover":
        for key in ["body", "bullets", "cta_title", "cta_button", "cta_body"]:
            entry.pop(key, None)
    elif role == "cta":
        for key in ["body", "bullets", "subtitle", "subhead", "kicker"]:
            entry.pop(key, None)
    # body: remover cta_*
```

Isso garante que mesmo se a IA retornar campos extras, eles sao descartados.

---

### 5. Atualizar `_fallback_payload` (stub)

O fallback atual gera body/bullets/cta no cover. Corrigir para respeitar as mesmas regras:
- Cover: so title + subtitle + brand + number
- Body: title + bullets (ou body) + number
- CTA: cta_title + cta_button + brand

---

### 6. Adaptar `_get_slot_schema` para retornar por role

Problema atual: `get_family_slots` retorna o slots.json inteiro da familia (com TODOS os slots: title, body, bullets, cta_title, etc.). Nao distingue por role.

Solucao: nova funcao `get_family_slots_for_role(family, format, role)` no template_service que:
1. Carrega o slots.json da familia
2. Busca a variacao selecionada (ou primeira) no `variations[format][role]`
3. Filtra os slots para retornar apenas os `primary_slots` + slots globais (brand, number, image)

Isso faz com que o outline_service receba constraints **apenas dos slots relevantes** para aquele role.

---

### 7. Adicionar teste unitario

Criar `app/tests/test_outline_roles.py`:

- Gerar fallback payload para carousel
- Validar: cover nao tem body/bullets/cta
- Validar: cta nao tem body/bullets
- Validar: body tem title + (bullets ou body)
- Validar: todos os slots respeitam limites do slots.json

---

### Arquivos modificados

| Arquivo | Mudanca |
|---|---|
| `app/utils/slots.py` | Adicionar `derive_slot_capabilities()` e `build_role_schema()` |
| `app/services/outline_service.py` | Refatorar prompts para role-aware, adicionar `_strip_forbidden_slots`, corrigir fallback |
| `app/services/template_service.py` | Adicionar `get_family_slots_for_role(family, format, role)` |
| `app/tests/test_outline_roles.py` | Teste unitario de validacao por role |
| `RUNBOOK.md` | Documentar regras de composicao por role |

### Arquivos NAO modificados

- `openai_service.py` — sem mudanca, compress_slot continua funcionando
- Templates HTML/CSS — sem mudanca
- Frontend — sem mudanca (ja consome o JSON corretamente)

