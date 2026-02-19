# Welcome to your Lovable project

## Project info

**URL**: https://lovable.dev/projects/REPLACE_WITH_PROJECT_ID

## How can I edit this code?

There are several ways of editing your application.

**Use Lovable**

Simply visit the [Lovable Project](https://lovable.dev/projects/REPLACE_WITH_PROJECT_ID) and start prompting.

Changes made via Lovable will be committed automatically to this repo.

**Use your preferred IDE**

If you want to work locally using your own IDE, you can clone this repo and push changes. Pushed changes will also be reflected in Lovable.

The only requirement is having Node.js & npm installed - [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating)

Follow these steps:

```sh
# Step 1: Clone the repository using the project's Git URL.
git clone <YOUR_GIT_URL>

# Step 2: Navigate to the project directory.
cd <YOUR_PROJECT_NAME>

# Step 3: Install the necessary dependencies.
npm i

# Step 4: Start the development server with auto-reloading and an instant preview.
npm run dev
```

**Edit a file directly in GitHub**

- Navigate to the desired file(s).
- Click the "Edit" button (pencil icon) at the top right of the file view.
- Make your changes and commit the changes.

**Use GitHub Codespaces**

- Navigate to the main page of your repository.
- Click on the "Code" button (green button) near the top right.
- Select the "Codespaces" tab.
- Click on "New codespace" to launch a new Codespace environment.
- Edit files directly within the Codespace and commit and push your changes once you're done.

## What technologies are used for this project?

This project is built with:

- Vite
- TypeScript
- React
- shadcn-ui
- Tailwind CSS

## Backend (FastAPI + SQLite)

A Python backend now lives in the same repo to power the generation/rendering flows.

### Requirements

- Python 3.12+
- Node.js/npm (already required for the Lovable frontend)
- Playwright browsers (`playwright install chromium`). Se precisar resolver dependências de sistema, use o comando padrão abaixo com o venv ativo:
  ```bash
  sudo $(which python) -m playwright install --with-deps chromium
  ```

### Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env  # preenche OPENAI_API_KEY antes de rodar
playwright install chromium
uvicorn app.main:app --reload
```

The FastAPI server exposes `GET /health` for quick smoke tests. Config is loaded from `.env` and defaults to local SQLite storage under `./data`.

### Directory highlights

```
app/
  main.py              # FastAPI entrypoint
  core/                # config + database bootstrap
  routers/, services/  # regras de negócio / endpoints / integrações
  templates/           # HTML/CSS templates usados na renderização
data/
  app.db               # SQLite
  projects/            # assets, uploads e renders por projeto
```

### Fluxo da API (MVP)
1. `POST /api/projects` — cria o projeto (carousel/stories) com seleção de templates.
2. `POST /api/projects/{id}/generate-outline` — chama OpenAI e grava os slides (status vai para `outlined`).
3. `PATCH /api/projects/{id}/slides/{n}` ou `POST /slides/{n}/image` — edita texto/upload; isso zera o `render_path` daquele slide.
4. `POST /api/projects/{id}/render` — renderiza todos os slides via Playwright. O status muda para `rendering` e depois `rendered`. Chamadas concorrentes retornam 409.
5. `GET /api/projects/{id}/export` — monta um ZIP em memória com os PNGs ordenados.

### Renderização
- O HTML final embute todo o CSS (`base.css` + variação) em `<style>` para evitar quebras de caminho.
- Imagens (template ou upload) são referenciadas via `file:///absoluto/...` quando existem no disco; fallback é um PNG em branco (data URI).
- O Playwright aguarda `networkidle` + `document.images.every(img => img.complete)` antes do screenshot, reduzindo riscos de PNG vazio.

### Backlog conhecido
- Exports hoje usam `BytesIO` em memória. Para projetos grandes, migrar para ZIP em disco/streaming.
- Migrar de `Base.metadata.create_all` para Alembic antes de produção.
- Criar runbook dedicado (deploy + troubleshooting) antes do primeiro deploy em VPS.

### Teste rápido com `curl`
Use `BASE=http://127.0.0.1:8000` (ou a URL exposta) e execute:

1. **Criar projeto**
   ```bash
   curl -s -X POST "$BASE/api/projects" \
     -H "Content-Type: application/json" \
     -d '{
       "type": "carousel",
       "title": "Casa TH — Implantação e Sombra",
       "template_selection": {"carousel": {"cover": "cover_v1", "body": "body_v1", "cta": "cta_v1"}},
       "slides_count": 8
     }' | tee /tmp/project.json

   PROJECT_ID=$(python - <<'PY'
import json
print(json.load(open("/tmp/project.json"))["id"])
PY
   )
   ```

2. **Gerar outline**
   ```bash
   curl -s -X POST "$BASE/api/projects/$PROJECT_ID/generate-outline" \
     -H "Content-Type: application/json" \
     -d '{
       "topic": "Implantação que resolve o cotidiano (sombra, percurso, volumes)",
       "tone": "editorial minimalista",
       "cta_action": "DM",
       "cta_trigger_word": "CASA"
     }' | jq .
   ```

3. **Upload de imagem (slide 2)**
   ```bash
   curl -s -X POST "$BASE/api/projects/$PROJECT_ID/slides/2/image" \
     -F "file=@/caminho/para/imagem.png" | jq .
   ```

4. **Renderizar**
   ```bash
   curl -s -X POST "$BASE/api/projects/$PROJECT_ID/render" | jq .
   ```

5. **Exportar ZIP**
   ```bash
   curl -L -o "/tmp/${PROJECT_ID}.zip" "$BASE/api/projects/$PROJECT_ID/export"
   ls -lh "/tmp/${PROJECT_ID}.zip"
   ```

6. **Conferir logs**
   ```bash
   tail -n 50 "data/projects/$PROJECT_ID/renders/render.log"
   ```

### Respostas de erro
Toda resposta de erro segue o envelope:
```json
{
  "error": {
    "code": "render_in_progress",
    "message": "Project is already rendering",
    "details": {"project_id": "..."}
  }
}
```
Códigos atuais: `project_not_found`, `slide_not_found`, `template_not_found`, `render_in_progress`, `invalid_payload`, `upload_too_large`, `render_failed`, `export_failed_missing_file`.

### Outputs e reset do banco
- Renders, uploads e logs residem em `data/projects/{project_id}/` (subpastas `uploads/`, `renders/png/`, `renders/render.log`).
- O banco SQLite fica em `data/app.db`. Para reset local, pare o servidor e execute `rm -f data/app.db && uvicorn app.main:app --reload` para recriar a base vazia (apaga todos os projetos).
- Evidências de testes podem ser guardadas em `data/_e2e/` (entrada já adicionada ao `.gitignore`).

### Métricas de referência
- Tempo total de render (8 slides): _pendente medir no E2E_.
- Tempo médio por slide: _pendente_.
- Tamanho médio dos PNGs e ZIP: _pendente_.

## How can I deploy this project?

Simply open [Lovable](https://lovable.dev/projects/REPLACE_WITH_PROJECT_ID) and click on Share -> Publish.

## Can I connect a custom domain to my Lovable project?

Yes, you can!

To connect a domain, navigate to Project > Settings > Domains and click Connect Domain.

Read more here: [Setting up a custom domain](https://docs.lovable.dev/features/custom-domain#custom-domain)
