
# Adicionar Slot de Imagem a Todos os Templates

## Problema
13 templates (3 premium, 10 classic) nao possuem `data-slot="image"`, fazendo com que imagens enviadas pelo usuario sejam ignoradas no render. Alem disso, o `render_service.py` possui logica de "auto-promote" que troca o template quando detecta imagem -- causando regressao visual.

## Auditoria Completa

### Templates que JA possuem imagem (14 -- nao precisam de mudanca HTML)
pe_cover_v1, pe_cover_v2, pe_cover_v3, pe_body_v2, pe_body_v3, pe_cta_v2, pe_cta_v3, pe_story_v2, pe_story_v3, cover_v2, cover_v3, body_v2, body_v3, story_v2, story_v3

### Templates que PRECISAM de imagem (13)
| Template | Familia | Formato | Role | Estrategia de imagem |
|---|---|---|---|---|
| pe_body_v1 | Premium | Carousel | Body | Card editorial lateral (40% inferior) |
| pe_cta_v1 | Premium | Carousel | CTA | Background sutil com scrim leve |
| pe_story_v1 | Premium | Stories | Frame | Card editorial no topo (640px) |
| cover_v1 | Classic | Carousel | Cover | Background full-bleed com overlay |
| body_v1 | Classic | Carousel | Body | Card editorial (340px, entre kicker e texto) |
| cta_v1 | Classic | Carousel | CTA | Background full-bleed com overlay escuro |
| cta_v2 | Classic | Carousel | CTA | Background full-bleed com overlay escuro |
| cta_v3 | Classic | Carousel | CTA | Background full-bleed (ja inverted, overlay) |
| story_v1 | Classic | Stories | Frame | Background full-bleed com overlay |
| story_cta_v1 | Classic | Stories | CTA | Background full-bleed com overlay |
| story_cta_v2 | Classic | Stories | CTA | Background full-bleed com overlay |
| story_cta_v3 | Classic | Stories | CTA | Background full-bleed (ja inverted) |

---

## Etapa 1 -- Adicionar imagem aos 3 templates Premium

### pe_body_v1 (Type-led Minimal)
Adicionar um card editorial de imagem entre o header e o text-block:
```text
<div class="image-card-zone">
  <img data-slot="image" src="../../assets/images/placeholder.jpg" alt="">
</div>
```
CSS em `variants.css`: reutilizar `.body-v1 .image-card-zone` com height 380px, border-radius var(--radius-card), overflow hidden, margin-bottom 32px.
Quando sem imagem: `.image-card-zone:has(img[src=""])` ou o backend esconde via classe.

### pe_cta_v1 (Minimal CTA)
Adicionar imagem como background sutil atras do conteudo:
```text
<img data-slot="image" class="img-cover" src="../../assets/images/placeholder.jpg" alt="" style="opacity:0.15">
```
Inserir antes do `.content`. Sem overlay necessario (opacidade baixa). Sem imagem: o `img-cover` fica transparente (1px placeholder).

### pe_story_v1 (Type-led Minimal)
Adicionar card editorial entre o brand e o text-block:
```text
<div class="image-hero" style="margin-top:32px">
  <img data-slot="image" src="../../assets/images/placeholder.jpg" alt="">
</div>
```
CSS: reutilizar `.story .image-hero` que ja existe em variants.css (height 640px).

---

## Etapa 2 -- Adicionar imagem aos 10 templates Classic

### Carousel

**cover_v1**: Adicionar `img-cover` + `overlay-dark` antes do `.content`. Texto ja esta centrado, overlay garante legibilidade.

**body_v1**: Adicionar `.image-zone` (340px) entre o divider e o paragrafo de body. Reutilizar CSS de body_v2 `.image-zone`.

**cta_v1, cta_v2, cta_v3**: Adicionar `img-cover` + `overlay-dark` antes do `.content`. Para cta_v3 (ja inverted), overlay mais leve. Texto fica sobre a imagem com contraste garantido.

### Stories

**story_v1**: Adicionar `img-cover` + `overlay-dark` antes do `.content`. Texto fica sobre imagem.

**story_cta_v1, story_cta_v2, story_cta_v3**: Adicionar `img-cover` + `overlay-dark` antes do `.content`. Para story_cta_v3 (ja inverted), overlay ajustado.

---

## Etapa 3 -- CSS para graceful fallback (sem imagem)

Adicionar nos 4 base.css (carousel cover/body/cta e stories frame/cta):
```css
/* Imagem ausente: placeholder transparente nao afeta layout */
img.img-cover[src=""], img.img-cover[src*="placeholder"] {
  opacity: 0;
}
.image-zone:empty, .image-card-zone:empty,
.image-hero:empty {
  display: none;
}
```

Para premium, adicionar em `base.css`:
```css
.image-card-zone:has(img[src=""]),
.image-hero:has(img[src=""]) {
  display: none;
}
```

O render_service ja injeta um placeholder 1px transparente quando nao ha imagem -- esse placeholder sera visualmente invisivel (opacity 0 ou 1px).

---

## Etapa 4 -- Atualizar slots.json (uses_image: true)

