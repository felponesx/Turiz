# Política de segurança do TURIZ

## Como reportar uma vulnerabilidade
Não abra uma issue pública com detalhes de exploração. Envie para **[definir o canal: e-mail de segurança do projeto]** ou use
*Security → Report a vulnerability* neste repositório (ative em *Settings → Code security → Private vulnerability reporting*).
Inclua: o que encontrou, como reproduzir e o impacto. Respondemos em até 5 dias úteis e corrigimos conforme a gravidade
(CRÍTICA/ALTA primeiro). Pesquisa de boa-fé, sem acessar dados de terceiros nem degradar o serviço, não será tratada como ameaça.

## O que está no repositório
Dados **públicos** coletados (lugares, eventos, imagens com crédito). O repositório NÃO contém dados de usuários, senhas, tokens nem
chaves de API; os segredos ficam em variáveis de ambiente/GitHub Secrets. A regra do projeto é: **nenhum CNPJ, CPF ou e-mail de
terceiros** em dados, API, banco ou GitHub (`scripts/verificar_privacidade.py` roda a cada push).

## Documentação
- Relatório da auditoria e status: [docs/seguranca/RELATORIO.md](docs/seguranca/RELATORIO.md)
- Resposta a incidentes (P0–P4): [docs/seguranca/resposta-a-incidentes.md](docs/seguranca/resposta-a-incidentes.md)
- Backups e recuperação: [docs/seguranca/recuperacao-de-desastres.md](docs/seguranca/recuperacao-de-desastres.md)
- Dados pessoais e LGPD: [docs/seguranca/dados-pessoais.md](docs/seguranca/dados-pessoais.md)
- Infraestrutura (WAF, anti-DDoS, banco, deploy): [docs/seguranca/infraestrutura.md](docs/seguranca/infraestrutura.md)
