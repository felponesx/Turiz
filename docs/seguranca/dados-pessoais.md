# Mapa de dados pessoais e LGPD

Princípios: **minimização** (só o necessário), **pseudonimização** (IP e notas viram hash com segredo), **retenção curta**, **direitos do titular automatizados**.

| Dado | Finalidade | Base legal | Onde | Proteção | Retenção |
|---|---|---|---|---|---|
| E-mail | Identificar a conta, recuperar senha | Execução de contrato | `usuarios.email_norm` | Acesso só pela API; nunca em logs | Até excluir a conta |
| Nome | Exibir no app | Contrato | `usuarios.nome` | — | Até excluir a conta |
| Senha | Autenticar | Contrato | `usuarios.senha_hash` | **Argon2id**; nunca em texto, log ou exportação | Até excluir a conta |
| TOTP (MFA) | 2ª etapa | Segurança | `usuarios.mfa_segredo` | **Cifrado (Fernet)**; códigos de recuperação só em hash | Até desativar/excluir |
| Sessão (dispositivo, IP pseudonimizado) | Manter login, detectar acesso suspeito | Legítimo interesse/segurança | `sessoes` | Token só em hash SHA-256; IP só em HMAC truncado | Expira em 30 d (7 d ociosa); apagada com a conta |
| Favoritos | Personalização | Contrato | `favoritos_usuario` | Dono vem da sessão (sem IDOR) | Até excluir a conta |
| Trilha de auditoria | Prevenção a fraudes, segurança | Legítimo interesse | `auditoria` | Sem segredos, sem IP puro; ator = `usuario:<id>` | **12 meses** (job de limpeza: ver pendências) |
| Tokens de recuperação/verificação | Fluxos de e-mail | Contrato | `tokens_conta` | Só hash; expiram em 1–48 h; uso único | Apagados com a conta |
| **Localização** | Mostrar o que está perto | Consentimento (permissão do navegador) | **Somente no aparelho** | Nunca enviada nem guardada no servidor | — |
| **Câmera / QR da nota** | Validar experiência | Consentimento | Só no aparelho (leitura do QR) | O servidor recebe a chave e guarda apenas **hash** (`notas.py`) | Hash enquanto a conta existir |
| **Nota fiscal / CNPJ do estabelecimento** | — | — | **Não guardamos** | A chave de acesso contém o CNPJ: nunca é gravada nem logada | — |
| Fotos de perfil/experiência (futuro) | Perfil | Consentimento | Armazenamento isolado | `uploads.py`: reencoda e remove EXIF/GPS | Até excluir |
| Dados públicos coletados (lugares/eventos) | Guia | Interesse legítimo / dados públicos | `data/`, banco | Sem CNPJ, CPF, e-mail ou telefone pessoal (varredura a cada push) | Atualizados nas coletas |

## Direitos do titular (art. 18) — como são atendidos
- **Acesso/portabilidade**: `GET /conta/exportar` (JSON; exige senha recente). Botão em *Configurações → Seus dados*.
- **Correção**: `PATCH /conta/eu`, troca de e-mail (`/conta/email`) e de senha (`/conta/senha`).
- **Eliminação**: `DELETE /conta` (exige senha) apaga conta, sessões, tokens e favoritos; a trilha de segurança permanece pseudonimizada por até 12 meses.
- **Informação sobre tratamento**: política de privacidade no app (aba *Privacidade e termos*) e este documento.
- **Revogar consentimento**: negar permissão de localização/câmera no navegador; excluir a conta.
- **Portabilidade/oposição/outros**: encarregado de dados (a definir em `EMPRESA.encarregado`).

## Notas fiscais — política de retenção
O app lê o QR **no aparelho**. O servidor deve receber só a URL/chave; `app/seguranca/notas.py` valida o dígito verificador e devolve dois HMACs (nota e emitente) — **a nota completa, o PDF e o CNPJ não são armazenados**. Se algum dia for preciso guardar o arquivo (disputa), apague/anonimize após o prazo legal aplicável (decisão do jurídico/contador) e registre a base legal.

## Pendências de privacidade
1. Preencher no build: razão social, CNPJ **da empresa TURIZ**, endereço, contato, encarregado e prazo de remoção (o build de produção recusa se faltar).
2. **Revisão jurídica** dos textos (o build exige `--juridico-revisado`). Os textos são pontos de partida, não parecer jurídico.
3. Job de retenção: apagar `auditoria` > 12 meses e sessões expiradas > 90 dias (`DELETE ... WHERE quando < now() - interval '12 months'`).
4. Contratos de operador (hospedagem, e-mail) e avaliação de transferência internacional conforme o provedor escolhido.
5. Relatório de impacto (RIPD) se o tratamento de localização/notas crescer.
