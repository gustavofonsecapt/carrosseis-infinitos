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

## 6. Referências úteis
- Envelope de erro padrão (`AppError`): `{"error": {"code": "...", "message": "...", "details": {...}}}`.
- Templates e slots: `app/templates/registry.json` + `app/templates/layouts/.../slots.json`.
- Runbook complementar: README.md (seção "Teste rápido com curl").
