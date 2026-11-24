"""Testes automatizados do CRUD MongoDB nas 4 coleções, integridade referencial, SplashScreen e Relatórios."""

import copy
import io
import sys
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from controller.controller_compra import ControllerCompra
from controller.controller_fornecedor import ControllerFornecedor
from controller.controller_item_compra import ControllerItemCompra
from controller.controller_produto import ControllerProduto
from create_collections_and_data import (
    DADOS_INICIAIS_PADRAO,
    _normalizar_documento,
    criar_colecoes,
)
from model.compra import Compra
from model.fornecedor import Fornecedor
from model.item_compra import ItemCompra
from model.produto import Produto
from reports.relatorios import Relatorio
from utils.splash_screen import SplashScreen


class _ResultadoUpdate:
    def __init__(self, matched_count: int, modified_count: int):
        self.matched_count = matched_count
        self.modified_count = modified_count


class _ResultadoDelete:
    def __init__(self, deleted_count: int):
        self.deleted_count = deleted_count


class _CursorMemoria(list):
    def sort(self, chave, direcao=1):
        reverso = direcao < 0
        ordenado = sorted(self, key=lambda d: d.get(chave), reverse=reverso)
        return _CursorMemoria(ordenado)


def _obter_caminho(doc: dict, caminho: str):
    atual = doc
    for parte in caminho.split("."):
        if not isinstance(atual, dict):
            return None
        atual = atual.get(parte)
    return atual


def _avaliar_expr(doc: dict, expr):
    if isinstance(expr, str) and expr.startswith("$"):
        return _obter_caminho(doc, expr[1:])
    if not isinstance(expr, dict):
        return expr
    if "$ifNull" in expr:
        alvo, padrao = expr["$ifNull"]
        val = _avaliar_expr(doc, alvo)
        return padrao if val is None else val
    if "$multiply" in expr:
        a, b = expr["$multiply"]
        return (_avaliar_expr(doc, a) or 0) * (_avaliar_expr(doc, b) or 0)
    if "$subtract" in expr:
        a, b = expr["$subtract"]
        return (_avaliar_expr(doc, a) or 0) - (_avaliar_expr(doc, b) or 0)
    if "$add" in expr:
        a, b = expr["$add"]
        va = _avaliar_expr(doc, a)
        vb = _avaliar_expr(doc, b)
        return None if va is None or vb is None else va + vb
    if "$round" in expr:
        alvo, casas = expr["$round"]
        return round(float(_avaliar_expr(doc, alvo) or 0), casas)
    if "$size" in expr:
        lista = _avaliar_expr(doc, expr["$size"]) or []
        return len(lista)
    if "$lte" in expr:
        a, b = expr["$lte"]
        return _avaliar_expr(doc, a) <= _avaliar_expr(doc, b)
    return expr


def _combina_filtro(doc: dict, filtro: dict) -> bool:
    if not filtro:
        return True
    for chave, esperado in filtro.items():
        if chave == "$expr":
            if not _avaliar_expr(doc, esperado):
                return False
            continue
        valor = _obter_caminho(doc, chave)
        if isinstance(esperado, dict):
            if "$ne" in esperado and valor == esperado["$ne"]:
                return False
        elif valor != esperado:
            return False
    return True


