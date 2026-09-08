import sqlite3
from datetime import date

DB = "banco.db"


# ==========================================================
# CONEXÃO
# ==========================================================

def conectar():
    conexao = sqlite3.connect(DB)
    conexao.row_factory = sqlite3.Row
    return conexao


# ==========================================================
# INICIALIZAÇÃO DO BANCO
# ==========================================================

def inicializar_banco():

    conexao = conectar()
    cursor = conexao.cursor()

    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS clientes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        telefone TEXT,
        cpf_cnpj TEXT,
        observacoes TEXT
    );

    CREATE TABLE IF NOT EXISTS despachantes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        telefone TEXT,
        observacoes TEXT
    );

    CREATE TABLE IF NOT EXISTS vendas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        despachante_id INTEGER,
        cliente_id INTEGER,
        placa TEXT NOT NULL,
        data TEXT NOT NULL,
        servico TEXT NOT NULL,
        valor REAL NOT NULL,
        valor_liquido REAL NOT NULL,
        forma_pagamento TEXT,
        pago INTEGER DEFAULT 0,
        FOREIGN KEY(despachante_id) REFERENCES despachantes(id),
        FOREIGN KEY(cliente_id) REFERENCES clientes(id)
    );

    CREATE TABLE IF NOT EXISTS gastos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data TEXT NOT NULL,
        categoria TEXT NOT NULL,
        descricao TEXT,
        valor REAL NOT NULL
    );

    CREATE TABLE IF NOT EXISTS estoque (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        categoria TEXT,
        quantidade REAL DEFAULT 0,
        estoque_minimo REAL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS movimentacoes_estoque (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        estoque_id INTEGER NOT NULL,
        data TEXT NOT NULL,
        tipo TEXT NOT NULL,
        quantidade REAL NOT NULL,
        observacao TEXT,
        FOREIGN KEY(estoque_id) REFERENCES estoque(id)
    );

    CREATE TABLE IF NOT EXISTS caixa (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data_abertura TEXT NOT NULL,
        valor_abertura REAL NOT NULL,
        data_fechamento TEXT,
        valor_fechamento REAL,
        diferenca REAL DEFAULT 0,
        status TEXT DEFAULT 'ABERTO'
    );
    """)

    # ======================================================
    # ATUALIZAÇÃO DO BANCO EXISTENTE
    # ======================================================
    #
    # Se o banco já existia antes da coluna "diferenca",
    # o SQLite não adiciona a coluna automaticamente.
    # Por isso verificamos se ela existe.
    #

    colunas = cursor.execute("""
        PRAGMA table_info(caixa)
    """).fetchall()

    nomes_colunas = [
        coluna["name"]
        for coluna in colunas
    ]

    if "diferenca" not in nomes_colunas:

        cursor.execute("""
            ALTER TABLE caixa
            ADD COLUMN diferenca REAL DEFAULT 0
        """)

    conexao.commit()
    conexao.close()


# ==========================================================
# DASHBOARD
# ==========================================================

def buscar_dashboard():

    conexao = conectar()

    hoje = date.today().isoformat()
    mes = date.today().strftime("%Y-%m")

    venda_dia = conexao.execute("""
        SELECT
            COALESCE(SUM(valor), 0) AS total
        FROM vendas
        WHERE data = ?
    """, (
        hoje,
    )).fetchone()["total"]

    venda_mes = conexao.execute("""
        SELECT
            COALESCE(SUM(valor), 0) AS total
        FROM vendas
        WHERE substr(data, 1, 7) = ?
    """, (
        mes,
    )).fetchone()["total"]

    liquido_mes = conexao.execute("""
        SELECT
            COALESCE(SUM(valor_liquido), 0) AS total
        FROM vendas
        WHERE substr(data, 1, 7) = ?
    """, (
        mes,
    )).fetchone()["total"]

    gastos_mes = conexao.execute("""
        SELECT
            COALESCE(SUM(valor), 0) AS total
        FROM gastos
        WHERE substr(data, 1, 7) = ?
    """, (
        mes,
    )).fetchone()["total"]

    pendentes = conexao.execute("""
        SELECT
            COUNT(*) AS total
        FROM vendas
        WHERE pago = 0
    """).fetchone()["total"]

    conexao.close()

    saldo = liquido_mes - gastos_mes

    return {
        "venda_dia": venda_dia,
        "venda_mes": venda_mes,
        "liquido_mes": liquido_mes,
        "gastos_mes": gastos_mes,
        "saldo": saldo,
        "pendentes": pendentes
    }


# ==========================================================
# VENDAS
# ==========================================================

def listar_vendas():

    conexao = conectar()

    vendas = conexao.execute("""
        SELECT
            v.*,
            c.nome AS cliente,
            d.nome AS despachante

        FROM vendas v

        LEFT JOIN clientes c
            ON c.id = v.cliente_id

        LEFT JOIN despachantes d
            ON d.id = v.despachante_id

        ORDER BY
            v.id DESC
    """).fetchall()

    conexao.close()

    return vendas


def cadastrar_venda(form):

    servico = form.get("servico")

    if servico == "Carro - par":
        valor = 248.97
        valor_liquido = 166.48

    elif servico == "Unitária / Moto":
        valor = 196.86
        valor_liquido = 154.60

    else:
        valor = 0
        valor_liquido = 0

    conexao = conectar()

    conexao.execute("""
        INSERT INTO vendas (
            despachante_id,
            cliente_id,
            placa,
            data,
            servico,
            valor,
            valor_liquido,
            forma_pagamento,
            pago
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        form.get("despachante_id") or None,
        form.get("cliente_id") or None,
        form.get("placa", "").upper(),
        form.get("data"),
        servico,
        valor,
        valor_liquido,
        form.get("forma_pagamento"),
        1 if form.get("pago") == "1" else 0
    ))

    conexao.commit()
    conexao.close()

    # ==========================================================
