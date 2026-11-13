# Sondagem de dados abertos

Gerado em 2026-11-13 20:21 (UTC). Amostras sem dados reais (dígitos=#, letras=x).

| Fonte | Resultado | Tamanho | Observação |
Pasta mais recente da Receita: **2026-10**

|---|---|---|---|
| Receita: Estabelecimentos0 | ok | 2277696710 | HTTP 206, aceita Range |
| Receita: Empresas0 | ok | 570972127 | HTTP 206, aceita Range |
| Receita: Simples | ok | 310608217 | HTTP 206, aceita Range |
| IBGE: CNEFE 2022 - SP | ok | 1082015432 | HTTP 206, aceita Range |

### Receita: Estabelecimentos0

- 1º arquivo do zip: `K3241.K03200Y0.D61010.ESTABELE`
- colunas (separador `;`): 30
- forma da linha 0: `"########";"####";"##";"#";"";"##";"########";"##";"";"";"########";"#######";"#######";"xxx";"xxxx xxxxxxxx xx xxxxxxxx";"###";"";"xxxxxxxx xxxxxxx xxxxxxxx";"########";"xx";"####";"##";"########";"";"";"";"";"xxxxxxxxxxx###@xxxxx.xxx";"";""`
- forma da linha 1: `"########";"####";"##";"#";"xxxxxxxxxx xx xxxxxxxx xxxxxxxxxxx xxxxxxxx ###";"##";"########";"##";"";"";"########";"#######";"";"xxx";"xxxxxxxx";"###";"";"xxxxxxx";"########";"xx";"####";"##";"########";"";"";"";"";"xxxxxxxxx@xxxxxxxxxxxxxx.xxx.xx";"";""`

### Receita: Empresas0

- 1º arquivo do zip: `K3241.K03200Y0.D61010.EMPRECSV`
- colunas (separador `;`): 7
- forma da linha 0: `"########";"xxxxxxxx xxxxxxxx xxxxx ###########";"####";"##";"####,##";"##";""`
- forma da linha 1: `"########";"xxxxx xxx xxxxxx xxxxxx xxxxx";"####";"##";"#,##";"##";""`

### Receita: Simples

- 1º arquivo do zip: `F.K03200$W.SIMPLES.CSV.D61010`
- colunas (separador `;`): 7
- forma da linha 0: `"########";"x";"########";"########";"x";"########";"########"`
- forma da linha 1: `"########";"x";"########";"########";"x";"########";"########"`

### IBGE: CNEFE 2022 - SP

- 1º arquivo do zip: `35_SP.csv`
- colunas (separador `;`): 34
- cabeçalho: `COD_UNICO_ENDERECO;COD_UF;COD_MUNICIPIO;COD_DISTRITO;COD_SUBDISTRITO;COD_SETOR;NUM_QUADRA;NUM_FACE;CEP;DSC_LOCALIDADE;NOM_TIPO_SEGLOGR;NOM_TITULO_SEGLOGR;NOM_SEGLOGR;NUM_ENDERECO;DSC_MODIFICADOR;NOM_COMP_ELEM1;VAL_COMP_ELEM1;NOM_COMP_ELEM2;VAL_COMP_ELEM2;NOM_COMP_ELEM3;VAL_COMP_ELEM3;NOM_COMP_ELEM4;VAL_COMP_ELEM4;NOM_COMP_ELEM5;VAL_COMP_ELEM5;LATITUDE;LONGITUDE;NV_GEO_COORD;COD_ESPECIE;DSC_ESTABELECIMENTO;COD_INDICADOR_ESTAB_ENDERECO;COD_INDICADOR_CONST_ENDERECO;COD_INDICADOR_FINALIDADE_CONST;COD_TIPO_ESPECI`
- forma da linha 0: `xxx_xxxxx_xxxxxxxx;xxx_xx;xxx_xxxxxxxxx;xxx_xxxxxxxx;xxx_xxxxxxxxxxx;xxx_xxxxx;xxx_xxxxxx;xxx_xxxx;xxx;xxx_xxxxxxxxxx;xxx_xxxx_xxxxxxx;xxx_xxxxxx_xxxxxxx;xxx_xxxxxxx;xxx_xxxxxxxx;xxx_xxxxxxxxxxx;xxx_xxxx_xxxx#;xxx_xxxx_xxxx#;xxx_xxxx_xxxx#;xxx_xxxx_xxxx#;xxx_x`
- forma da linha 1: `#########;##;#######;#########;###########;###############x;#;#;########;xxxxxx;xxx;;xxxx xxxxxxx xxxxxxx;##;;xxxxxxx;##;;;;;;;;;-##.######;-##.######;#;#;;;#;#;`

## Tabelas de referência

### Municipios.zip (linhas com 'SAO PAULO')

- `"0275";"SAO PAULO DE OLIVENCA"`
- `"1849";"SAO PAULO DO POTENGI"`
- `"7107";"SAO PAULO"`
- `"8889";"SAO PAULO DAS MISSOES"`

### Cnaes.zip (linhas com '5611')

- `"5611201";"Restaurantes e similares"`
- `"5611202";"Bares e outros estabelecimentos especializados em servir bebidas"`
- `"5611203";"Lanchonetes, casas de chá, de sucos e similares"`
- `"5611204";"Bares e outros estabelecimentos especializados em servir bebidas, sem entretenimento"`
- `"5611205";"Bares e outros estabelecimentos especializados em servir bebidas, com entretenimento"`
