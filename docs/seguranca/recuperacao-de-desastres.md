# Backups e recuperação de desastres

## O que precisa ser protegido
| Dado | Onde vive hoje | Reconstruível? |
|---|---|---|
| Lugares, eventos, imagens (referências), cardápios, redes | `data/*.json(.gz)` no Git (snapshot) + banco | **Sim**, a partir do snapshot (`python restaurar.py`) e das coletas |
| Fotos (miniaturas) | `data/fotos/`, `data/fotos_exemplo/` no Git | Sim (bot de fotos) |
| **Contas, sessões, favoritos, auditoria** | **Banco de produção** (ainda não existe hospedagem) | **Não** — só por backup do banco |
| Segredos (chaves, TOTP) | Variáveis de ambiente / GitHub Secrets | Não — guarde em gerenciador de segredos com cópia |

> Os snapshots no Git **nunca** contêm dados de usuários (há teste automatizado: `test_snapshot_nunca_inclui_contas_de_usuario`).

## Metas (RPO/RTO)
| Componente | RPO (perda máxima aceitável) | RTO (tempo para voltar) | Como |
|---|---|---|---|
| Dados públicos coletados | até 24 h (eventos: 6 h) | 1 h | Snapshot no Git + `restaurar.py` + workflow de coleta |
| Contas/sessões/favoritos (Postgres) | **15 min** | **4 h** | PITR do provedor (WAL/ponto no tempo) + backup diário lógico criptografado, em outra conta/região |
| Front estático | 0 (vem do Git) | 30 min | Rebuild com `build_producao.py` + deploy |

Se a hospedagem escolhida não oferecer PITR, o RPO real das contas sobe para o intervalo do backup (24 h): registre isso como risco aceito.

## O que já está implementado (e testado)
- `scripts/testar_restauracao.py`: reconstrói um banco do zero a partir de `data/`, confere contagens, `PRAGMA integrity_check` e chaves estrangeiras. **Executado com sucesso** (23.990 lugares e 71 eventos restaurados em ~14 s; ver relatório).
- Workflow **Backup e teste de restauração** (diário): roda o teste acima + varredura de privacidade; com o secret `BACKUP_PASSPHRASE` gera `turiz-backup-*.tar.gz.enc` (AES-256-CBC, PBKDF2 600 mil iterações, hash SHA-256) como artefato por 90 dias; com `BACKUP_S3_*` envia uma cópia para armazenamento **fora do GitHub**. Sem a senha, **nunca** gera cópia sem criptografia.
- Proteção do histórico: o Git guarda versões; ative proteção de branch contra *force-push* e exclusão (pendência manual).

## O que falta (depende de hospedagem/serviços)
1. Banco Postgres gerenciado com **PITR**, backups em outra região/conta e **usuário de backup somente leitura** (`postgres-roles.sql`).
2. Backup **imutável** (Object Lock/WORM ou versionamento + MFA delete) para sobreviver a ransomware/admin malicioso.
3. **Teste de restauração do Postgres** (mensal): restaurar num ambiente novo, subir a API e rodar `pytest tests/seguranca` + E2E. *Um backup só conta depois disso.*
4. Alertas de falha de backup (o workflow já falha e o GitHub avisa por e-mail; adicione `ALERTA_WEBHOOK`).

## Procedimentos
**Banco apagado/corrompido** — (1) pare a escrita (modo leitura/manutenção); (2) identifique o último ponto bom; (3) restaure o Postgres para um *novo* servidor no ponto escolhido; (4) `python -c "from app.migrar import upgrade_head; upgrade_head()"`; (5) `python restaurar.py` para repor os dados públicos que faltarem; (6) rode `scripts/testar_restauracao.py` e os testes; (7) troque a `DATABASE_URL`; (8) revogue sessões se houver suspeita de comprometimento; (9) relatório pós-incidente.

**Perda do servidor** — reimplante a API de um commit conhecido (CI verde), aponte para o banco restaurado, reaplique segredos do gerenciador.

**Erro de deploy / rollback** — reimplante o commit anterior (tag por release); as migrações são só aditivas (`downgrade` existe e foi testado em `test_migracoes.py`).

**Falha do provedor** — a API pode ser reimplantada em outro provedor em ~RTO usando o mesmo repositório e o backup externo.

**Comprometimento de administrador** — veja `resposta-a-incidentes.md`.