# EDITAR VENDA
# ==========================================================

def editar_venda(venda_id, form):

    servico = form.get("servico")

    if servico == "Carro - par":
        valor = 248.97
        valor_liquido = 166.48

    elif servico == "Unitária / Moto":
        valor = 196.86
        valor_liquido = 154.60

    else:
        valor = 0
        valor_liquido = 0

    conexao = conectar()

    conexao.execute("""
        UPDATE vendas
        SET
            despachante_id = ?,
            cliente_id = ?,
            placa = ?,
            data = ?,
            servico = ?,
            valor = ?,
            valor_liquido = ?,
            forma_pagamento = ?,
            pago = ?
        WHERE id = ?
    """, (
        form.get("despachante_id") or None,
        form.get("cliente_id") or None,
        form.get("placa", "").upper(),
        form.get("data"),
        servico,
        valor,
        valor_liquido,
        form.get("forma_pagamento"),
        1 if form.get("pago") == "1" else 0,
        venda_id
    ))

    conexao.commit()

    alterada = conexao.total_changes > 0

    conexao.close()

    return alterada


# ==========================================================
# EXCLUIR VENDA
# ==========================================================

def excluir_venda(venda_id):

    conexao = conectar()

    conexao.execute("""
        DELETE FROM vendas

        WHERE id = ?
    """, (
        venda_id,
    ))

    conexao.commit()

    excluida = conexao.total_changes > 0

    conexao.close()

    return excluida


# ==========================================================
# CLIENTES
# ==========================================================

def listar_clientes():

    conexao = conectar()

    clientes = conexao.execute("""
        SELECT *
        FROM clientes
        ORDER BY nome
    """).fetchall()

    conexao.close()

    return clientes


def cadastrar_cliente(form):

    conexao = conectar()

    conexao.execute("""
        INSERT INTO clientes (
            nome,
            telefone,
            cpf_cnpj,
            observacoes
        )

        VALUES (?, ?, ?, ?)
    """, (
        form.get("nome"),
        form.get("telefone"),
        form.get("cpf_cnpj"),
        form.get("observacoes")
    ))

    conexao.commit()
    conexao.close()


# ==========================================================
# DESPACHANTES
# ==========================================================

def listar_despachantes():

    conexao = conectar()

    despachantes = conexao.execute("""
        SELECT *
        FROM despachantes
        ORDER BY nome
    """).fetchall()

    conexao.close()

    return despachantes


