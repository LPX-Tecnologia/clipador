# Clipador — app web

Site de uma página só (não precisa instalar nada nem compilar) que conecta ao seu banco Supabase.

## Como colocar no GitHub

1. Crie um repositório novo no GitHub (pode ser público ou privado)
2. Suba os arquivos `index.html` e este `README.md` pra dentro dele
   - Mais fácil: na página do repositório, clique em **Add file → Upload files** e arraste o `index.html`
3. Ative o GitHub Pages:
   - Vá em **Settings → Pages**
   - Em **Source**, selecione a branch `main` e a pasta `/ (root)`
   - Salve — em ~1 minuto seu site fica no ar em algo como
     `https://seu-usuario.github.io/nome-do-repositorio/`

## Como configurar

1. Abra o site
2. Clique em **Configurar Supabase** no topo
3. Cole a **Project URL** e a **anon public key** (Supabase → Project Settings → API)
4. Salve

## Como usar

1. Digite seu e-mail e clique em **Enviar link de acesso** — você recebe um link mágico por e-mail (sem precisar de senha)
2. Clique no link do e-mail pra entrar
3. Cole um link do YouTube e clique em **Enviar**
4. O vídeo aparece na lista com uma barrinha mostrando a etapa atual (baixando, transcrevendo, analisando, pronto)

Nota: a listagem e o formulário já funcionam sozinhos assim que o Supabase estiver configurado. Quem faz o trabalho pesado (baixar o vídeo, transcrever, cortar, legendar e preencher as tabelas `clips`) é o fluxo do n8n que a gente vai montar em seguida — ele escreve nessas mesmas tabelas, e o site atualiza mostrando o progresso automaticamente.