class _ColecaoMemoria:
    def __init__(self, db_memoria, nome: str):
        self.db = db_memoria
        self.nome = nome
        self.docs = []

    def count_documents(self, filtro=None) -> int:
        return len(self.find(filtro or {}))

    def find(self, filtro=None, projecao=None):
        selecionados = [
            copy.deepcopy(d) for d in self.docs if _combina_filtro(d, filtro or {})
        ]
        return _CursorMemoria(selecionados)

    def find_one(self, filtro=None, projecao=None):
        encontrados = self.find(filtro, projecao)
        return encontrados[0] if encontrados else None

    def insert_one(self, doc: dict):
        self.docs.append(copy.deepcopy(doc))

    def insert_many(self, lista_docs: list):
        for doc in lista_docs:
            self.insert_one(doc)

    def update_one(self, filtro: dict, atualizacao: dict):
        for doc in self.docs:
            if _combina_filtro(doc, filtro):
                doc.update(copy.deepcopy(atualizacao.get("$set", {})))
                return _ResultadoUpdate(1, 1)
        return _ResultadoUpdate(0, 0)

    def delete_one(self, filtro: dict):
        for i, doc in enumerate(self.docs):
            if _combina_filtro(doc, filtro):
                self.docs.pop(i)
                return _ResultadoDelete(1)
        return _ResultadoDelete(0)

    def aggregate(self, pipeline: list):
        atual = [copy.deepcopy(d) for d in self.docs]
        for estagio in pipeline:
            if "$match" in estagio:
                atual = [d for d in atual if _combina_filtro(d, estagio["$match"])]
            elif "$lookup" in estagio:
                cfg = estagio["$lookup"]
                estrangeira = self.db[cfg["from"]]
                novo = []
                for d in atual:
                    val_local = _obter_caminho(d, cfg["localField"])
                    correspondentes = (
                        estrangeira.find({cfg["foreignField"]: val_local})
                        if val_local is not None
                        else []
                    )
                    copia = copy.deepcopy(d)
                    copia[cfg["as"]] = correspondentes
                    novo.append(copia)
                atual = novo
            elif "$unwind" in estagio:
                cfg = estagio["$unwind"]
                if isinstance(cfg, str):
                    campo = cfg[1:]
                    preservar = False
                else:
                    campo = cfg["path"][1:]
                    preservar = cfg.get("preserveNullAndEmptyArrays", False)
                novo = []
                for d in atual:
                    itens = d.get(campo) or []
                    if not itens and preservar:
                        copia = copy.deepcopy(d)
                        copia[campo] = {}
                        novo.append(copia)
                    for item in itens:
                        copia = copy.deepcopy(d)
                        copia[campo] = item
                        novo.append(copia)
                atual = novo
            elif "$group" in estagio:
                cfg = estagio["$group"]
                grupos = {}
                ordem = []
                for d in atual:
                    id_spec = cfg["_id"]
                    if id_spec is None:
                        chave = None
                        id_val = None
                    else:
                        id_val = {k: _avaliar_expr(d, v) for k, v in id_spec.items()}
                        chave = tuple(sorted(id_val.items()))
                    if chave not in grupos:
                        ordem.append(chave)
                        grupos[chave] = {"_id": id_val, "_docs": []}
                    grupos[chave]["_docs"].append(d)

                novo = []
                for chave in ordem:
                    g = grupos[chave]
                    docs_g = g["_docs"]
                    saida = {"_id": g["_id"]}
                    for campo, op in cfg.items():
                        if campo == "_id":
                            continue
                        if "$max" in op:
                            vals = [
                                _avaliar_expr(x, op["$max"])
                                for x in docs_g
                                if _avaliar_expr(x, op["$max"]) is not None
                            ]
                            saida[campo] = max(vals) if vals else None
                        elif "$addToSet" in op:
                            conj = []
                            for x in docs_g:
                                v = _avaliar_expr(x, op["$addToSet"])
                                if v is not None and v not in conj:
                                    conj.append(v)
                            saida[campo] = conj
                        elif "$sum" in op:
                            saida[campo] = sum(_avaliar_expr(x, op["$sum"]) or 0 for x in docs_g)
                    novo.append(saida)
                atual = novo
            elif "$project" in estagio:
                cfg = estagio["$project"]
                novo = []
                for d in atual:
                    proj = {}
                    for campo, regra in cfg.items():
                        if campo == "_id" and regra == 0:
                            continue
                        if regra == 1:
                            proj[campo] = d.get(campo)
                        else:
                            proj[campo] = _avaliar_expr(d, regra)
                    novo.append(proj)
                atual = novo
            elif "$sort" in estagio:
                chaves = list(estagio["$sort"].items())
                for campo, direcao in reversed(chaves):
                    atual.sort(key=lambda x: x.get(campo), reverse=(direcao < 0))
        return atual


class _DBMemoria:
    def __init__(self):
        self.colecoes = {}

    def list_collection_names(self):
        return list(self.colecoes.keys())

    def create_collection(self, nome: str):
        self.colecoes[nome] = _ColecaoMemoria(self, nome)

    def drop_collection(self, nome: str):
        self.colecoes.pop(nome, None)

    def __getitem__(self, nome: str) -> _ColecaoMemoria:
        if nome not in self.colecoes:
            self.create_collection(nome)
        return self.colecoes[nome]


