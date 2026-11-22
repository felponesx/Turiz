-- Papéis de mínimo privilégio para o TURIZ (PostgreSQL). Rode como superusuário/dono do banco, UMA vez, e troque as senhas
-- (use um gerenciador de segredos; nunca versione senhas reais). Ajuste "turiz" para o nome do banco.
CREATE ROLE turiz_migrador LOGIN PASSWORD 'TROCAR-1' NOSUPERUSER NOCREATEDB NOCREATEROLE;
CREATE ROLE turiz_app      LOGIN PASSWORD 'TROCAR-2' NOSUPERUSER NOCREATEDB NOCREATEROLE CONNECTION LIMIT 40;
CREATE ROLE turiz_leitura  LOGIN PASSWORD 'TROCAR-3' NOSUPERUSER NOCREATEDB NOCREATEROLE CONNECTION LIMIT 5;
CREATE ROLE turiz_backup   LOGIN PASSWORD 'TROCAR-4' NOSUPERUSER NOCREATEDB NOCREATEROLE CONNECTION LIMIT 2;

REVOKE ALL ON DATABASE turiz FROM PUBLIC;
GRANT CONNECT ON DATABASE turiz TO turiz_migrador, turiz_app, turiz_leitura, turiz_backup;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA public TO turiz_migrador;           -- só o migrador altera o esquema (Alembic)
GRANT USAGE ON SCHEMA public TO turiz_app, turiz_leitura, turiz_backup;

-- o migrador é DONO dos objetos; os demais recebem só o que precisam
ALTER DEFAULT PRIVILEGES FOR ROLE turiz_migrador IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO turiz_app;
ALTER DEFAULT PRIVILEGES FOR ROLE turiz_migrador IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO turiz_app;
ALTER DEFAULT PRIVILEGES FOR ROLE turiz_migrador IN SCHEMA public GRANT SELECT ON TABLES TO turiz_leitura, turiz_backup;

-- dados de usuário NÃO ficam visíveis ao papel de leitura/BI
-- (rode depois de criar as tabelas)
-- REVOKE ALL ON usuarios, sessoes, tokens_conta, favoritos_usuario, auditoria FROM turiz_leitura;

-- limites de segurança por papel
ALTER ROLE turiz_app     SET statement_timeout = '10s';
ALTER ROLE turiz_app     SET idle_in_transaction_session_timeout = '15s';
ALTER ROLE turiz_leitura SET statement_timeout = '60s';
ALTER ROLE turiz_app     SET default_transaction_read_only = off;
-- A API deve usar DATABASE_URL com o papel turiz_app; o deploy roda `upgrade_head()` com turiz_migrador.
-- Exija TLS no pg_hba.conf:   hostssl  turiz  all  10.0.0.0/8  scram-sha-256
