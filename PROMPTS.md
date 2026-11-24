# Documentação de Transparência e Uso de IA Generativa (`PROMPTS.md`)

**Disciplina:** Banco de Dados (Semestre 2026/2)  
**Professor:** Prof. M.Sc. Howard Roatti  
**Projeto:** Sistema de Gerenciamento e Controle de Estoque (Migração Oracle → MongoDB)  

Este documento registra os prompts utilizados pelo grupo como apoio técnico ao desenvolvimento e adaptação do projeto da etapa relacional (C2 - Oracle) para o banco de dados não relacional **MongoDB** (C3), detalhando a ferramenta consultada e como o grupo aplicou os resultados.

---

## 1. Análise do Edital C3 (MongoDB) e Planejamento de Reuso da C2

- **Fonte / Ferramenta:** Google Antigravity (Modelo Gemini)
- **Data da Consulta:** 24/11/2026
- **Prompt Utilizado:**
  > *"Analise o edital do trabalho de MongoDB do professor Howard Roatti e verifique o que pode ser reaproveitado do nosso Sistema de Gerenciamento de Estoque feito em Oracle na C2 (FORNECEDOR, PRODUTO, COMPRA e ITEM_COMPRA) e o que precisa ser reescrito usando PyMongo."*
- **Aplicação pelo Grupo:**
  - Mantivemos o diagrama relacional (`diagrams/diagrama_relacional.png`) e as 4 classes da camada `src/model/`.
  - Planejamos a criação do módulo `src/conexion/mongo_queries.py`, do script de migração `src/create_collections_and_data.py` e a adaptação dos controllers, relatórios e splash screen para comandos nativos do MongoDB (`pymongo`).

---

## 2. Conexão com MongoDB e Script de Migração Oracle → MongoDB (Item 4 do Edital)

- **Fonte / Ferramenta:** Google Antigravity (Modelo Gemini)
- **Data da Consulta:** 24/11/2026
- **Prompt Utilizado:**
  > *"Implemente o módulo src/conexion/mongo_queries.py conectando ao MongoDB da VM (localhost:27017, banco labdatabase) via PyMongo e crie o script src/create_collections_and_data.py atendendo ao Item 4 do edital: conectar no Oracle, consultar as tabelas FORNECEDOR, PRODUTO, COMPRA e ITEM_COMPRA, criar as coleções correspondentes no MongoDB e inserir os documentos migrados."*
- **Aplicação pelo Grupo:**
  - Criamos a classe `ConexaoMongo` com suporte ao arquivo `src/conexion/passphrase/authentication.mongo`, contagem de documentos (`count_documents`) e geração sequencial de IDs via agregação (`$max + 1`).
  - Criamos o script `src/create_collections_and_data.py` que lê os registros do Oracle com `ConexaoOracle`, normaliza os tipos de dados e popula as coleções `fornecedor`, `produto`, `compra` e `item_compra` no MongoDB com `insert_many`.

---

## 3. Adaptação dos Controllers para Comandos Nativos do MongoDB

- **Fonte / Ferramenta:** Google Antigravity (Modelo Gemini)
- **Data da Consulta:** 24/11/2026
- **Prompt Utilizado:**
  > *"Reescreva os 4 controllers (controller_fornecedor.py, controller_produto.py, controller_compra.py e controller_item_compra.py) substituindo as queries SQL pelos métodos nativos do PyMongo (insert_one, find, find_one, update_one, delete_one e aggregate com $lookup), mantendo todas as validações e a verificação de documentos referenciados nas coleções filhas antes da exclusão."*
- **Aplicação pelo Grupo:**
  - Substituímos todas as instruções SQL por operações de documentos no MongoDB, preservando a assinatura dos métodos (`inserir`, `listar`, `buscar`, `atualizar`, `excluir`, `existe`) e o retorno das instâncias associadas de `Fornecedor`, `Produto`, `Compra` e `ItemCompra`.

---

## 4. Relatórios com Aggregation Pipeline (`$group` e `$lookup`), Splash Screen e Testes