class BancoMongoTeste:
    def __init__(self):
        self.permite_escrita = True
        self.db = _DBMemoria()
        self.fechamentos = 0
        self.db["fornecedor"].insert_one({
            "id_fornecedor": 1,
            "nome": "Fornecedor teste",
            "cnpj": "12345678000199",
            "telefone": "2733330000",
            "email": "teste@forn.com",
        })
        self.db["produto"].insert_one({
            "id_produto": 1,
            "nome": "Produto teste",
            "descricao": "Descricao inicial",
            "preco_venda": 10.50,
            "estoque_atual": 4,
            "estoque_minimo": 5,
        })

    def conectar(self):
        return self.db

    def desconectar(self):
        self.fechamentos += 1

    def obter_proximo_id(self, nome_colecao: str, campo_id: str) -> int:
        pipeline = [
            {"$group": {"_id": None, "max_id": {"$max": f"${campo_id}"}}},
            {"$project": {"_id": 0, "proximo": {"$add": ["$max_id", 1]}}},
        ]
        res = list(self.db[nome_colecao].aggregate(pipeline))
        if not res or res[0].get("proximo") is None:
            return 1
        return int(res[0]["proximo"])

    def contar_documentos(self, nome_colecao: str) -> int:
        return self.db[nome_colecao].count_documents({})


