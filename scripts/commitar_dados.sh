#!/usr/bin/env bash
# Envia ao GitHub só os arquivos que o bot gerou. Uso: scripts/commitar_dados.sh "mensagem" caminho [caminho...]
# Robusto a: outro envio chegando no meio (sincroniza e tenta de novo), arquivos modificados que são de outros bots
# (são descartados, o bot não é dono deles) e caminhos que não existem.
set -u
msg="$1"; shift
git config user.name "${GIT_AUTOR_NOME:-bot-turiz}"
git config user.email "${GIT_AUTOR_EMAIL:-bot-turiz@users.noreply.github.com}"
for p in "$@"; do [ -e "$p" ] && git add -- "$p"; done
if git diff --cached --quiet; then echo "sem mudanças"; exit 0; fi
git commit -q -m "$msg"
git checkout -- . 2>/dev/null || true        # saídas de outros bots que este não deve enviar
for t in 1 2 3 4 5 6; do
  if git pull -q --rebase origin main && git push -q origin main; then echo "dados enviados (tentativa $t)"; exit 0; fi
  echo "tentativa $t falhou; sincronizando de novo"
  git rebase --abort 2>/dev/null || true
  sleep $(( RANDOM % 10 + 4 ))
done
echo "não consegui enviar os dados"; exit 1
