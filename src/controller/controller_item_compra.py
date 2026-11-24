"""Operações CRUD da coleção 'item_compra' no MongoDB com agregação $lookup."""

from decimal import Decimal, InvalidOperation
from controller.controller_compra import (
    converter_data,
    existe_documento,
    inteiro_positivo,
    verificar_permissao_escrita,
)
from model.compra import Compra
from model.fornecedor import Fornecedor
from model.item_compra import ItemCompra
from model.produto import Produto


def validar_decimal_positivo(valor, campo: str = "Preco") -> Decimal:
    try:
        if isinstance(valor, bool):
            raise ValueError(f"{campo} invalido.")
        preco = Decimal(str(valor))
        if (
            not preco.is_finite()
            or preco <= 0
            or preco > Decimal("99999999.99")
            or preco != preco.quantize(Decimal("0.01"))
        ):
            raise ValueError(f"{campo} deve ser positivo e ter no maximo duas casas decimais.")
        return preco
    except (InvalidOperation, TypeError, ValueError) as erro:
        raise ValueError(f"{campo} invalido para valor monetario.") from erro


class ControllerItemCompra:
    COLECAO = "item_compra"

    def __init__(self, banco=None):
        if banco is None:
            from conexion.mongo_queries import ConexaoMongo
            banco = ConexaoMongo(permite_escrita=True)
        self.banco = banco

    def existe(self, id_item: int) -> bool:
        return existe_documento(self.banco, self.COLECAO, "id_item", id_item)

    def _validar(self, item: ItemCompra) -> dict:
        if not isinstance(item, ItemCompra):
            raise ValueError("Informe um objeto ItemCompra.")
        if not isinstance(item.get_compra(), Compra):
            raise ValueError("O item precisa de um objeto Compra.")
        if not isinstance(item.get_produto(), Produto):
            raise ValueError("O item precisa de um objeto Produto.")

        id_compra = inteiro_positivo(item.get_compra().get_id_compra(), "Compra")
        id_produto = inteiro_positivo(item.get_produto().get_id_produto(), "Produto")
        if not existe_documento(self.banco, "compra", "id_compra", id_compra):
            raise ValueError("Compra nao encontrada.")
        if not existe_documento(self.banco, "produto", "id_produto", id_produto):
            raise ValueError("Produto nao encontrado.")

        quantidade = inteiro_positivo(item.get_quantidade(), "Quantidade")
        preco = validar_decimal_positivo(item.get_preco_unitario(), "Preco")
        return {
            "id_compra": id_compra,
            "id_produto": id_produto,
            "quantidade": quantidade,
            "preco_unitario": float(preco),
        }

    @staticmethod
    def _pipeline_consulta(filtro: dict = None) -> list:
        pipeline = []
        if filtro:
            pipeline.append({"$match": filtro})
        pipeline.extend([
            {
                "$lookup": {
                    "from": "compra",
                    "localField": "id_compra",
                    "foreignField": "id_compra",
                    "as": "compra_info",
                }
            },
            {"$unwind": "$compra_info"},
            {
                "$lookup": {
                    "from": "fornecedor",
                    "localField": "compra_info.id_fornecedor",
                    "foreignField": "id_fornecedor",
                    "as": "fornecedor_info",
                }
            },
            {"$unwind": "$fornecedor_info"},
            {
                "$lookup": {
                    "from": "produto",
                    "localField": "id_produto",
                    "foreignField": "id_produto",
                    "as": "produto_info",
                }
            },
            {"$unwind": "$produto_info"},
            {"$sort": {"id_item": 1}},
        ])
        return pipeline

    @staticmethod
    def _objeto(doc: dict) -> ItemCompra:
        f_doc = doc["fornecedor_info"]
        c_doc = doc["compra_info"]
        p_doc = doc["produto_info"]
        cnpj = f_doc.get("cnpj")

        fornecedor = Fornecedor(
            int(f_doc["id_fornecedor"]),
            f_doc.get("nome"),
            cnpj.strip() if isinstance(cnpj, str) else cnpj,
            f_doc.get("telefone"),
            f_doc.get("email"),
        )
        compra = Compra(
            int(c_doc["id_compra"]),
            fornecedor,
            converter_data(c_doc["data_compra"]),
            c_doc.get("status"),
        )
        produto = Produto(
            int(p_doc["id_produto"]),
            p_doc.get("nome"),
            p_doc.get("descricao"),
            float(p_doc["preco_venda"]),
            int(p_doc["estoque_atual"]),
            int(p_doc["estoque_minimo"]),
        )
        return ItemCompra(
            int(doc["id_item"]),
            compra,
            produto,
            int(doc["quantidade"]),
            float(doc["preco_unitario"]),
        )

    def inserir(self, item: ItemCompra) -> ItemCompra:
        verificar_permissao_escrita(self.banco)
        dados = self._validar(item)
        if item.get_id_item() is not None:
            raise ValueError("Um novo item deve ter id_item=None.")

        codigo = self.banco.obter_proximo_id(self.COLECAO, "id_item")
        try:
            db = self.banco.conectar()
            db[self.COLECAO].insert_one({"id_item": codigo, **dados})
        finally:
            self.banco.desconectar()

        item.set_id_item(codigo)
        return self.buscar(codigo)

    def listar(self, id_compra: int = None, id_produto: int = None) -> list:
        filtro = {}
        if id_compra is not None:
            inteiro_positivo(id_compra, "Compra")
            filtro["id_compra"] = id_compra
        if id_produto is not None:
            inteiro_positivo(id_produto, "Produto")
            filtro["id_produto"] = id_produto

        try:
            db = self.banco.conectar()
            docs = list(db[self.COLECAO].aggregate(self._pipeline_consulta(filtro)))
            return [self._objeto(doc) for doc in docs]
        finally:
            self.banco.desconectar()

    def buscar(self, id_item: int):
        inteiro_positivo(id_item, "Item")
        try:
            db = self.banco.conectar()
            docs = list(db[self.COLECAO].aggregate(self._pipeline_consulta({"id_item": id_item})))
            return self._objeto(docs[0]) if docs else None
        finally:
            self.banco.desconectar()

    def atualizar(self, item: ItemCompra) -> ItemCompra:
        verificar_permissao_escrita(self.banco)
        dados = self._validar(item)
        codigo = inteiro_positivo(item.get_id_item(), "Item")
        try:
            db = self.banco.conectar()
            resultado = db[self.COLECAO].update_one({"id_item": codigo}, {"$set": dados})
            if resultado.matched_count == 0:
                raise ValueError("Item de compra nao encontrado.")
        finally:
            self.banco.desconectar()
        return self.buscar(codigo)

    def excluir(self, id_item: int) -> bool:
        verificar_permissao_escrita(self.banco)
        inteiro_positivo(id_item, "Item")
        try:
            db = self.banco.conectar()
            resultado = db[self.COLECAO].delete_one({"id_item": id_item})
            if resultado.deleted_count == 0:
                raise ValueError("Item de compra nao encontrado.")
            return True
        finally:
            self.banco.desconectar()