### Classic slots.json (3 arquivos)
- `layouts/carousel/cover/slots.json`: cover_v1 `uses_image: true`
- `layouts/carousel/body/slots.json`: body_v1 `uses_image: true`
- `layouts/carousel/cta/slots.json`: cta_v1, cta_v2, cta_v3 todos `uses_image: true`
- `layouts/stories/frame/slots.json`: story_v1 `uses_image: true`
- `layouts/stories/cta/slots.json`: story_cta_v1, v2, v3 todos `uses_image: true`

### Premium slots.json
- `families/premium_editorial_v1/slots.json`: pe_body_v1 e pe_cta_v1 `uses_image: true`, pe_story_v1 `uses_image: true`

---

## Etapa 5 -- Remover auto-promote no render_service.py

Remover o bloco de logica nas linhas 531-557 que troca o template quando `slide.image_path` existe e o template atual nao suporta imagem. Com todos os templates suportando imagem, essa logica e desnecessaria e era a causa da regressao.

Substituir por um simples warning se o template nao tiver `uses_image` mas houver imagem:
```python
if slide.image_path and not current_variant_supports_image:
    # Log warning but DO NOT change template
    logger.warning("Slide %d has image but template %s declares uses_image=false", 
                   slide.index, selected_id)
```

---

## Etapa 6 -- Espelhar para public/templates/

Copiar todas as alteracoes HTML para os arquivos correspondentes em `public/templates/` para manter paridade (necessario para previews iframe).

---

## Secao Tecnica

### Arquivos modificados

| Arquivo | Mudanca |
|---|---|
| `app/templates/families/premium_editorial_v1/carousel/body_v1.html` | Adicionar image-card-zone com data-slot="image" |
| `app/templates/families/premium_editorial_v1/carousel/cta_v1.html` | Adicionar img-cover background |
| `app/templates/families/premium_editorial_v1/stories/frame_v1.html` | Adicionar image-hero com data-slot="image" |
| `app/templates/families/premium_editorial_v1/variants.css` | CSS para body-v1 image-card-zone |
| `app/templates/families/premium_editorial_v1/slots.json` | uses_image: true para pe_body_v1, pe_cta_v1, pe_story_v1 |
| `app/templates/layouts/carousel/cover/cover_v1.html` | Adicionar img-cover + overlay |
| `app/templates/layouts/carousel/body/body_v1.html` | Adicionar image-zone |
| `app/templates/layouts/carousel/cta/cta_v1.html` | Adicionar img-cover + overlay |
| `app/templates/layouts/carousel/cta/cta_v2.html` | Adicionar img-cover + overlay |
| `app/templates/layouts/carousel/cta/cta_v3.html` | Adicionar img-cover + overlay |
| `app/templates/layouts/stories/frame/story_v1.html` | Adicionar img-cover + overlay |
| `app/templates/layouts/stories/cta/story_cta_v1.html` | Adicionar img-cover + overlay |
| `app/templates/layouts/stories/cta/story_cta_v2.html` | Adicionar img-cover + overlay |
| `app/templates/layouts/stories/cta/story_cta_v3.html` | Adicionar img-cover + overlay |
| `app/templates/layouts/carousel/cover/slots.json` | cover_v1 uses_image: true |
| `app/templates/layouts/carousel/body/slots.json` | body_v1 uses_image: true |
| `app/templates/layouts/carousel/cta/slots.json` | todos uses_image: true |
| `app/templates/layouts/stories/frame/slots.json` | story_v1 uses_image: true |
| `app/templates/layouts/stories/cta/slots.json` | todos uses_image: true |
| `app/templates/layouts/carousel/cover/cover.css` | CSS para cover_v1 com imagem |
| `app/templates/layouts/carousel/body/body.css` | CSS para body_v1 image-zone |
| `app/templates/layouts/carousel/cta/cta.css` | CSS para cta com imagem background |
| `app/templates/layouts/stories/frame/story.css` | CSS para story_v1 com imagem |
| `app/templates/layouts/stories/cta/story_cta.css` | CSS para story_cta com imagem |
| `app/services/render_service.py` | Remover auto-promote (linhas 531-557) |
| `public/templates/...` | Espelhar todas as alteracoes HTML |

### Padrao de insercao de imagem

Para templates "type-led" (texto puro) que recebem imagem como **background**:
```html
<img data-slot="image" class="img-cover" src="../../assets/images/placeholder.jpg" alt="">
<div class="overlay-dark"></div>
<!-- .content existente permanece inalterado -->
```

Para templates que recebem imagem como **card editorial**:
```html
<div class="image-zone">
  <img data-slot="image" src="../../assets/images/placeholder.jpg" alt="">
</div>
```

### Contraste garantido
- Templates com imagem full-bleed usam `.overlay-dark` (gradiente 20% a 65%) ja definido nos base.css
- Templates com card de imagem nao precisam de scrim (imagem separada do texto)
- O render_service ja aplica scrim adicional via `_resolve_effective_scrim` quando detecta imagem

### Riscos
- Nenhum template existente que ja tem imagem sera alterado
- O fallback (sem imagem) usa o placeholder 1px do render_service que sera invisivel
- A remocao do auto-promote e segura porque todos os templates passam a suportar imagem
