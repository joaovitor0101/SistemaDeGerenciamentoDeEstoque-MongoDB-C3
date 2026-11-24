"""
Script de criação das coleções no MongoDB e migração dos dados do Oracle (C2 -> C3).
Atende ao Item 4 (migração a partir das tabelas do Oracle) e Item 5 do edital.
"""

from datetime import date, datetime
import sys
from pathlib import Path

DIRETORIO_SRC = Path(__file__).resolve().parent
if str(DIRETORIO_SRC) not in sys.path:
    sys.path.insert(0, str(DIRETORIO_SRC))

from conexion.mongo_queries import ConexaoMongo
from conexion.oracle_queries import ConexaoOracle

COLECOES = ("fornecedor", "produto", "compra", "item_compra")

# Carga inicial padrão caso o banco Oracle ainda não tenha sido populado
DADOS_INICIAIS_PADRAO = {
    "fornecedor": [
        {
            "id_fornecedor": 1,
            "nome": "Tech Distribuidora LTDA",
            "cnpj": "12345678000190",
            "telefone": "2733221100",
            "email": "contato@techdist.com.br",
        },
        {
            "id_fornecedor": 2,
            "nome": "Suprimentos Brasil S/A",
            "cnpj": "98765432000155",
            "telefone": "1140028922",
            "email": "vendas@suprimentosbr.com.br",
        },
        {
            "id_fornecedor": 3,
            "nome": "Alfa Componentes Eletronicos",
            "cnpj": "45678912000133",
            "telefone": "27998887766",
            "email": "comercial@alfacomp.com.br",
        },
        {
            "id_fornecedor": 4,
            "nome": "Logistica e Atacado Vitoria",
            "cnpj": "33445566000177",
            "telefone": "2732004500",
            "email": "atendimento@atacadovix.com.br",
        },
    ],
    "produto": [
        {
            "id_produto": 1,
            "nome": "Mouse Optico USB",
            "descricao": "Mouse 1200 DPI com fio",
            "preco_venda": 45.90,
            "estoque_atual": 35,
            "estoque_minimo": 10,
        },
        {
            "id_produto": 2,
            "nome": "Teclado Mecanico ABNT2",
            "descricao": "Teclado switch brown",
            "preco_venda": 249.90,
            "estoque_atual": 4,
            "estoque_minimo": 8,
        },
        {
            "id_produto": 3,
            "nome": "Monitor LED 24 Polegadas",
            "descricao": "Monitor Full HD 75Hz HDMI",
            "preco_venda": 789.00,
            "estoque_atual": 12,
            "estoque_minimo": 5,
        },
        {
            "id_produto": 4,
            "nome": "SSD NVMe 500GB",
            "descricao": "Leitura 3500MB/s M.2",
            "preco_venda": 329.90,
            "estoque_atual": 3,
            "estoque_minimo": 6,
        },
        {
            "id_produto": 5,
            "nome": "Cabo HDMI 2.0 2 Metros",
            "descricao": "Cabo blindado 4K 60Hz",
            "preco_venda": 29.90,
            "estoque_atual": 50,
            "estoque_minimo": 15,
        },
        {
            "id_produto": 6,
            "nome": "Headset USB com Microfone",
            "descricao": "Headset corporativo",
            "preco_venda": 139.90,
            "estoque_atual": 2,
            "estoque_minimo": 5,
        },
    ],
    "compra": [
        {"id_compra": 1, "id_fornecedor": 1, "data_compra": "2026-10-10", "status": "CONCLUIDA"},
        {"id_compra": 2, "id_fornecedor": 2, "data_compra": "2026-10-15", "status": "CONCLUIDA"},
        {"id_compra": 3, "id_fornecedor": 1, "data_compra": "2026-10-20", "status": "PENDENTE"},
        {"id_compra": 4, "id_fornecedor": 3, "data_compra": "2026-10-25", "status": "CONCLUIDA"},
    ],
    "item_compra": [
        {"id_item": 1, "id_compra": 1, "id_produto": 1, "quantidade": 20, "preco_unitario": 22.50},
        {"id_item": 2, "id_compra": 1, "id_produto": 5, "quantidade": 30, "preco_unitario": 12.00},
        {"id_item": 3, "id_compra": 2, "id_produto": 3, "quantidade": 10, "preco_unitario": 520.00},
        {"id_item": 4, "id_compra": 2, "id_produto": 2, "quantidade": 5, "preco_unitario": 150.00},
        {"id_item": 5, "id_compra": 3, "id_produto": 4, "quantidade": 8, "preco_unitario": 210.00},
        {"id_item": 6, "id_compra": 3, "id_produto": 6, "quantidade": 6, "preco_unitario": 85.00},
        {"id_item": 7, "id_compra": 4, "id_produto": 1, "quantidade": 15, "preco_unitario": 21.00},
        {"id_item": 8, "id_compra": 4, "id_produto": 4, "quantidade": 5, "preco_unitario": 205.00},
    ],
}


def criar_colecoes(mongo: ConexaoMongo, recriar_se_existir: bool = True):
    """Cria as 4 coleções no MongoDB (apagando versões anteriores se recriar_se_existir=True)."""
    print("\n=== [1/3] CRIANDO COLEÇÕES NO MONGODB ===")
    try:
        db = mongo.conectar()
        existentes = db.list_collection_names()
        for colecao in COLECOES:
            if colecao in existentes:
                if recriar_se_existir:
                    db.drop_collection(colecao)
                    db.create_collection(colecao)
                    print(f"[OK] Coleção '{colecao}' recriada do zero.")
                else:
                    print(f"[INFO] Coleção '{colecao}' já existe (mantida).")
            else:
                db.create_collection(colecao)
                print(f"[OK] Coleção '{colecao}' criada com sucesso.")
    finally:
        mongo.desconectar()