- **Fonte / Ferramenta:** Google Antigravity (Modelo Gemini)
- **Data da Consulta:** 24/11/2026
- **Prompt Utilizado:**
  > *"Adapte src/reports/relatorios.py para gerar os relatórios diretamente no MongoDB usando pipelines de agregação ($lookup, $unwind, $group, $project e $sort) para sumarização de compras por fornecedor, junção de itens de compra, estoque baixo e relatórios individuais. Atualize também o splash_screen.py para contar documentos nas coleções do MongoDB e adapte os testes automatizados."*
- **Aplicação pelo Grupo:**
  - Implementamos os pipelines de agregação em `src/reports/relatorios.py` exibindo os resultados em `pandas.DataFrame`, atualizamos `src/utils/splash_screen.py` e `src/principal.py` e validamos todas as operações com a suíte `tests/test_controllers.py`.

---

## 5. Revisão local da Parte 3 — Compra, Item de Compra e Testes

- **Fonte / Ferramenta:** ChatGPT/Codex.
- **Data da consulta:** 24/11/2026.
- **Integrante:** Miguel Gomes Silveira (`miguelgomessilveira7-cmd`).
- **Solicitações:** revisar a parte atribuída ao integrante e preparar localmente os controllers de compra e item de compra e os testes para MongoDB, seguindo o fluxo de validação utilizado na C2. Esta descrição é uma síntese dos pedidos da conversa.
- **Aplicação do apoio:** a revisão partiu das versões já publicadas pelo grupo. Foram mantidos os métodos públicos e os pipelines com `$lookup`, acrescentando verificação de colisão do ID gerado antes da inclusão e corrigindo a conversão de datas para rejeitar texto inválido após a data, preservando suporte a datas ISO e aos formatos já utilizados.
- **Testes acrescentados:** validação de datas e status, IDs gerados duplicados, alteração das associações, filtros combinados e fechamento da conexão após falha simulada de gravação. Também foram preparados dois testes opcionais com MongoDB real, para CRUD, agregação `$lookup`, referências inexistentes e bloqueio da exclusão de compra com itens.
- **Validação local:** 15 testes passaram; os dois testes de integração foram ignorados por padrão, pois não foi conectado um servidor MongoDB nesta execução. Os testes locais utilizam a implementação em memória já existente no projeto. Não comprovam o funcionamento na VM.

- **Validação na VM (24/11/2026):** a suíte executou no Ubuntu da VM LabDatabase com Python 3.12 e MongoDB real em contêiner. Os 17 testes passaram, sem testes ignorados, incluindo os dois de integração de compra e item de compra. Foram confirmados CRUD, associações com `$lookup`, validação de referências, bloqueio de exclusão da compra com itens e preservação do estoque. Os bancos temporários foram removidos ao final (nenhum restante). Essa execução valida os controllers nos cenários testados; não equivale a testar todo o menu interativo ou a migração completa do grupo.

### Como executar os testes

Na raiz do projeto, com o ambiente Python e as dependências de `requirements.txt` instalados:

```sh
python -m unittest discover -s tests -v
```

Para validar no MongoDB real da VM, informar em `MONGO_TEST_URI` a URI de conexão do ambiente e ativar os testes de integração:

```sh
export RUN_MONGO_INTEGRATION=1
read -r -s -p "URI do MongoDB de teste: " MONGO_TEST_URI
echo
export MONGO_TEST_URI
python -m unittest discover -s tests -v
unset RUN_MONGO_INTEGRATION MONGO_TEST_URI
```

Os testes reais criam um banco com nome exclusivo iniciado por `teste_c3_parte3_`, inserem seus próprios documentos e removem somente esse banco ao terminar. O usuário da conexão precisa de permissão para criar e remover esse banco temporário. Não é necessário executar o script de migração nem recriar as coleções de trabalho para rodar esses testes.

A checagem adicional de ID evita inserir um ID já presente no momento da consulta. A estratégia compartilhada de geração por `$max + 1` permanece a do grupo e não assegura unicidade em inclusões simultâneas. A conexão, a migração, os controllers de fornecedor e produto e o menu não foram alterados nesta revisão. Após a validação na VM, o integrante autorizou criar o commit e enviar estes quatro arquivos ao repositório do grupo.