def cadastrar_despachante(form):

    conexao = conectar()

    conexao.execute("""
        INSERT INTO despachantes (
            nome,
            telefone,
            observacoes
        )

        VALUES (?, ?, ?)
    """, (
        form.get("nome"),
        form.get("telefone"),
        form.get("observacoes")
    ))

    conexao.commit()
    conexao.close()


# ==========================================================
# GASTOS
# ==========================================================

def listar_gastos():

    conexao = conectar()

    gastos = conexao.execute("""
        SELECT *
        FROM gastos
        ORDER BY id DESC
    """).fetchall()

    conexao.close()

    return gastos


def cadastrar_gasto(form):

    conexao = conectar()

    conexao.execute("""
        INSERT INTO gastos (
            data,
            categoria,
            descricao,
            valor
        )

        VALUES (?, ?, ?, ?)
    """, (
        form.get("data"),
        form.get("categoria"),
        form.get("descricao"),
        float(form.get("valor") or 0)
    ))

    conexao.commit()
    conexao.close()


# ==========================================================
# ESTOQUE
# ==========================================================

def listar_estoque():

    conexao = conectar()

    estoque = conexao.execute("""
        SELECT *
        FROM estoque
        ORDER BY nome
    """).fetchall()

    conexao.close()

    return estoque


def cadastrar_estoque(form):

    conexao = conectar()

    conexao.execute("""
        INSERT INTO estoque (
            nome,
            categoria,
            quantidade,
            estoque_minimo
        )

        VALUES (?, ?, ?, ?)
    """, (
        form.get("nome"),
        form.get("categoria"),
        float(form.get("quantidade") or 0),
        float(form.get("estoque_minimo") or 0)
    ))

    conexao.commit()
    conexao.close()


def registrar_movimentacao_estoque(form):

    estoque_id = int(
        form.get("estoque_id")
    )

    quantidade = float(
        form.get("quantidade") or 0
    )

    tipo = form.get("tipo")

    if tipo == "ENTRADA":

        quantidade_final = quantidade

    else:

        quantidade_final = -quantidade

    conexao = conectar()

    conexao.execute("""
        UPDATE estoque

        SET quantidade = quantidade + ?

        WHERE id = ?
    """, (
        quantidade_final,
        estoque_id
    ))

    conexao.execute("""
        INSERT INTO movimentacoes_estoque (
            estoque_id,
            data,
            tipo,
            quantidade,
            observacao
        )

        VALUES (?, ?, ?, ?, ?)
    """, (
        estoque_id,
        form.get("data"),
        tipo,
        quantidade,
        form.get("observacao")
    ))

    conexao.commit()
    conexao.close()


# ==========================================================
# CAIXA
# ==========================================================

def listar_caixa():

    conexao = conectar()

    caixas = conexao.execute("""
        SELECT *
        FROM caixa
        ORDER BY id DESC
    """).fetchall()

    conexao.close()

    return caixas


def abrir_caixa(form):

    conexao = conectar()

    conexao.execute("""
        INSERT INTO caixa (
            data_abertura,
            valor_abertura,
            status
        )

        VALUES (?, ?, 'ABERTO')
    """, (
        form.get("data_abertura"),
        float(form.get("valor_abertura") or 0)
    ))

    conexao.commit()
    conexao.close()


# ==========================================================
# DADOS PARA FECHAMENTO DO CAIXA
# ==========================================================

def dados_fechamento_caixa(caixa_id):

    conexao = conectar()

    caixa = conexao.execute("""
        SELECT *
        FROM caixa

        WHERE id = ?
    """, (
        caixa_id,
    )).fetchone()

    if not caixa:

        conexao.close()

        return None

    data = caixa["data_abertura"]

    # ------------------------------------------------------
    # TODAS AS VENDAS DO DIA
    # ------------------------------------------------------

    vendas = conexao.execute("""
        SELECT
            COALESCE(SUM(valor), 0) AS total

        FROM vendas

        WHERE data = ?
    """, (
        data,
    )).fetchone()["total"]

    # ------------------------------------------------------
    # TODOS OS GASTOS DO DIA
    # ------------------------------------------------------

    gastos = conexao.execute("""
        SELECT
            COALESCE(SUM(valor), 0) AS total

        FROM gastos

        WHERE data = ?
    """, (
        data,
    )).fetchone()["total"]

    # ------------------------------------------------------
    # SALDO ESPERADO
    # ------------------------------------------------------
    #
    # Abertura
    # + todas as vendas
    # - gastos
    #

    saldo_esperado = (
        caixa["valor_abertura"]
        + vendas
        - gastos
    )

    conexao.close()

    return {
        "caixa": caixa,
        "vendas": vendas,
        "gastos": gastos,
        "saldo_esperado": saldo_esperado
    }