class ControllersMongoTest(unittest.TestCase):
    def setUp(self):
        self.banco = BancoMongoTeste()
        self.fornecedores = ControllerFornecedor(self.banco)
        self.produtos = ControllerProduto(self.banco)
        self.compras = ControllerCompra(self.banco)
        self.itens = ControllerItemCompra(self.banco)

    def compra(self):
        return self.compras.inserir(Compra(None, Fornecedor(1), date(2026, 10, 29), "PENDENTE"))

    def test_crud_completo_fornecedor_e_bloqueio_referencia(self):
        novo = self.fornecedores.inserir(
            Fornecedor(None, "Fornecedor Dois", "98765432000188", "11999990000", "dois@forn.com")
        )
        self.assertEqual(novo.get_id_fornecedor(), 2)
        self.assertIn("Fornecedor Dois", novo.to_string())
        self.assertEqual(len(self.fornecedores.listar()), 2)

        novo.set_nome("Fornecedor Dois Atualizado")
        atualizado = self.fornecedores.atualizar(novo)
        self.assertEqual(atualizado.get_nome(), "Fornecedor Dois Atualizado")

        compra_vinculada = self.compras.inserir(Compra(None, atualizado, date(2026, 10, 29), "CONCLUIDA"))
        with self.assertRaisesRegex(ValueError, "possui compras"):
            self.fornecedores.excluir(novo.get_id_fornecedor())

        self.compras.excluir(compra_vinculada.get_id_compra())
        self.assertTrue(self.fornecedores.excluir(novo.get_id_fornecedor()))
        self.assertIsNone(self.fornecedores.buscar(novo.get_id_fornecedor()))

    def test_crud_completo_produto_e_bloqueio_referencia(self):
        novo = self.produtos.inserir(
            Produto(None, "Teclado Gamer", "Switch Red", 199.90, 15, 5)
        )
        self.assertEqual(novo.get_id_produto(), 2)
        self.assertIn("199.90", novo.to_string())
        self.assertEqual(len(self.produtos.listar()), 2)

        novo.set_estoque_atual(22)
        novo.set_preco_venda(210.00)
        atualizado = self.produtos.atualizar(novo)
        self.assertEqual(atualizado.get_estoque_atual(), 22)
        self.assertEqual(atualizado.get_preco_venda(), 210.00)

        compra = self.compra()
        item = self.itens.inserir(ItemCompra(None, compra, atualizado, 2, 120.00))
        with self.assertRaisesRegex(ValueError, "possui itens"):
            self.produtos.excluir(atualizado.get_id_produto())

        self.itens.excluir(item.get_id_item())
        self.assertTrue(self.produtos.excluir(atualizado.get_id_produto()))
        self.assertIsNone(self.produtos.buscar(atualizado.get_id_produto()))

    def test_ciclo_compra_no_mongodb(self):
        compra = self.compra()
        compra.set_status("CONCLUIDA")
        salvo = self.compras.atualizar(compra)
        self.assertEqual(salvo.get_status(), "CONCLUIDA")
        self.assertEqual(salvo.get_fornecedor().get_nome(), "Fornecedor teste")
        self.assertIn("29/10/2026", salvo.to_string())
        self.assertEqual(len(self.compras.listar()), 1)
        self.assertTrue(self.compras.existe(compra.get_id_compra()))
        self.assertTrue(self.compras.excluir(compra.get_id_compra()))
        self.assertIsNone(self.compras.buscar(compra.get_id_compra()))

    def test_ciclo_item_e_bloqueio_de_exclusao_da_compra(self):
        compra = self.compra()
        item = self.itens.inserir(ItemCompra(None, compra, Produto(1), 3, Decimal("12.50")))
        self.assertIn("12.50", item.to_string())
        with self.assertRaisesRegex(ValueError, "possui itens"):
            self.compras.excluir(compra.get_id_compra())
        self.assertEqual(len(self.itens.listar(id_compra=compra.get_id_compra())), 1)
        self.assertEqual(self.itens.listar(id_compra=999), [])
        item.set_quantidade(4)
        atualizado = self.itens.atualizar(item)
        self.assertEqual(atualizado.get_quantidade(), 4)
        self.assertEqual(atualizado.get_produto().get_nome(), "Produto teste")
        self.assertEqual(atualizado.get_compra().get_fornecedor().get_nome(), "Fornecedor teste")
        self.itens.excluir(item.get_id_item())
        self.assertIsNone(self.itens.buscar(item.get_id_item()))
        self.compras.excluir(compra.get_id_compra())

    def test_splash_screen_e_seis_relatorios_mongodb(self):
        compra = self.compra()
        self.itens.inserir(ItemCompra(None, compra, Produto(1), 5, 8.00))

        tela = SplashScreen(conexao=self.banco).get_updated_screen()
        self.assertIn("COM DOCUMENTOS", tela)
        self.assertIn("FORNECEDOR", tela)
        self.assertIn("ITEM_COMPRA", tela)
        for integrante in SplashScreen.INTEGRANTES:
            self.assertIn(integrante, tela)

        saida = io.StringIO()
        relatorio = Relatorio(conexao=self.banco, saida=saida)
        relatorio.get_relatorio_compras_por_fornecedor()
        relatorio.get_relatorio_itens_compra()
        relatorio.get_relatorio_estoque_baixo()
        relatorio.get_relatorio_fornecedores()
        relatorio.get_relatorio_produtos()
        relatorio.get_relatorio_compras()
        texto_relatorios = saida.getvalue()
        self.assertIn("Fornecedor teste", texto_relatorios)
        self.assertIn("Produto teste", texto_relatorios)
        self.assertIn("12345678000199", texto_relatorios)
        self.assertIn("Descricao inicial", texto_relatorios)
        self.assertIn("PENDENTE", texto_relatorios)
        self.assertIn("40", texto_relatorios)

    def test_rejeita_referencias_inexistentes(self):
        with self.assertRaisesRegex(ValueError, "Fornecedor nao encontrado"):
            self.compras.inserir(Compra(None, Fornecedor(999), date.today(), "PENDENTE"))
        compra = self.compra()
        with self.assertRaisesRegex(ValueError, "Produto nao encontrado"):
            self.itens.inserir(ItemCompra(None, compra, Produto(999), 1, 10))
        with self.assertRaisesRegex(ValueError, "Compra nao encontrada"):
            self.itens.inserir(ItemCompra(None, Compra(999), Produto(1), 1, 10))

    def test_validacoes_de_quantidade_preco_e_id(self):
        compra = self.compra()
        for quantidade in (0, -1, True, 1.5, "2"):
            with self.subTest(quantidade=quantidade), self.assertRaises(ValueError):
                self.itens.inserir(ItemCompra(None, compra, Produto(1), quantidade, 10))
        for preco in (0, -1, True, "NaN", "Infinity", "1.234", "100000000", None):
            with self.subTest(preco=preco), self.assertRaises(ValueError):
                self.itens.inserir(ItemCompra(None, compra, Produto(1), 1, preco))
        with self.assertRaises(ValueError):
            self.compras.buscar("1 OR 1=1")

    def test_ausencia_e_protecao_de_id_principal(self):
        compra = self.compra()
        with self.assertRaises(ValueError):
            self.compras.inserir(compra)
        compra.set_id_compra(999)
        with self.assertRaisesRegex(ValueError, "nao encontrada"):
            self.compras.atualizar(compra)
        with self.assertRaises(ValueError):
            self.itens.excluir(999)

    def test_criacao_e_normalizacao_de_colecoes_migradas(self):
        criar_colecoes(self.banco, recriar_se_existir=True)
        for colecao, lista in DADOS_INICIAIS_PADRAO.items():
            docs = [_normalizar_documento(colecao, d) for d in lista]
            self.banco.db[colecao].insert_many(docs)
        self.assertEqual(self.banco.contar_documentos("fornecedor"), 4)
        self.assertEqual(self.banco.contar_documentos("produto"), 6)
        self.assertEqual(self.banco.contar_documentos("compra"), 4)
        self.assertEqual(self.banco.contar_documentos("item_compra"), 8)

    def test_permissao_de_escrita(self):
        self.banco.permite_escrita = False
        with self.assertRaises(PermissionError):
            self.compra()
        self.assertEqual(self.compras.listar(), [])


if __name__ == "__main__":
    unittest.main()
