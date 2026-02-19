

## Plano: Integrar seleção de família de templates no fluxo de criação e renderização

### Problema atual

O backend já possui o campo `template_selection` no modelo `Project` e o `RenderService` já o consulta para escolher variantes. Porém:

1. **O `TemplateRegistry` não suporta a estrutura da família premium** -- o `registry.json` tem `premium_editorial_v1` com nesting diferente (`premium_editorial_v1 > carousel > cover`) vs o layout antigo (`carousel > cover`). O método `get_variant` faz `registry[family][role_key]`, que só funciona para o layout antigo.

2. **O frontend não oferece seleção de template** -- o `CreateProject` não envia `template_selection` ao criar o projeto.

3. **Os templates premium estão apenas em `public/templates/`** mas o backend lê de `app/templates/` (via `settings.templates_dir`). Embora o `registry.json` em `app/templates/` já inclua `premium_editorial_v1`, os arquivos HTML ficam em `app/templates/families/` que precisam existir lá.

---

### Solução

#### 1. Garantir que os templates premium existam em `app/templates/`

Copiar a pasta `families/premium_editorial_v1/` (com base.css, variants.css e todos os HTMLs) para `app/templates/families/premium_editorial_v1/`, espelhando o que já está em `public/templates/`.

#### 2. Refatorar o `TemplateRegistry` para suportar famílias

Atualizar `template_service.py` para que `get_variant` aceite um parâmetro `family_name` (ex: `"premium_editorial_v1"`) além do formato/role. Quando o projeto tem uma família selecionada, busca em `registry[family_name][format][role]`; caso contrário, cai no comportamento atual (`registry[format][role]`).

#### 3. Atualizar o `RenderService._resolve_variant`

Modificar para ler `template_selection.family` do projeto e passar ao registry. Exemplo de `template_selection`:

```text
{
  "family": "premium_editorial_v1",
  "carousel": {
    "cover": "pe_cover_v1",
    "body": "pe_body_v2",
    "cta": "pe_cta_v1"
  }
}
```

Se `family` estiver presente, busca variantes dentro daquela família. Senão, usa o comportamento antigo (layouts avulsos).

#### 4. Adicionar endpoint para listar famílias e variações

Criar `GET /api/templates/families` que retorna as famílias disponíveis com suas variações, lendo do `registry.json`. Isso alimenta o seletor no frontend.

#### 5. Adicionar seletor de template no frontend

No `CreateProject.tsx`, adicionar:
- Um `Select` para escolher a **família de templates** (ex: "Premium Editorial V1" ou "Layouts Clássicos")
- Opcionalmente, selects para escolher a variação de cada role (cover, body, cta)
- Enviar `template_selection` no payload de `createProject()`

#### 6. Atualizar `createProject` na API do frontend

Passar `template_selection` no body do POST para `/api/projects`.

---

### Detalhes técnicos

**Arquivos modificados no backend:**

| Arquivo | Mudança |
|---|---|
| `app/services/template_service.py` | Novo método `get_variant_from_family(family, format, role, variant_id)` e `list_families()` |
| `app/services/render_service.py` | `_resolve_variant` lê `template_selection.family` e delega ao novo método |
| `app/routers/templates.py` | Novo endpoint `GET /api/templates/families` |

**Arquivos modificados no frontend:**

| Arquivo | Mudança |
|---|---|
| `src/pages/CreateProject.tsx` | Seletor de família + variações |
| `src/services/api.ts` | `createProject` envia `template_selection` |
| `src/types/project.ts` | Tipo `TemplateSelection` |

**Arquivos criados:**

| Arquivo | Descrição |
|---|---|
| `app/templates/families/premium_editorial_v1/*` | Cópia dos HTMLs e CSS da família premium (espelhando `public/`) |