def _normalizar_documento(colecao: str, doc: dict) -> dict:
    """Garante tipos nativos consistentes (int, float, strings limpas e data YYYY-MM-DD)."""
    if colecao == "fornecedor":
        return {
            "id_fornecedor": int(doc["id_fornecedor"]),
            "nome": str(doc["nome"]).strip(),
            "cnpj": str(doc["cnpj"]).strip(),
            "telefone": str(doc["telefone"]).strip() if doc.get("telefone") is not None else None,
            "email": str(doc["email"]).strip() if doc.get("email") is not None else None,
        }
    if colecao == "produto":
        return {
            "id_produto": int(doc["id_produto"]),
            "nome": str(doc["nome"]).strip(),
            "descricao": str(doc["descricao"]).strip() if doc.get("descricao") is not None else None,
            "preco_venda": round(float(doc["preco_venda"]), 2),
            "estoque_atual": int(doc["estoque_atual"]),
            "estoque_minimo": int(doc["estoque_minimo"]),
        }
    if colecao == "compra":
        valor_data = doc["data_compra"]
        if isinstance(valor_data, (datetime, date)):
            data_str = valor_data.strftime("%Y-%m-%d")
        else:
            data_str = str(valor_data)[:10]
        return {
            "id_compra": int(doc["id_compra"]),
            "id_fornecedor": int(doc["id_fornecedor"]),
            "data_compra": data_str,
            "status": str(doc["status"]).strip().upper(),
        }
    if colecao == "item_compra":
        return {
            "id_item": int(doc["id_item"]),
            "id_compra": int(doc["id_compra"]),
            "id_produto": int(doc["id_produto"]),
            "quantidade": int(doc["quantidade"]),
            "preco_unitario": round(float(doc["preco_unitario"]), 2),
        }
    return doc


def extrair_dados_do_oracle() -> dict:
    """
    Item 4 (I e II): Conecta ao banco relacional Oracle e extrai os registros
    pré-cadastrados das tabelas FORNECEDOR, PRODUTO, COMPRA e ITEM_COMPRA.
    """
    oracle = ConexaoOracle(permite_escrita=False)
    dados_extraidos = {}
    for colecao in COLECOES:
        tabela_oracle = colecao.upper()
        df = oracle.consultar(f"SELECT * FROM {tabela_oracle} ORDER BY 1")
        registros = df.where(df.notna(), None).to_dict(orient="records")
        dados_extraidos[colecao] = [_normalizar_documento(colecao, r) for r in registros]
    return dados_extraidos


def migrar_e_inserir_documentos(mongo: ConexaoMongo):
    """
    Tenta extrair os registros das tabelas do Oracle (Item 4 do Edital).
    Caso o Oracle não esteja ativo ou as tabelas ainda não existam, utiliza a carga inicial padrão.
    """
    print("\n=== [2/3] EXTRAINDO DADOS DO ORACLE E INSERINDO NO MONGODB ===")
    try:
        dados = extrair_dados_do_oracle()
        total_oracle = sum(len(lista) for lista in dados.values())
        if total_oracle == 0:
            print("[AVISO] As tabelas do Oracle estão vazias. Utilizando registros iniciais padrão.")
            dados = DADOS_INICIAIS_PADRAO
        else:
            print("[OK] Dados extraídos com sucesso diretamente do banco relacional Oracle!")
    except Exception as erro:
        print(f"[AVISO] Oracle indisponível ou sem tabelas criadas ({erro}).")
        print("[INFO] Inserindo os documentos iniciais do projeto diretamente no MongoDB...")
        dados = DADOS_INICIAIS_PADRAO

    try:
        db = mongo.conectar()
        for colecao in COLECOES:
            documentos = [_normalizar_documento(colecao, d) for d in dados.get(colecao, [])]
            if documentos:
                db[colecao].insert_many(documentos)
            print(f"[OK] {len(documentos)} documento(s) inserido(s) na coleção '{colecao}'.")
    finally:
        mongo.desconectar()


def validar_colecoes_mongodb(mongo: ConexaoMongo):
    """Exibe a contagem final de documentos em cada coleção criada no MongoDB."""
    print("\n=== [3/3] VALIDANDO DOCUMENTOS GRAVADOS NO MONGODB ===")
    for colecao in COLECOES:
        total = mongo.contar_documentos(colecao)
        print(f"-> Coleção '{colecao}': {total} documento(s) cadastrado(s).")


def inicializar_mongodb():
    mongo = ConexaoMongo(permite_escrita=True)
    print(f"Testando conexão com MongoDB em {mongo.host}:{mongo.porta} (banco: {mongo.nome_banco})...")
    try:
        mongo.conectar()
        mongo.desconectar()
        print("[OK] Conexão com o MongoDB estabelecida com sucesso!")
    except Exception as erro:
        print(f"[ERRO DE CONEXÃO] Não foi possível conectar ao MongoDB:\n{erro}")
        sys.exit(1)

    criar_colecoes(mongo, recriar_se_existir=True)
    migrar_e_inserir_documentos(mongo)
    validar_colecoes_mongodb(mongo)
    print("\nColeções criadas e documentos populados no MongoDB com sucesso!\n")


if __name__ == "__main__":
    inicializar_mongodb()
