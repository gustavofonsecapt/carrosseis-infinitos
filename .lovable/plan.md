

## Problema

O `SlidePreview` e um componente React simplificado que mostra headline/subhead/body/bullets como texto puro. Ele **nao usa o campo `template_variant`** para nada visual --- entao mudar o template e salvar nao causa nenhuma mudanca visivel no card.

Alem disso, o campo `render_path` (PNG renderizado pelo backend) nunca e exibido no preview, mesmo quando disponivel.

---

## Solucao

### 1. Mostrar imagem renderizada (render_path) quando disponivel

Quando o slide ja foi renderizado pelo backend (status `rendered`), o `SlidePreview` deve exibir a imagem PNG real em vez do preview simplificado de texto. Isso mostra exatamente como o template ficara.

- Se `render_path` existe: mostrar a imagem PNG como card
- Se nao: manter o preview de texto simplificado atual (fallback)

### 2. Badge de template variant no SlidePreview

Adicionar um badge visual no canto do card mostrando qual variante esta selecionada (ex: "v2", "v3"). Isso da feedback imediato ao usuario de que a mudanca foi salva, mesmo antes de re-renderizar.

### 3. Invalidar render_path no frontend apos salvar

O backend ja limpa `render_path = None` quando o payload muda. Mas o frontend precisa refletir isso: apos salvar, o card volta ao preview de texto (indicando que precisa re-renderizar para ver o resultado final com o novo template).

### 4. Feedback visual pos-save

Adicionar um toast de confirmacao ao salvar e um indicador visual (badge "Precisa renderizar") nos cards cujo `render_path` e null mas o projeto ja foi renderizado antes.

---

## Detalhes tecnicos

### Arquivo: `src/components/SlidePreview.tsx`

- Verificar se `data.render_path` existe; se sim, renderizar `<img src={API_BASE}/{render_path}>` como conteudo principal do card
- Adicionar badge de template variant (canto inferior esquerdo): mostrar `data.template_variant` se definido (ex: "body_v2")
- Adicionar badge "Desatualizado" quando `render_path` e null e o slide tem conteudo (ja foi editado)

### Arquivo: `src/components/SlideEditor.tsx`

- Na funcao `handleSave`: adicionar toast de confirmacao (`sonner`) apos `onSave(payload)`
- Garantir que o payload enviado inclui todos os campos existentes do slide para nao perder dados (merge com `data` original)

### Arquivo: `src/pages/ProjectEditor.tsx`

- Sem mudancas estruturais --- o fluxo de save ja atualiza o state corretamente via `setProject`
- Adicionar indicador textual abaixo do grid: "Slides editados desde a ultima renderizacao. Clique em Renderizar PNGs para atualizar."

---

## Arquivos modificados

| Arquivo | Mudanca |
|---|---|
| `src/components/SlidePreview.tsx` | Mostrar render_path quando disponivel, badge de variant, badge de desatualizado |
| `src/components/SlideEditor.tsx` | Toast de confirmacao, merge de payload com dados originais |
| `src/pages/ProjectEditor.tsx` | Indicador de slides desatualizados |