# ==========================================================
# FECHAR CAIXA
# ==========================================================

def fechar_caixa(form):

    caixa_id = int(
        form.get("caixa_id")
    )

    valor_fechamento = float(
        form.get("valor_fechamento") or 0
    )

    conexao = conectar()

    # ------------------------------------------------------
    # BUSCAR OS DADOS DO CAIXA
    # ------------------------------------------------------

    caixa = conexao.execute("""
        SELECT *
        FROM caixa
        WHERE id = ?
        AND status = 'ABERTO'
    """, (
        caixa_id,
    )).fetchone()

    if not caixa:

        conexao.close()

        return False

    # ------------------------------------------------------
    # DATA DO CAIXA
    # ------------------------------------------------------

    data = caixa["data_abertura"]

    # ------------------------------------------------------
    # TODAS AS VENDAS DO DIA
    # ------------------------------------------------------

    vendas = conexao.execute("""
        SELECT
            COALESCE(SUM(valor), 0) AS total

        FROM vendas

        WHERE data = ?
    """, (
        data,
    )).fetchone()["total"]

    # ------------------------------------------------------
    # TODOS OS GASTOS DO DIA
    # ------------------------------------------------------

    gastos = conexao.execute("""
        SELECT
            COALESCE(SUM(valor), 0) AS total

        FROM gastos

        WHERE data = ?
    """, (
        data,
    )).fetchone()["total"]

    # ------------------------------------------------------
    # SALDO ESPERADO
    # ------------------------------------------------------

    saldo_esperado = (
        caixa["valor_abertura"]
        + vendas
        - gastos
    )

    # ------------------------------------------------------
    # DIFERENÇA
    # ------------------------------------------------------

    diferenca = (
        valor_fechamento
        - saldo_esperado
    )

    # ------------------------------------------------------
    # FECHAR CAIXA
    # ------------------------------------------------------

    conexao.execute("""
        UPDATE caixa

        SET
            data_fechamento = ?,
            valor_fechamento = ?,
            diferenca = ?,
            status = 'FECHADO'

        WHERE id = ?

        AND status = 'ABERTO'
    """, (
        form.get("data_fechamento"),
        valor_fechamento,
        diferenca,
        caixa_id
    ))

    conexao.commit()
    conexao.close()

    return True


# ==========================================================
# RELATÓRIO DE VENDAS
# ==========================================================

def relatorio_vendas(
    data_inicio,
    data_fim
):

    conexao = conectar()

    vendas = conexao.execute("""
        SELECT
            v.*,
            c.nome AS cliente,
            d.nome AS despachante

        FROM vendas v

        LEFT JOIN clientes c
            ON c.id = v.cliente_id

        LEFT JOIN despachantes d
            ON d.id = v.despachante_id

        WHERE v.data BETWEEN ? AND ?

        ORDER BY
            v.data DESC,
            v.id DESC
    """, (
        data_inicio,
        data_fim
    )).fetchall()

    resumo = conexao.execute("""
        SELECT
            COUNT(*) AS quantidade,

            COALESCE(
                SUM(valor),
                0
            ) AS total_bruto,

            COALESCE(
                SUM(valor_liquido),
                0
            ) AS total_liquido

        FROM vendas

        WHERE data BETWEEN ? AND ?
    """, (
        data_inicio,
        data_fim
    )).fetchone()

    conexao.close()

    return vendas, resumo


# ==========================================================
# RELATÓRIO DE GASTOS
# ==========================================================

