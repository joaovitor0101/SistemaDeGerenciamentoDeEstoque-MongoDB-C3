"""Execução e apresentação dos relatórios do sistema no MongoDB via Aggregation Pipelines."""

import sys
import pandas as pd


class Relatorio:
    """Executa consultas analíticas e listagens nas coleções do MongoDB."""

    def __init__(self, conexao=None, saida=None):
        if conexao is None:
            from conexion.mongo_queries import ConexaoMongo
            conexao = ConexaoMongo(permite_escrita=False)
        self.conexao = conexao
        self.saida = saida if saida is not None else sys.stdout

    def _exibir_dataframe(self, titulo: str, registros: list, colunas: list = None):
        print(f"\n=== {titulo} ===", file=self.saida)
        if not registros:
            print("A consulta não retornou documentos.", file=self.saida)
            return
        df = pd.DataFrame(registros)
        if colunas:
            colunas_presentes = [c for c in colunas if c in df.columns]
            df = df[colunas_presentes]
        print(df.to_string(index=False), file=self.saida)

    def get_relatorio_compras_por_fornecedor(self):
        """
        Item 7.a.1.i: Relatório com sumarização/agrupamento ($lookup + $group)
        calculando quantidade de compras e valor total comprado por fornecedor.
        """
        pipeline = [
            {
                "$lookup": {
                    "from": "compra",
                    "localField": "id_fornecedor",
                    "foreignField": "id_fornecedor",
                    "as": "compras",
                }
            },
            {"$unwind": {"path": "$compras", "preserveNullAndEmptyArrays": True}},
            {
                "$lookup": {
                    "from": "item_compra",
                    "localField": "compras.id_compra",
                    "foreignField": "id_compra",
                    "as": "itens",
                }
            },
            {"$unwind": {"path": "$itens", "preserveNullAndEmptyArrays": True}},
            {
                "$group": {
                    "_id": {"id_fornecedor": "$id_fornecedor", "nome": "$nome"},
                    "compras_ids": {"$addToSet": "$compras.id_compra"},
                    "valor_total_compras": {
                        "$sum": {
                            "$multiply": [
                                {"$ifNull": ["$itens.quantidade", 0]},
                                {"$ifNull": ["$itens.preco_unitario", 0]},
                            ]
                        }
                    },
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "nome_fornecedor": "$_id.nome",
                    "quantidade_compras": {"$size": "$compras_ids"},
                    "valor_total_compras": {"$round": ["$valor_total_compras", 2]},
                }
            },
            {"$sort": {"nome_fornecedor": 1}},
        ]
        try:
            db = self.conexao.conectar()
            registros = list(db["fornecedor"].aggregate(pipeline))
            self._exibir_dataframe(
                "Relatório de Compras por Fornecedor (Sumarização - $group)",
                registros,
                ["nome_fornecedor", "quantidade_compras", "valor_total_compras"],
            )
        except Exception as erro:
            print(f"Falha ao executar o relatório: {erro}", file=self.saida)
        finally:
            self.conexao.desconectar()

    def get_relatorio_itens_compra(self):
        """
        Item 7.a.1.ii: Relatório com junção de coleções ($lookup + $unwind)
        unindo item_compra, compra, fornecedor e produto.
        """
        pipeline = [
            {
                "$lookup": {
                    "from": "compra",
                    "localField": "id_compra",
                    "foreignField": "id_compra",
                    "as": "compra",
                }
            },
            {"$unwind": "$compra"},
            {
                "$lookup": {
                    "from": "fornecedor",
                    "localField": "compra.id_fornecedor",
                    "foreignField": "id_fornecedor",
                    "as": "fornecedor",
                }
            },
            {"$unwind": "$fornecedor"},
            {
                "$lookup": {
                    "from": "produto",
                    "localField": "id_produto",
                    "foreignField": "id_produto",
                    "as": "produto",
                }
            },
            {"$unwind": "$produto"},
            {
                "$project": {
                    "_id": 0,
                    "id_compra": "$compra.id_compra",
                    "data_compra": "$compra.data_compra",
                    "nome_fornecedor": "$fornecedor.nome",
                    "nome_produto": "$produto.nome",
                    "quantidade_comprada": "$quantidade",
                    "preco_unitario": "$preco_unitario",
                    "valor_total_item": {
                        "$round": [{"$multiply": ["$quantidade", "$preco_unitario"]}, 2]
                    },
                    "id_produto": "$produto.id_produto",
                    "id_item": "$id_item",
                }
            },
            {"$sort": {"id_compra": 1, "id_produto": 1, "id_item": 1}},
        ]
        try:
            db = self.conexao.conectar()
            registros = list(db["item_compra"].aggregate(pipeline))
            self._exibir_dataframe(
                "Relatório Detalhado de Itens de Compra (Junção - $lookup)",
                registros,
                [
                    "id_compra",
                    "data_compra",
                    "nome_fornecedor",
                    "nome_produto",
                    "quantidade_comprada",
                    "preco_unitario",
                    "valor_total_item",
                ],
            )
        except Exception as erro:
            print(f"Falha ao executar o relatório: {erro}", file=self.saida)
        finally:
            self.conexao.desconectar()

    def get_relatorio_estoque_baixo(self):
        """Exibe os produtos com estoque_atual <= estoque_minimo no MongoDB."""
        pipeline = [
            {"$match": {"$expr": {"$lte": ["$estoque_atual", "$estoque_minimo"]}}},
            {
                "$project": {
                    "_id": 0,
                    "id_produto": 1,
                    "nome_produto": "$nome",
                    "estoque_atual": 1,
                    "estoque_minimo": 1,
                    "deficit_reposicao": {"$subtract": ["$estoque_minimo", "$estoque_atual"]},
                    "preco_venda": 1,
                }
            },
            {"$sort": {"deficit_reposicao": -1, "nome_produto": 1}},
        ]
        try:
            db = self.conexao.conectar()
            registros = list(db["produto"].aggregate(pipeline))
            self._exibir_dataframe(
                "Relatório de Produtos com Estoque Baixo",
                registros,
                [
                    "id_produto",
                    "nome_produto",
                    "estoque_atual",
                    "estoque_minimo",
                    "deficit_reposicao",
                    "preco_venda",
                ],
            )
        except Exception as erro:
            print(f"Falha ao executar o relatório: {erro}", file=self.saida)
        finally:
            self.conexao.desconectar()

    def get_relatorio_fornecedores(self):
        """Lista isoladamente todos os documentos da coleção 'fornecedor'."""
        try:
            db = self.conexao.conectar()
            docs = list(db["fornecedor"].find({}, {"_id": 0}).sort("id_fornecedor", 1))
            registros = [
                {
                    "id_fornecedor": d.get("id_fornecedor"),
                    "nome_fornecedor": d.get("nome"),
                    "cnpj": str(d.get("cnpj") or "").strip(),
                    "telefone": d.get("telefone") or "-",
                    "email": d.get("email") or "-",
                }
                for d in docs
            ]
            self._exibir_dataframe(
                "Relatório de Fornecedores Cadastrados",
                registros,
                ["id_fornecedor", "nome_fornecedor", "cnpj", "telefone", "email"],
            )
        except Exception as erro:
            print(f"Falha ao executar o relatório: {erro}", file=self.saida)
        finally:
            self.conexao.desconectar()

    def get_relatorio_produtos(self):
        """Lista isoladamente todos os documentos da coleção 'produto'."""
        try:
            db = self.conexao.conectar()
            docs = list(db["produto"].find({}, {"_id": 0}).sort("id_produto", 1))
            registros = [
                {
                    "id_produto": d.get("id_produto"),
                    "nome_produto": d.get("nome"),
                    "descricao": d.get("descricao") or "-",
                    "preco_venda": d.get("preco_venda"),
                    "estoque_atual": d.get("estoque_atual"),
                    "estoque_minimo": d.get("estoque_minimo"),
                }
                for d in docs
            ]
            self._exibir_dataframe(
                "Relatório de Produtos Cadastrados",
                registros,
                [
                    "id_produto",
                    "nome_produto",
                    "descricao",
                    "preco_venda",
                    "estoque_atual",
                    "estoque_minimo",
                ],
            )
        except Exception as erro:
            print(f"Falha ao executar o relatório: {erro}", file=self.saida)
        finally:
            self.conexao.desconectar()

    def get_relatorio_compras(self):
        """Lista isoladamente todas as compras registradas na coleção 'compra'."""
        pipeline = [
            {
                "$lookup": {
                    "from": "fornecedor",
                    "localField": "id_fornecedor",
                    "foreignField": "id_fornecedor",
                    "as": "fornecedor",
                }
            },
            {"$unwind": {"path": "$fornecedor", "preserveNullAndEmptyArrays": True}},
            {
                "$project": {
                    "_id": 0,
                    "id_compra": 1,
                    "id_fornecedor": 1,
                    "nome_fornecedor": {"$ifNull": ["$fornecedor.nome", "-"]},
                    "data_compra": 1,
                    "status": 1,
                }
            },
            {"$sort": {"id_compra": 1}},
        ]
        try:
            db = self.conexao.conectar()
            registros = list(db["compra"].aggregate(pipeline))
            self._exibir_dataframe(
                "Relatório de Compras Registradas",
                registros,
                ["id_compra", "id_fornecedor", "nome_fornecedor", "data_compra", "status"],
            )
        except Exception as erro:
            print(f"Falha ao executar o relatório: {erro}", file=self.saida)
        finally:
            self.conexao.desconectar()
