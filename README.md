# ClipForge AI

Aplicação web MVP para transformar vídeos autorizados em cortes curtos.

## Funcionalidades atuais

- Upload de vídeo.
- Escolha da quantidade de cortes.
- Duração aproximada de 30, 45, 60, 90 ou 120 segundos.
- Transcrição com OpenAI quando `OPENAI_API_KEY` estiver configurada.
- Seleção/ranking de candidatos com IA.
- Evita sobreposição forte entre cortes.
- Renderização vertical 9:16 com FFmpeg.
- Arquivos SRT.
- Preview no navegador.
- Download dos cortes.
- Endpoint `/health`.
- Docker.
- Configuração para Render.

## Requisitos locais

- Python 3.12+
- FFmpeg
- Uma chave da OpenAI é opcional para a parte inteligente.

### Ubuntu/Debian

```bash
sudo apt update
sudo apt install -y ffmpeg python3 python3-venv
```

### Instalação

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Configure a chave:

```bash
export OPENAI_API_KEY="SUA_CHAVE"
```

Execute:

```bash
python app.py
```

Abra:

```text
http://127.0.0.1:8000
```

## Docker

```bash
docker compose up --build
```

Abra:

```text
http://127.0.0.1:8000
```

## GitHub

```bash
git init
git add .
git commit -m "feat: initial ClipForge AI MVP"
git branch -M main
git remote add origin https://github.com/SEU-USUARIO/clipforge-ai.git
git push -u origin main
```

Não coloque `.env`, chaves de API ou vídeos no GitHub.

## Deploy com Render

O `render.yaml` e o `Dockerfile` já estão incluídos.

Fluxo:

1. Suba este projeto para o GitHub.
2. Crie um Web Service no Render.
3. Conecte o repositório.
4. Selecione Docker.
5. Configure `OPENAI_API_KEY` como Secret/Environment Variable.
6. Faça o deploy.

O endpoint `/health` pode ser usado como health check.

## Atenção sobre armazenamento

Este MVP grava arquivos em `data/`. Em hospedagem com filesystem efêmero, os arquivos podem desaparecer quando a instância reiniciar.

Para produção, use armazenamento persistente/S3 compatível.

## Próximas etapas

- PostgreSQL.
- Redis + worker separado.
- Armazenamento S3.
- Login de usuários.
- OAuth oficial do YouTube.
- OAuth oficial do TikTok.
- Publicação/agendamento conforme APIs e permissões oficiais.
- Legendas ASS/Karaoke palavra por palavra.
- Tracking de rosto/alto-falante.
- Editor de timeline.
- Sistema de pagamentos e planos.
- Limites por usuário.
- Observabilidade e logs.
- Processamento paralelo.

## Direitos autorais e APIs

Use somente conteúdo que você tenha autorização/direito de reutilizar.

Não use o sistema para contornar DRM, autenticação ou restrições de plataformas.

As integrações com plataformas devem utilizar APIs e mecanismos oficiais e respeitar as políticas vigentes.
