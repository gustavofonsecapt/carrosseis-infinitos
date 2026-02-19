

## Controle de Tema e Scrim por Slide

### Resumo

Implementar controles por slide para que o usuario escolha se o visual sera claro ou escuro e ajuste o scrim (overlay de legibilidade) -- tudo refletindo no preview React e no render final via Playwright. Um unico template HTML serve ambos os temas, alternando via classe CSS e tokens.

---

### 1. CSS: Sistema de temas via tokens (sem duplicar templates)

**Arquivo:** `public/templates/families/premium_editorial_v1/base.css` (e espelho em `app/templates/`)

Atualmente o tema dark funciona pela classe `.slide.dark`. Precisamos refatorar para um sistema `.theme-light` / `.theme-dark` mais completo e adicionar tokens de scrim:

```text
.theme-light {
  --bg: #fbfbf8;
  --surface: #f2f2ed;
  --ink: #111111;
  --muted: rgba(17,17,17,0.55);
  --line: rgba(17,17,17,0.12);
  --shadow: 0 2px 24px rgba(0,0,0,0.06);
  --scrim-color: rgba(0,0,0,0.35);
}
.theme-dark {
  --bg: #0f0f10;
  --surface: #1a1a1c;
  --ink: #f5f5f0;
  --muted: rgba(245,245,240,0.55);
  --line: rgba(245,245,240,0.12);
  --shadow: 0 2px 24px rgba(0,0,0,0.25);
  --scrim-color: rgba(0,0,0,0.55);
}
```

Todos os componentes (`.body-text`, `.subtitle`, `.bullets li`, `.cta-button`, `.accent-pill`, `.rule`, etc.) passam a consumir **apenas** tokens genericos (`var(--ink)`, `var(--muted)`, etc.) -- removendo as regras `.slide.dark .xxx` espalhadas.

Adicionar CSS de scrim via custom properties:
```text
.slide::before {
  content: '';
  position: absolute;
  inset: 0;
  background: var(--scrim-bg, transparent);
  pointer-events: none;
  z-index: 0;
}
```

Assim o render so precisa setar `--scrim-bg` via inline style quando necessario.

**Templates HTML:** Substituir `class="slide dark ..."` por `class="slide ..."` -- o tema sera aplicado via classe no render/preview.

---

### 2. Dados: appearance no payload do slide

**Sem mudanca de schema SQL** -- `appearance` vive dentro de `slides.payload` (campo JSON existente).

Estrutura:
```text
payload.appearance = {
  "theme": "auto" | "light" | "dark",     // default: "auto"
  "scrim": {
    "enabled": true | false,               // default: true
    "strength": 0.25 | 0.35 | 0.50,       // suave/medio/forte
    "position": "top" | "center" | "bottom", // default: "bottom"
    "mode": "gradient" | "box"             // default: "gradient"
  }
}
```

O endpoint PATCH existente (`/api/projects/{id}/slides/{index}`) ja aceita `payload` como JSON livre, entao nao precisa de mudanca no router nem no schema.

---

### 3. Backend: Render engine com overrides por slide

**Arquivo:** `app/services/render_service.py`

Modificar `_build_html` para:

1. Extrair `appearance = slide.payload.get("appearance", {})`
2. Resolver tema efetivo:
   - `appearance.theme == "light"` ou `"dark"` -> usar esse
   - `"auto"` ou ausente -> usar `variant.theme` do registry
3. Adicionar classe `theme-light` ou `theme-dark` no elemento `.slide`
4. Resolver scrim efetivo (merge de `appearance.scrim` com `variant.scrim`):
   - Se `appearance.scrim.enabled` esta definido, usar esse; senao usar `variant.scrim.enabled`
   - Idem para strength, position, mode
5. Gerar CSS inline `--scrim-bg` com o gradiente correto (usando `_scrim_gradient` ja existente, adaptado para modo "box" tambem)
6. Injetar como style inline no `.slide` ao inves de bloco `<style>` separado
7. Adicionar warnings: `applied_theme_dark`, `applied_theme_light`, `scrim_disabled`, `scrim_overridden`

Novo modo "box":
```text
def _scrim_box(...):
    return f"rgba(0,0,0,{strength})"  # solid translucido, aplicado apenas na area de texto
```
Para box, ao inves de pseudo-element no `.slide`, injeta um `<div class="scrim-box">` atras do `.content`.

---

### 4. Frontend: Controles de aparencia no SlideEditor

**Arquivo:** `src/components/SlideEditor.tsx`

Adicionar uma secao "Aparencia" com:

- **Tema:** 3 botoes (toggle group): Auto | Claro | Escuro
- **Scrim:** Switch on/off
- **Intensidade:** 3 botoes: Suave | Medio | Forte (mapeia para 0.25/0.35/0.50)
- **Posicao:** 3 botoes: Topo | Centro | Base
- **Modo:** 2 botoes: Gradiente | Box

Estado inicial carrega de `data.appearance` (novo campo no UiSlide). No `handleSave`, inclui `appearance` no payload.

---

### 5. Frontend: Tipo UiSlide atualizado

**Arquivo:** `src/types/project.ts`

Adicionar:

```text
interface SlideAppearance {
  theme: "auto" | "light" | "dark";
  scrim: {
    enabled: boolean;
    strength: number;
    position: "top" | "center" | "bottom";
    mode: "gradient" | "box";
  };
}

interface UiSlide {
  // ... campos existentes ...
  appearance?: SlideAppearance;
}
```

---

### 6. Frontend: Mapper atualizado

**Arquivo:** `src/services/api.ts`

No `mapApiSlideToUiSlide`, adicionar:
```text
appearance: p.appearance || undefined
```

---

### 7. Frontend: Preview ao vivo

**Arquivo:** `src/components/SlidePreview.tsx`

Aplicar visualmente o tema e scrim no card de preview:
- Se `appearance.theme === "dark"` -> fundo escuro, texto claro no preview card
- Se scrim ativo -> mostrar overlay gradiente no preview

---

### 8. Sincronizar templates app/ e public/

Garantir que `app/templates/families/premium_editorial_v1/base.css` receba as mesmas mudancas de tokens.

---

### Arquivos modificados

| Arquivo | Mudanca |
|---|---|
| `public/templates/families/premium_editorial_v1/base.css` | Refatorar para `.theme-light`/`.theme-dark` + tokens de scrim |
| `app/templates/families/premium_editorial_v1/base.css` | Espelho do acima |
| `public/templates/families/premium_editorial_v1/carousel/*.html` | Remover classe `dark` hardcoded, remover `overlay--dark` hardcoded |
| `app/templates/families/premium_editorial_v1/carousel/*.html` | Espelho |
| `public/templates/families/premium_editorial_v1/stories/*.html` | Idem |
| `app/templates/families/premium_editorial_v1/stories/*.html` | Idem |
| `app/services/render_service.py` | Resolver effective_theme e effective_scrim por slide, injetar classe e vars |
| `src/types/project.ts` | Tipo `SlideAppearance` |
| `src/services/api.ts` | Mapear `appearance` |
| `src/components/SlideEditor.tsx` | Secao "Aparencia" com controles visuais |
| `src/components/SlidePreview.tsx` | Refletir tema/scrim no preview card |

### Precedencia (documentar no RUNBOOK)

```text
slide.payload.appearance > registry template defaults > base defaults (light, scrim off)
```
