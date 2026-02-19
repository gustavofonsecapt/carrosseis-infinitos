# Carrosséis Infinitos – Runbook

> Documento operacional para rodar, diagnosticar e recuperar o backend FastAPI/Playwright.

## 1. Setup rápido
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env  # preencher OPENAI_API_KEY
playwright install chromium
```
Se faltar dependência de sistema (especialmente no VPS), execute com sudo usando o Python do venv:
```bash
sudo $(which python) -m playwright install --with-deps chromium
```

## 2. Smoke test
Após instalar o Playwright, verifique se ele renderiza algo:
```bash
source .venv/bin/activate
python - <<'PY'
from playwright.sync_api import sync_playwright
from pathlib import Path
out = Path('/tmp/playwright_ok.png')
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 800, "height": 600})
    page.set_content('<html><body><h1>ok</h1></body></html>')
    page.screenshot(path=str(out))
    browser.close()
print('Screenshot saved to', out)
PY
```

## 3. Estrutura de dados
- `data/app.db` – banco SQLite (não versionar).
- `data/projects/{id}/uploads` – imagens enviadas pelo usuário.
- `data/projects/{id}/renders/png` – PNGs finais.
- `data/projects/{id}/renders/render.log` – log linha-a-linha com template, duração e warnings (image_missing, image_blocked_external, etc.).
- `data/_e2e/` – guardar métricas e evidências de testes (gitignored).

## 4. Troubleshooting
### 4.1 PNG branco
1. Confirme que o backend usa `page.set_content` (já padrão) – reinicie se houver modificações.
2. Verifique se `render.log` registrou warnings (`image_blocked_external`, `image_missing_disk`). Ajuste uploads/template.
3. Garanta que o Playwright foi instalado com deps (`sudo $(which python) -m playwright install --with-deps chromium`).
4. Confira viewport 1080x1350 ou 1080x1920 (config padrão). Se alterado, revert.
5. Rode o smoke test acima; se falhar, reinstale o Playwright.

### 4.2 Render travado (status `rendering` eternamente)
1. `GET /api/projects/{id}` – confirme `status`.
2. Se travado, checar logs do servidor para o stacktrace registrado pelo `AppError(render_failed)`.
3. Forçar reset do status: `python - <<'PY' ...` (use o shell do FastAPI ou atualize direto via DB se necessário).
4. Se necessário, delete os PNGs da pasta `renders/` e rerode `POST /render`.

### 4.3 Playwright não instala
- Use o comando com sudo exibido acima.
- Em ambientes sem sudo, instale manualmente as bibliotecas do Chromium (libX11, libgtk, etc.) conforme [documentação Playwright Linux](https://playwright.dev/docs/browsers#linux).
- Reinstale o venv se o cache estiver corrompido.

### 4.4 Reset do banco
> **ATENÇÃO:** apaga todos os projetos e uploads.
```bash
rm -f data/app.db
rm -rf data/projects/*
mkdir -p data/projects
uvicorn app.main:app --reload
```
Recrie a base com `Base.metadata.create_all` rodando no startup.

## 5. Fluxo de verificação manual
1. Criar projeto carrossel (`POST /api/projects`).
2. `POST /generate-outline` com tema real.
3. Editar pelo menos um slide (`PATCH /slides/{n}`) e subir uma imagem (`POST /slides/{n}/image`).
4. `POST /render` e acompanhar `render.log`.
5. `GET /export` e conferir o ZIP baixado.
6. Registrar tempos e tamanhos em `data/_e2e/metrics.json`.

## 7. Slot Constraints (texto nunca quebra layout)

O sistema garante que o texto gerado pela IA respeita os limites definidos em `slots.json`:

### Fonte da verdade
- Layouts clássicos: `app/templates/layouts/{format}/{role}/slots.json`
- Famílias: `app/templates/families/{family}/slots.json`

### Pipeline de 3 camadas
1. **Prompt hard constraints** – O `outline_service` carrega os limites e os injeta no prompt com instruções explícitas para respeitar cada limite.
2. **Auto-rewrite (compress)** – Se um slot excede >15% do limite, o `openai_service.compress_slot()` reescreve automaticamente o texto para caber, preservando sentido e estilo.
3. **Truncation (fallback)** – `enforce_slot_limits()` trunca o que ainda exceder. Warnings são logados.

### Composition hints
O `build_composition_hints()` analisa o `slots.json` e orienta a IA:
- Se `bullets.max_items >= 3` e `body.max_chars <= 120` → prioriza bullets
- Se `body.max_chars >= 180` → permite parágrafo curto
- Headlines curtos (≤50 chars) recebem instrução de impacto

### Warnings expostos
Cada slide pode conter `warnings[]` no response:
```json
["title truncated to 68 chars", "applied_scrim_soft", "image_missing_disk"]
```

## 8. Scrim overlay (legibilidade garantida)

Quando um slide usa imagem, o `render_service` injeta automaticamente um overlay CSS para garantir contraste.

### Como funciona
1. O `registry.json` define metadados por variante: `theme`, `scrim`, `text_area`.
2. No render, se `scrim.enabled: true` E o slide tem imagem, um `::after` pseudo-element é adicionado ao `.slide`.
3. O gradiente é posicionado conforme `text_area` (top/center/bottom).

### Modos de scrim
| Modo | Cor base | Uso |
|------|----------|-----|
| `soft` | `rgba(255,255,255, strength)` | Templates claros com imagem |
| `dark` | `rgba(0,0,0, strength)` | Templates escuros com imagem |

### Configuração no registry.json
```json
{
  "id": "cover_v3",
  "theme": "dark",
  "scrim": { "enabled": true, "mode": "dark", "strength": 0.45 },
  "text_area": "bottom"
}
```

### Controle de aparência por slide

O usuário pode sobrescrever tema e scrim por slide via `payload.appearance`:

```json
{
  "appearance": {
    "theme": "auto|light|dark",
    "scrim": {
      "enabled": true,
      "strength": 0.25|0.35|0.50,
      "position": "top|center|bottom",
      "mode": "gradient|box"
    }
  }
}
```

**Precedência:**
```
slide.payload.appearance > registry.json template defaults > base CSS defaults (light, scrim off)
```

- `theme: "auto"` → usa o tema do template no registry
- `theme: "light"/"dark"` → aplica `.theme-light`/`.theme-dark` no elemento `.slide`
- Scrim `gradient` → pseudo-element `::before` com gradiente posicional
- Scrim `box` → div `.scrim-box` translúcido com backdrop-filter atrás do `.content`

### Logs de scrim
O `render.log` registra `scrim=yes|no` por slide. Warnings incluem:
- `applied_theme_dark`, `applied_theme_light` — tema sobrescrito pelo slide
- `applied_scrim_gradient_bottom`, `applied_scrim_box` — tipo de scrim aplicado
- `scrim_disabled`, `scrim_enabled` — scrim alterado vs default do template
- `scrim_strength_changed` — intensidade diferente do default

## 9. Referências úteis
- Envelope de erro padrão (`AppError`): `{"error": {"code": "...", "message": "...", "details": {...}}}`.
- Templates e slots: `app/templates/registry.json` + `app/templates/layouts/.../slots.json`.
- Runbook complementar: README.md (seção "Teste rápido com curl").
