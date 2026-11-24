"""Tela inicial do Sistema de Gerenciamento de Estoque (MongoDB)."""


class SplashScreen:
    """Exibe os dados do projeto e as contagens de documentos das coleções no MongoDB."""

    COLECOES = ("fornecedor", "produto", "compra", "item_compra")
    INTEGRANTES = (
        "Arthur Gava Calil",
        "André Luiz Alves Bofonha",
        "Miguel Gomes",
        "Kawan Wendler Goldner",
        "João Vitor Gnocchi da Cunha",
        "João Vitor Gera Bof",
    )

    def __init__(self, conexao=None):
        self.conexao = conexao

    def _contar_documentos(self):
        contagens = {}
        erros = {}

        if self.conexao is None:
            erros["CONEXAO"] = "conexão MongoDB compartilhada não fornecida"
            return contagens, erros

        if hasattr(self.conexao, "contar_documentos"):
            for colecao in self.COLECOES:
                try:
                    contagens[colecao.upper()] = int(self.conexao.contar_documentos(colecao))
                except Exception as erro:
                    erros[colecao.upper()] = str(erro)
            return contagens, erros

        try:
            db = self.conexao.conectar()
            for colecao in self.COLECOES:
                try:
                    contagens[colecao.upper()] = int(db[colecao].count_documents({}))
                except Exception as erro:
                    erros[colecao.upper()] = str(erro)
        except Exception as erro:
            erros["CONEXAO"] = str(erro)
        finally:
            if hasattr(self.conexao, "desconectar"):
                self.conexao.desconectar()

        return contagens, erros

    def get_updated_screen(self):
        """Retorna a tela inicial atualizada com a contagem de documentos no MongoDB."""
        contagens, erros = self._contar_documentos()

        linhas = [
            "=" * 60,
            "        SISTEMA DE GERENCIAMENTO DE ESTOQUE (2026/2)",
            "     Disciplina: Banco de Dados | Prof.: Howard Roatti",
            "=" * 60,
            "Integrantes:",
        ]
        for i in range(0, len(self.INTEGRANTES), 2):
            esq = f"- {self.INTEGRANTES[i]}"
            if i + 1 < len(self.INTEGRANTES):
                dir_nome = f"- {self.INTEGRANTES[i + 1]}"
                linhas.append(f"  {esq:<30} {dir_nome}")
            else:
                linhas.append(f"  {esq}")

        linhas.append("-" * 60)
        linhas.append("Documentos no MongoDB:")
        if "CONEXAO" in erros:
            linhas.append("  MongoDB indisponível: " + erros["CONEXAO"])

        for colecao in self.COLECOES:
            chave = colecao.upper()
            if chave in contagens:
                quantidade = contagens[chave]
                situacao = "COM DOCUMENTOS" if quantidade else "VAZIA"
                linhas.append(f"  {chave:<18} {quantidade:>6}  {situacao}")
            elif chave in erros:
                linhas.append(f"  {chave:<18} indisponível: {erros[chave]}")
            else:
                linhas.append(f"  {chave:<18} indisponível")

        linhas.append("=" * 60)
        return "\n".join(linhas)


if __name__ == "__main__":
    print(SplashScreen().get_updated_screen())
