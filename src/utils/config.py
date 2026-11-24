import os
import time

# Menus do Sistema (Item 6.a do Edital C3 - MongoDB)
MENU_PRINCIPAL = """|                      MENU PRINCIPAL                      |
============================================================
1 - Relatórios
2 - Inserir Documentos
3 - Remover Documentos
4 - Atualizar Documentos
5 - Sair
============================================================
Escolha uma opção: """

MENU_ENTIDADES = """
============================================================
|                    MENU DE COLEÇÕES                      |
============================================================
1 - FORNECEDOR
2 - PRODUTO
3 - COMPRA
4 - ITEM COMPRA
5 - Voltar
============================================================
Escolha uma opção: """

MENU_RELATORIOS = """
============================================================
|                    MENU DE RELATÓRIOS                    |
============================================================
1 - Relatório de Compras Agrupado por Fornecedor ($group)
2 - Relatório Detalhado de Itens de Compra ($lookup)
3 - Relatório de Produtos com Estoque Baixo
4 - Relatório de Fornecedores
5 - Relatório de Produtos
6 - Relatório de Compras
7 - Voltar
============================================================
Escolha uma opção: """


def clear_console(wait_time: int = 1):
    """
    Limpa a tela do console após aguardar um tempo.
    Compatível com Linux ('posix' -> clear) e Windows ('cls').
    """
    if wait_time > 0:
        time.sleep(wait_time)
    if os.name == 'posix':
        os.system('clear')
    else:
        os.system('cls')
