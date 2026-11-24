"""Operações CRUD da coleção 'fornecedor' no MongoDB com validação e integridade referencial."""

from controller.controller_compra import (
    existe_documento,
    inteiro_positivo,
    verificar_permissao_escrita,
)
from model.fornecedor import Fornecedor


class ControllerFornecedor:
    COLECAO = "fornecedor"

    def __init__(self, banco=None, conexao=None):
        banco_efetivo = banco if banco is not None else conexao
        if banco_efetivo is None:
            from conexion.mongo_queries import ConexaoMongo
            banco_efetivo = ConexaoMongo(permite_escrita=True)
        self.banco = banco_efetivo

    def existe(self, id_fornecedor: int) -> bool:
        return existe_documento(self.banco, self.COLECAO, "id_fornecedor", id_fornecedor)

    @staticmethod
    def _validar(fornecedor: Fornecedor) -> dict:
        if not isinstance(fornecedor, Fornecedor):
            raise ValueError("Informe um objeto Fornecedor.")
        nome = (fornecedor.get_nome() or "").strip()
        if not nome or len(nome) > 120:
            raise ValueError("O nome do fornecedor deve ter entre 1 e 120 caracteres.")
        cnpj = (fornecedor.get_cnpj() or "").strip()
        if not cnpj or len(cnpj) > 14:
            raise ValueError("O CNPJ deve ser informado com até 14 caracteres.")
        telefone = (fornecedor.get_telefone() or "").strip() or None
        if telefone and len(telefone) > 20:
            raise ValueError("O telefone deve ter no máximo 20 caracteres.")
        email = (fornecedor.get_email() or "").strip() or None
        if email and len(email) > 120:
            raise ValueError("O email deve ter no máximo 120 caracteres.")
        return {
            "nome": nome,
            "cnpj": cnpj,
            "telefone": telefone,
            "email": email,
        }

    @staticmethod
    def _objeto(doc: dict) -> Fornecedor:
        cnpj = doc.get("cnpj")
        return Fornecedor(
            int(doc["id_fornecedor"]),
            doc.get("nome"),
            cnpj.strip() if isinstance(cnpj, str) else cnpj,
            doc.get("telefone"),
            doc.get("email"),
        )

    def inserir(self, fornecedor: Fornecedor) -> Fornecedor:
        verificar_permissao_escrita(self.banco)
        dados = self._validar(fornecedor)
        if fornecedor.get_id_fornecedor() is not None:
            raise ValueError("Um novo fornecedor deve ter id_fornecedor=None.")

        codigo = self.banco.obter_proximo_id(self.COLECAO, "id_fornecedor")
        try:
            db = self.banco.conectar()
            if db[self.COLECAO].find_one({"cnpj": dados["cnpj"]}):
                raise ValueError(f"Ja existe um fornecedor cadastrado com o CNPJ {dados['cnpj']}.")
            db[self.COLECAO].insert_one({"id_fornecedor": codigo, **dados})
        finally:
            self.banco.desconectar()

        fornecedor.set_id_fornecedor(codigo)
        return self.buscar(codigo)

    def listar(self) -> list:
        try:
            db = self.banco.conectar()
            docs = list(db[self.COLECAO].find({}, {"_id": 0}).sort("id_fornecedor", 1))
            return [self._objeto(doc) for doc in docs]
        finally:
            self.banco.desconectar()

    def buscar(self, id_fornecedor: int):
        inteiro_positivo(id_fornecedor, "Fornecedor")
        try:
            db = self.banco.conectar()
            doc = db[self.COLECAO].find_one({"id_fornecedor": id_fornecedor}, {"_id": 0})
            return self._objeto(doc) if doc else None
        finally:
            self.banco.desconectar()

    def atualizar(self, fornecedor: Fornecedor) -> Fornecedor:
        verificar_permissao_escrita(self.banco)
        dados = self._validar(fornecedor)
        codigo = inteiro_positivo(fornecedor.get_id_fornecedor(), "Fornecedor")
        try:
            db = self.banco.conectar()
            duplicado = db[self.COLECAO].find_one(
                {"cnpj": dados["cnpj"], "id_fornecedor": {"$ne": codigo}}
            )
            if duplicado:
                raise ValueError(f"Ja existe outro fornecedor com o CNPJ {dados['cnpj']}.")
            resultado = db[self.COLECAO].update_one({"id_fornecedor": codigo}, {"$set": dados})
            if resultado.matched_count == 0:
                raise ValueError("Fornecedor nao encontrado.")
        finally:
            self.banco.desconectar()
        return self.buscar(codigo)

    def excluir(self, id_fornecedor: int) -> bool:
        verificar_permissao_escrita(self.banco)
        inteiro_positivo(id_fornecedor, "Fornecedor")
        if not self.existe(id_fornecedor):
            raise ValueError("Fornecedor nao encontrado.")
        try:
            db = self.banco.conectar()
            compra_filha = db["compra"].find_one({"id_fornecedor": id_fornecedor}, {"id_compra": 1})
            if compra_filha:
                raise ValueError(
                    "Fornecedor possui compras vinculadas. Exclua as compras antes de remover o fornecedor."
                )
            resultado = db[self.COLECAO].delete_one({"id_fornecedor": id_fornecedor})
            if resultado.deleted_count == 0:
                raise ValueError("Fornecedor nao encontrado.")
            return True
        finally:
            self.banco.desconectar()
