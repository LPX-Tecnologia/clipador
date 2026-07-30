# Subir manualmente para o GitHub

## 1. Crie o repositório

No GitHub, crie um repositório vazio chamado:

`clipforge-ai`

Não precisa criar README, .gitignore ou licença pelo site porque estes arquivos já estão no projeto.

## 2. Abra o terminal na pasta

```bash
cd clipforge_ai
```

## 3. Inicialize o Git

```bash
git init
git branch -M main
```

## 4. Confira os arquivos

```bash
ls -la
```

Você deverá ver:

- app.py
- requirements.txt
- Dockerfile
- docker-compose.yml
- render.yaml
- .env.example
- .gitignore
- README.md
- Procfile
- start.sh
- LICENSE

## 5. Faça o primeiro commit

```bash
git add .
git status
git commit -m "feat: initial ClipForge AI MVP"
```

## 6. Conecte ao GitHub

Troque SEU-USUARIO pelo seu usuário:

```bash
git remote add origin https://github.com/SEU-USUARIO/clipforge-ai.git
```

## 7. Envie

```bash
git push -u origin main
```

## 8. Confirme

Abra o repositório no navegador e confirme se os arquivos apareceram.

## Importante

NUNCA faça:

```bash
git add .env
```

O `.gitignore` já protege o `.env`, mas confira o `git status` antes do primeiro push.

Se uma chave de API for exposta no GitHub, revogue a chave imediatamente e gere outra.
