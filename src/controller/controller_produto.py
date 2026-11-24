"""Operações CRUD da coleção 'produto' no MongoDB com validação e integridade referencial."""

from controller.controller_compra import (
    existe_documento,
    inteiro_nao_negativo,
    inteiro_positivo,
    verificar_permissao_escrita,
)
from controller.controller_item_compra import validar_decimal_positivo
from model.produto import Produto


class ControllerProduto:
    COLECAO = "produto"

    def __init__(self, banco=None, conexao=None):
        banco_efetivo = banco if banco is not None else conexao
        if banco_efetivo is None:
            from conexion.mongo_queries import ConexaoMongo
            banco_efetivo = ConexaoMongo(permite_escrita=True)
        self.banco = banco_efetivo

    def existe(self, id_produto: int) -> bool:
        return existe_documento(self.banco, self.COLECAO, "id_produto", id_produto)

    @staticmethod
    def _validar(produto: Produto) -> dict:
        if not isinstance(produto, Produto):
            raise ValueError("Informe um objeto Produto.")
        nome = (produto.get_nome() or "").strip()
        if not nome or len(nome) > 120:
            raise ValueError("O nome do produto deve ter entre 1 e 120 caracteres.")
        descricao = (produto.get_descricao() or "").strip() or None
        if descricao and len(descricao) > 255:
            raise ValueError("A descricao do produto deve ter no maximo 255 caracteres.")
        preco = validar_decimal_positivo(produto.get_preco_venda(), "Preco de venda")
        atual = inteiro_nao_negativo(produto.get_estoque_atual(), "Estoque atual")
        minimo = inteiro_nao_negativo(produto.get_estoque_minimo(), "Estoque minimo")
        return {
            "nome": nome,
            "descricao": descricao,
            "preco_venda": float(preco),
            "estoque_atual": atual,
            "estoque_minimo": minimo,
        }

    @staticmethod
    def _objeto(doc: dict) -> Produto:
        return Produto(
            int(doc["id_produto"]),
            doc.get("nome"),
            doc.get("descricao"),
            float(doc["preco_venda"]),
            int(doc["estoque_atual"]),
            int(doc["estoque_minimo"]),
        )

    def inserir(self, produto: Produto) -> Produto:
        verificar_permissao_escrita(self.banco)
        dados = self._validar(produto)
        if produto.get_id_produto() is not None:
            raise ValueError("Um novo produto deve ter id_produto=None.")

        codigo = self.banco.obter_proximo_id(self.COLECAO, "id_produto")
        try:
            db = self.banco.conectar()
            db[self.COLECAO].insert_one({"id_produto": codigo, **dados})
        finally:
            self.banco.desconectar()

        produto.set_id_produto(codigo)
        return self.buscar(codigo)

    def listar(self) -> list:
        try:
            db = self.banco.conectar()
            docs = list(db[self.COLECAO].find({}, {"_id": 0}).sort("id_produto", 1))
            return [self._objeto(doc) for doc in docs]
        finally:
            self.banco.desconectar()

    def buscar(self, id_produto: int):
        inteiro_positivo(id_produto, "Produto")
        try:
            db = self.banco.conectar()
            doc = db[self.COLECAO].find_one({"id_produto": id_produto}, {"_id": 0})
            return self._objeto(doc) if doc else None
        finally:
            self.banco.desconectar()

    def atualizar(self, produto: Produto) -> Produto:
        verificar_permissao_escrita(self.banco)
        dados = self._validar(produto)
        codigo = inteiro_positivo(produto.get_id_produto(), "Produto")
        try:
            db = self.banco.conectar()
            resultado = db[self.COLECAO].update_one({"id_produto": codigo}, {"$set": dados})
            if resultado.matched_count == 0:
                raise ValueError("Produto nao encontrado.")
        finally:
            self.banco.desconectar()
        return self.buscar(codigo)

    def excluir(self, id_produto: int) -> bool:
        verificar_permissao_escrita(self.banco)
        inteiro_positivo(id_produto, "Produto")
        if not self.existe(id_produto):
            raise ValueError("Produto nao encontrado.")
        try:
            db = self.banco.conectar()
            item_filho = db["item_compra"].find_one({"id_produto": id_produto}, {"id_item": 1})
            if item_filho:
                raise ValueError(
                    "Produto possui itens de compra vinculados. Exclua os itens antes de remover o produto."
                )
            resultado = db[self.COLECAO].delete_one({"id_produto": id_produto})
            if resultado.deleted_count == 0:
                raise ValueError("Produto nao encontrado.")
            return True
        finally:
            self.banco.desconectar()
