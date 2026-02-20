

# Galeria de Templates: Preview Real via Backend (Playwright)

## Problema
A galeria atual (`public/templates/gallery.html`) e uma pagina HTML estatica com iframes apontando para arquivos locais. Esses arquivos sao copias no `public/` que podem divergir dos templates reais usados pelo backend (`app/templates/`). Resultado: "vitrine bonita" que nao reflete o PNG final.

## Solucao

Criar uma pagina React `/gallery` que consome a API do backend para listar templates e gera thumbnails reais via `POST /api/templates/{id}/preview/json` (Playwright).

---

## Etapa 1 -- Pagina React de Galeria

Criar `src/pages/TemplateGallery.tsx`:

- Ao montar, chamar `GET /api/templates` para obter o registry completo
- Parsear a resposta separando families (premium_editorial_v1) e legacy (carousel/stories)
- Para cada family/format/role, listar os template cards com: `id`, `label`, `role`, `format`
- Adicionar rota `/gallery` no `App.tsx`

### Layout da pagina
- Header com titulo "Template Gallery" e toggle "Preview Real / Rapido"
- Secoes por familia (Premium Editorial V1, Classic)
- Dentro de cada familia, subsecoes por role (Cover, Body, CTA)
- Cards em grid responsivo

---

## Etapa 2 -- Thumbnails via Backend Preview

Criar `src/components/TemplateCard.tsx`:

- Recebe `templateId`, `label`, `format`, `role`, `family`
- Ao montar (ou ao entrar no viewport), chama `POST /api/templates/{id}/preview/json?format_key={format}`
- Exibe skeleton/loading enquanto aguarda
- Ao receber resposta, renderiza `<img src="data:image/png;base64,..." />`
- Exibe warnings (font_timeout, image_missing) como badges discretos no card
- Cache em `useState` / `useRef` para nao re-chamar ao scroll

### Fallback offline
- Se a chamada falhar (backend offline / timeout), exibir card com icone "Backend offline" e mensagem clara
- Botao "Tentar novamente" no card

---

## Etapa 3 -- Modal de detalhe do template

Ao clicar num card:
- Abrir dialog com PNG em tamanho maior
- Mostrar metadata: `template_id`, `template_path`, `theme`, `available_slots`, `filled_slots`, `missing_required`
- Mostrar warnings do preview
- Botao "Usar como padrao" (para futuro uso na criacao de projeto)

---

## Etapa 4 -- Funcao de API no frontend

Adicionar em `src/services/api.ts`:

```typescript
export async function fetchTemplateRegistry(): Promise<Record<string, any>> {
  return http<Record<string, any>>("/api/templates");
}

export async function fetchTemplatePreview(
  templateId: string,
  formatKey: string = "carousel"
): Promise<{
  image_base64: string;
  warnings: string[];
  slot_info: Record<string, any>;
}> {
  return http("/api/templates/" + templateId + "/preview/json?format_key=" + formatKey, {
    method: "POST",
    body: JSON.stringify(null),
  });
}
```

---

## Etapa 5 -- Botao "Regerar thumbnails"

- Botao no header da galeria que limpa o cache local (state) e re-chama todos os previews
- Util para validar apos alterar CSS/templates

---

## Etapa 6 -- Rota e navegacao

- Adicionar `/gallery` no `App.tsx` (rota React)
- Adicionar link "Galeria" no `Layout.tsx` / `NavLink`
- A galeria estatica `public/templates/gallery.html` permanece como arquivo legacy mas nao e mais o caminho principal

---

## Secao Tecnica

### Arquivos criados
| Arquivo | Descricao |
|---|---|
| `src/pages/TemplateGallery.tsx` | Pagina principal da galeria |
| `src/components/TemplateCard.tsx` | Card com thumbnail via preview API |

### Arquivos modificados
| Arquivo | Mudanca |
|---|---|
| `src/App.tsx` | Adicionar rota `/gallery` |
| `src/services/api.ts` | Adicionar `fetchTemplateRegistry` e `fetchTemplatePreview` |
| `src/components/Layout.tsx` | Adicionar link de navegacao para galeria |

### Backend -- sem mudancas
Os endpoints ja existem e funcionam:
- `GET /api/templates` -- retorna registry.json
- `POST /api/templates/{id}/preview/json` -- retorna PNG base64 + metadata

### Fluxo de dados
```text
TemplateGallery
  |-- GET /api/templates --> registry JSON
  |-- Para cada template_id:
       |-- POST /api/templates/{id}/preview/json
       |-- Playwright renderiza HTML real (app/templates/...)
       |-- Retorna PNG base64
       |-- TemplateCard exibe <img src="data:..." />
```

### Cache e performance
- Cada TemplateCard faz 1 chamada ao montar (Playwright por template)
- Para 27 templates, sao 27 chamadas sequenciais ou com concorrencia limitada (max 3 simultaneas via queue)
- Cache em state React -- nao re-chama ao re-render
- Botao "Regerar" limpa cache e re-dispara

### Riscos e mitigacoes
- **Playwright lento**: thumbnails podem demorar 2-5s cada. Skeleton loading + carregamento progressivo
- **Backend offline**: fallback visual claro, sem quebra de UI
- **27 chamadas simultaneas**: limitar concorrencia a 3 para nao sobrecarregar o Playwright

