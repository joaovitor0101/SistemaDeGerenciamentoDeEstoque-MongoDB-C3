"""Gerenciamento de conexão direta com o banco de dados NoSQL MongoDB (via PyMongo)."""

import os
from pathlib import Path
from urllib.parse import quote_plus
import pymongo
from pymongo.errors import OperationFailure


class ConexaoMongo:
    """
    Gerencia a conexão com o MongoDB da VM (localhost:27017, banco labdatabase),
    disponibilizando acesso às coleções e geração incremental de IDs inteiros.
    """

    def __init__(self, permite_escrita: bool = False):
        self.permite_escrita = permite_escrita
        self.host = os.getenv("MONGO_HOST", "localhost")
        self.porta = int(os.getenv("MONGO_PORT", "27017"))
        self.nome_banco = os.getenv("MONGO_DB", "labdatabase")

        usuario_padrao, senha_padrao = self._ler_arquivo_autenticacao()
        self.usuario = os.getenv("MONGO_USER", usuario_padrao)
        self.senha = os.getenv("MONGO_PASSWORD", senha_padrao)

        self.mongo_client = None
        self.db = None
        self._uri_validada = None

    @staticmethod
    def _ler_arquivo_autenticacao() -> tuple:
        caminho = Path(__file__).resolve().parent / "passphrase" / "authentication.mongo"
        if caminho.exists():
            try:
                conteudo = caminho.read_text(encoding="utf-8").strip()
                if "," in conteudo:
                    usuario, senha = conteudo.split(",", 1)
                    return usuario.strip(), senha.strip()
            except OSError:
                pass
        return "labdatabase", "labDatabase2022"

    def _candidatos_uri(self) -> list:
        if os.getenv("MONGO_URI"):
            return [os.getenv("MONGO_URI")]
        if self._uri_validada:
            return [self._uri_validada]

        uris = []
        if self.usuario and self.senha:
            u = quote_plus(self.usuario)
            for s in (self.senha, "lab@Database2025", "labDatabase2022"):
                uri = f"mongodb://{u}:{quote_plus(s)}@{self.host}:{self.porta}/"
                if uri not in uris:
                    uris.append(uri)
        uris.append(f"mongodb://{self.host}:{self.porta}/")
        return uris

    def conectar(self):
        """Abre a conexão com o MongoDB e retorna a referência do banco (self.db)."""
        ultimo_erro = None
        for uri in self._candidatos_uri():
            cliente = pymongo.MongoClient(uri, serverSelectionTimeoutMS=4000)
            try:
                db = cliente[self.nome_banco]
                # Valida autenticação e conectividade imediatamente
                db.list_collection_names()
                self._uri_validada = uri
                self.mongo_client = cliente
                self.db = db
                return self.db
            except OperationFailure as erro:
                ultimo_erro = erro
                cliente.close()
            except Exception:
                cliente.close()
                raise

        if ultimo_erro is not None:
            raise ultimo_erro
        raise ConnectionError("Não foi possível conectar ao MongoDB.")

    def desconectar(self):
        """Fecha o cliente do MongoDB com segurança."""
        if self.mongo_client is not None:
            try:
                self.mongo_client.close()
            except Exception:
                pass
            self.mongo_client = None
            self.db = None

    def obter_proximo_id(self, nome_colecao: str, campo_id: str) -> int:
        """
        Calcula o próximo ID inteiro sequencial da coleção usando agregação ($max + 1),
        substituindo o comportamento das SEQUENCES do Oracle no MongoDB.
        """
        try:
            db = self.conectar()
            pipeline = [
                {"$group": {"_id": None, "max_id": {"$max": f"${campo_id}"}}},
                {"$project": {"_id": 0, "proximo": {"$add": ["$max_id", 1]}}},
            ]
            resultado = list(db[nome_colecao].aggregate(pipeline))
            if not resultado or resultado[0].get("proximo") is None:
                return 1
            return int(resultado[0]["proximo"])
        finally:
            self.desconectar()

    def contar_documentos(self, nome_colecao: str) -> int:
        """Retorna a quantidade total de documentos na coleção informada."""
        try:
            db = self.conectar()
            return int(db[nome_colecao].count_documents({}))
        finally:
            self.desconectar()
