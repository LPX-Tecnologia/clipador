# Clipador — Frontend do ClipForge AI

Frontend estático para GitHub Pages.

## Arquivos

- `index.html` — interface.
- `style.css` — visual responsivo.
- `app.js` — conexão com a API FastAPI.

## Publicar no GitHub Pages

1. Coloque os três arquivos na raiz do repositório `clipador`.
2. Faça commit e push.
3. No GitHub: Settings → Pages.
4. Em "Build and deployment", escolha:
   - Source: Deploy from a branch
   - Branch: `main`
   - Folder: `/ (root)`
5. Salve.

## Conectar à API

Na interface existe o campo:

`URL da API`

Digite a URL do backend, por exemplo:

`https://SEU-BACKEND.onrender.com`

Clique em **Salvar**.

A página testa:

`GET /health`

e depois envia vídeos para:

`POST /api/projects`

O progresso é consultado em:

`GET /api/projects/{job_id}`

## Importante

O frontend não executa Python ou FFmpeg. Ele apenas envia o vídeo para o backend e mostra os resultados.

Não coloque `OPENAI_API_KEY` neste repositório. A chave deve ficar somente no backend.