def relatorio_gastos(
    data_inicio,
    data_fim
):

    conexao = conectar()

    gastos = conexao.execute("""
        SELECT *
        FROM gastos

        WHERE data BETWEEN ? AND ?

        ORDER BY
            data DESC,
            id DESC
    """, (
        data_inicio,
        data_fim
    )).fetchall()

    resumo = conexao.execute("""
        SELECT
            COALESCE(
                SUM(valor),
                0
            ) AS total

        FROM gastos

        WHERE data BETWEEN ? AND ?
    """, (
        data_inicio,
        data_fim
    )).fetchone()

    categorias = conexao.execute("""
        SELECT
            categoria,

            COALESCE(
                SUM(valor),
                0
            ) AS total

        FROM gastos

        WHERE data BETWEEN ? AND ?

        GROUP BY categoria

        ORDER BY total DESC
    """, (
        data_inicio,
        data_fim
    )).fetchall()

    conexao.close()

    return gastos, resumo, categorias


# ==========================================================
# RELATÓRIO DE VENDAS POR DESPACHANTE
# ==========================================================

def relatorio_despachantes(
    data_inicio,
    data_fim,
    despachante_id=None
):

    conexao = conectar()

    # ------------------------------------------------------
    # UM DESPACHANTE
    # ------------------------------------------------------

    if despachante_id:

        resultado = conexao.execute("""
            SELECT

                COALESCE(
                    d.nome,
                    'Não informado'
                ) AS despachante,

                COUNT(v.id) AS quantidade,

                COALESCE(
                    SUM(v.valor),
                    0
                ) AS total_bruto,

                COALESCE(
                    SUM(v.valor_liquido),
                    0
                ) AS total_liquido

            FROM vendas v

            LEFT JOIN despachantes d
                ON d.id = v.despachante_id

            WHERE v.data BETWEEN ? AND ?

            AND v.despachante_id = ?

            GROUP BY
                v.despachante_id

            ORDER BY
                total_bruto DESC

        """, (
            data_inicio,
            data_fim,
            despachante_id
        )).fetchall()

    # ------------------------------------------------------
    # TODOS OS DESPACHANTES
    # ------------------------------------------------------

    else:

        resultado = conexao.execute("""
            SELECT

                COALESCE(
                    d.nome,
                    'Não informado'
                ) AS despachante,

                COUNT(v.id) AS quantidade,

                COALESCE(
                    SUM(v.valor),
                    0
                ) AS total_bruto,

                COALESCE(
                    SUM(v.valor_liquido),
                    0
                ) AS total_liquido

            FROM vendas v

            LEFT JOIN despachantes d
                ON d.id = v.despachante_id

            WHERE v.data BETWEEN ? AND ?

            GROUP BY
                v.despachante_id

            ORDER BY
                total_bruto DESC

        """, (
            data_inicio,
            data_fim
        )).fetchall()

    conexao.close()

    return resultado


# ==========================================================
# RELATÓRIO DE CONTAS PENDENTES
# ==========================================================

def relatorio_pendentes():

    conexao = conectar()

    pendentes = conexao.execute("""
        SELECT
            v.*,

            c.nome AS cliente,

            d.nome AS despachante

        FROM vendas v

        LEFT JOIN clientes c
            ON c.id = v.cliente_id

        LEFT JOIN despachantes d
            ON d.id = v.despachante_id

        WHERE v.pago = 0

        ORDER BY
            v.data DESC,
            v.id DESC

    """).fetchall()

    conexao.close()

    return pendentes

def editar_cliente(cliente_id, form):
    conexao = conectar()

    conexao.execute("""
        UPDATE clientes
        SET
            nome = ?,
            telefone = ?,
            cpf_cnpj = ?,
            observacoes = ?
        WHERE id = ?
    """, (
        form.get("nome"),
        form.get("telefone"),
        form.get("cpf_cnpj"),
        form.get("observacoes"),
        cliente_id
    ))

    alterado = conexao.total_changes > 0

    conexao.commit()
    conexao.close()

    return alterado


def excluir_cliente(cliente_id):
    conexao = conectar()

    conexao.execute(
        "DELETE FROM clientes WHERE id = ?",
        (cliente_id,)
    )

    excluido = conexao.total_changes > 0

    conexao.commit()
    conexao.close()

    return excluido