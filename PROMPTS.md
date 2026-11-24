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
