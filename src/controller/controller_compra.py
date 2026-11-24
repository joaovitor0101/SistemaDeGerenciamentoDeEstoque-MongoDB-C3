"""Operações CRUD da coleção 'compra' no MongoDB com validação e integridade referencial."""

from datetime import date, datetime
from model.compra import Compra
from model.fornecedor import Fornecedor


def inteiro_positivo(valor, campo: str) -> int:
    if isinstance(valor, bool) or not isinstance(valor, int) or valor <= 0:
        raise ValueError(f"{campo} deve ser um inteiro positivo.")
    return valor


def inteiro_nao_negativo(valor, campo: str) -> int:
    if isinstance(valor, bool) or not isinstance(valor, int) or valor < 0:
        raise ValueError(f"{campo} deve ser um inteiro maior ou igual a zero.")
    return valor


def verificar_permissao_escrita(banco):
    if not getattr(banco, "permite_escrita", False):
        raise PermissionError("A conexao precisa de permite_escrita=True.")


def converter_data(valor) -> date:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if isinstance(valor, str):
        texto = valor.strip()[:10]
        for formato in ("%Y-%m-%d", "%d/%m/%Y", "%m-%d-%Y"):
            try:
                return datetime.strptime(texto, formato).date()
            except ValueError:
                continue
    raise ValueError("Data da compra invalida.")


def existe_documento(banco, colecao: str, campo_id: str, codigo: int) -> bool:
    inteiro_positivo(codigo, campo_id)
    try:
        db = banco.conectar()
        doc = db[colecao].find_one({campo_id: codigo}, {campo_id: 1, "_id": 0})
        return doc is not None
    finally:
        banco.desconectar()


class ControllerCompra:
    COLECAO = "compra"

    def __init__(self, banco=None):
        if banco is None:
            from conexion.mongo_queries import ConexaoMongo
            banco = ConexaoMongo(permite_escrita=True)
        self.banco = banco

    def existe(self, id_compra: int) -> bool:
        return existe_documento(self.banco, self.COLECAO, "id_compra", id_compra)

    def _validar(self, compra: Compra) -> dict:
        if not isinstance(compra, Compra):
            raise ValueError("Informe um objeto Compra.")
        fornecedor = compra.get_fornecedor()
        if not isinstance(fornecedor, Fornecedor):
            raise ValueError("A compra precisa de um objeto Fornecedor.")
        codigo_fornecedor = inteiro_positivo(fornecedor.get_id_fornecedor(), "Fornecedor")
        if not existe_documento(self.banco, "fornecedor", "id_fornecedor", codigo_fornecedor):
            raise ValueError("Fornecedor nao encontrado.")

        data = compra.get_data_compra()
        if isinstance(data, datetime):
            data = data.date()
        if not isinstance(data, date):
            raise ValueError("Data da compra deve ser datetime.date.")

        status = compra.get_status()
        if not isinstance(status, str) or not status.strip() or len(status.strip()) > 12:
            raise ValueError("Status deve ter entre 1 e 12 caracteres.")

        return {
            "id_fornecedor": codigo_fornecedor,
            "data_compra": data.strftime("%Y-%m-%d"),
            "status": status.strip().upper(),
        }

    @staticmethod
    def _objeto(doc: dict) -> Compra:
        f_doc = doc.get("fornecedor_info") or {}
        cnpj = f_doc.get("cnpj")
        fornecedor = Fornecedor(
            f_doc.get("id_fornecedor", doc.get("id_fornecedor")),
            f_doc.get("nome"),
            cnpj.strip() if isinstance(cnpj, str) else cnpj,
            f_doc.get("telefone"),
            f_doc.get("email"),
        )
        return Compra(
            int(doc["id_compra"]),
            fornecedor,
            converter_data(doc["data_compra"]),
            doc["status"],
        )

    @staticmethod
    def _pipeline_consulta(filtro: dict = None) -> list:
        pipeline = []
        if filtro:
            pipeline.append({"$match": filtro})
        pipeline.extend([
            {
                "$lookup": {
                    "from": "fornecedor",
                    "localField": "id_fornecedor",
                    "foreignField": "id_fornecedor",
                    "as": "fornecedor_info",
                }
            },
            {"$unwind": "$fornecedor_info"},
            {"$sort": {"id_compra": 1}},
        ])
        return pipeline

    def inserir(self, compra: Compra) -> Compra:
        verificar_permissao_escrita(self.banco)
        dados = self._validar(compra)
        if compra.get_id_compra() is not None:
            raise ValueError("Uma nova compra deve ter id_compra=None.")

        codigo = self.banco.obter_proximo_id(self.COLECAO, "id_compra")
        documento = {"id_compra": codigo, **dados}
        try:
            db = self.banco.conectar()
            db[self.COLECAO].insert_one(documento)
        finally:
            self.banco.desconectar()

        compra.set_id_compra(codigo)
        return self.buscar(codigo)

    def listar(self, id_fornecedor: int = None) -> list:
        filtro = {}
        if id_fornecedor is not None:
            inteiro_positivo(id_fornecedor, "Fornecedor")
            filtro["id_fornecedor"] = id_fornecedor
        try:
            db = self.banco.conectar()
            docs = list(db[self.COLECAO].aggregate(self._pipeline_consulta(filtro)))
            return [self._objeto(doc) for doc in docs]
        finally:
            self.banco.desconectar()

    def buscar(self, id_compra: int):
        inteiro_positivo(id_compra, "Compra")
        try:
            db = self.banco.conectar()
            docs = list(db[self.COLECAO].aggregate(self._pipeline_consulta({"id_compra": id_compra})))
            return self._objeto(docs[0]) if docs else None
        finally:
            self.banco.desconectar()

    def atualizar(self, compra: Compra) -> Compra:
        verificar_permissao_escrita(self.banco)
        dados = self._validar(compra)
        codigo = inteiro_positivo(compra.get_id_compra(), "Compra")
        try:
            db = self.banco.conectar()
            resultado = db[self.COLECAO].update_one({"id_compra": codigo}, {"$set": dados})
            if resultado.matched_count == 0:
                raise ValueError("Compra nao encontrada.")
        finally:
            self.banco.desconectar()
        return self.buscar(codigo)

    def excluir(self, id_compra: int) -> bool:
        verificar_permissao_escrita(self.banco)
        inteiro_positivo(id_compra, "Compra")
        if not self.existe(id_compra):
            raise ValueError("Compra nao encontrada.")

        try:
            db = self.banco.conectar()
            item_filho = db["item_compra"].find_one({"id_compra": id_compra}, {"id_item": 1})
            if item_filho:
                raise ValueError("Compra possui itens. Exclua os itens antes de excluir a compra.")
            resultado = db[self.COLECAO].delete_one({"id_compra": id_compra})
            if resultado.deleted_count == 0:
                raise ValueError("Compra nao encontrada.")
            return True
        finally:
            self.banco.desconectar()
