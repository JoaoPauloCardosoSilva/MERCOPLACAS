import sqlite3
import os
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash


# ==========================================================
# LOCALIZAÇÃO DO BANCO
# ==========================================================

if os.environ.get("VERCEL"):
    DB = "/tmp/banco.db"
else:
    DB = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "banco.db"
    )


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
        usuario_id INTEGER,
        FOREIGN KEY(despachante_id) REFERENCES despachantes(id),
        FOREIGN KEY(cliente_id) REFERENCES clientes(id)
    );

    CREATE TABLE IF NOT EXISTS gastos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data TEXT NOT NULL,
        categoria TEXT NOT NULL,
        descricao TEXT,
        valor REAL NOT NULL,
        usuario_id INTEGER
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
        usuario_id INTEGER,
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

    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        usuario TEXT NOT NULL UNIQUE,
        senha TEXT NOT NULL,
        perfil TEXT NOT NULL DEFAULT 'Funcionário',
        ativo INTEGER NOT NULL DEFAULT 1,
        criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
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

    # ------------------------------------------------------
    # ADMINISTRADOR PADRÃO
    # ------------------------------------------------------
    # Mantém o acesso inicial do sistema sem gravar a senha
    # em texto puro no banco.
    admin_existente = cursor.execute("""
        SELECT id FROM usuarios WHERE usuario = ?
    """, ("admin",)).fetchone()

    if not admin_existente:
        cursor.execute("""
            INSERT INTO usuarios (nome, usuario, senha, perfil, ativo)
            VALUES (?, ?, ?, ?, 1)
        """, (
            "Administrador",
            "admin",
            generate_password_hash("admin123"),
            "Administrador"
        ))

    # Colunas de auditoria para bancos já existentes.
    for tabela in ["vendas", "gastos", "movimentacoes_estoque"]:
        colunas_tabela = cursor.execute(f"PRAGMA table_info({tabela})").fetchall()
        nomes = [coluna["name"] for coluna in colunas_tabela]
        if "usuario_id" not in nomes:
            cursor.execute(f"ALTER TABLE {tabela} ADD COLUMN usuario_id INTEGER")

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
            d.nome AS despachante,
            u.nome AS usuario_nome

        FROM vendas v

        LEFT JOIN clientes c
            ON c.id = v.cliente_id

        LEFT JOIN despachantes d
            ON d.id = v.despachante_id

        LEFT JOIN usuarios u
            ON u.id = v.usuario_id

        ORDER BY
            v.id DESC
    """).fetchall()

    conexao.close()

    return vendas


def cadastrar_venda(form, usuario_id=None):

    servico = form.get("servico")
    valores = {
        "Carro - par": (248.97, 166.48),
        "Unitária / Moto": (196.86, 154.60)
    }

    if servico not in valores:
        return False, "Serviço inválido. Selecione um serviço disponível."

    placa = form.get("placa", "").strip().upper()
    data_venda = form.get("data", "").strip()

    if not placa:
        return False, "Informe a placa do veículo."
    if not data_venda:
        return False, "Informe a data da venda."

    valor, valor_liquido = valores[servico]
    conexao = conectar()
    conexao.execute("""
        INSERT INTO vendas (
            despachante_id, cliente_id, placa, data, servico,
            valor, valor_liquido, forma_pagamento, pago, usuario_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        form.get("despachante_id") or None,
        form.get("cliente_id") or None,
        placa, data_venda, servico, valor, valor_liquido,
        form.get("forma_pagamento"),
        1 if form.get("pago") == "1" else 0,
        usuario_id
    ))
    conexao.commit()
    conexao.close()
    return True, "Venda cadastrada com sucesso."


# ==========================================================
# EDITAR VENDA
# ==========================================================

def editar_venda(venda_id, form):

    servico = form.get("servico")
    valores = {
        "Carro - par": (248.97, 166.48),
        "Unitária / Moto": (196.86, 154.60)
    }

    if servico not in valores:
        return False

    placa = form.get("placa", "").strip().upper()
    data_venda = form.get("data", "").strip()
    if not placa or not data_venda:
        return False

    valor, valor_liquido = valores[servico]
    conexao = conectar()
    conexao.execute("""
        UPDATE vendas
        SET despachante_id = ?, cliente_id = ?, placa = ?, data = ?,
            servico = ?, valor = ?, valor_liquido = ?,
            forma_pagamento = ?, pago = ?
        WHERE id = ?
    """, (
        form.get("despachante_id") or None,
        form.get("cliente_id") or None,
        placa, data_venda, servico, valor, valor_liquido,
        form.get("forma_pagamento"),
        1 if form.get("pago") == "1" else 0,
        venda_id
    ))
    conexao.commit()
    alterada = conexao.total_changes > 0
    conexao.close()
    return alterada


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

def listar_gastos(data_inicio=None, data_fim=None):

    conexao = conectar()

    if data_inicio and data_fim:
        gastos = conexao.execute("""
            SELECT g.*, u.nome AS usuario_nome
            FROM gastos g
            LEFT JOIN usuarios u ON u.id = g.usuario_id
            WHERE g.data BETWEEN ? AND ?
            ORDER BY g.data DESC, g.id DESC
        """, (data_inicio, data_fim)).fetchall()
    else:
        gastos = conexao.execute("""
            SELECT g.*, u.nome AS usuario_nome
            FROM gastos g
            LEFT JOIN usuarios u ON u.id = g.usuario_id
            ORDER BY g.data DESC, g.id DESC
        """).fetchall()

    conexao.close()

    return gastos


def buscar_gasto(gasto_id):

    conexao = conectar()

    gasto = conexao.execute("""
        SELECT g.*, u.nome AS usuario_nome
        FROM gastos g
        LEFT JOIN usuarios u ON u.id = g.usuario_id
        WHERE g.id = ?
    """, (gasto_id,)).fetchone()

    conexao.close()

    return gasto


def editar_gasto(gasto_id, form):

    conexao = conectar()

    conexao.execute("""
        UPDATE gastos
        SET
            data = ?,
            categoria = ?,
            descricao = ?,
            valor = ?
        WHERE id = ?
    """, (
        form.get("data"),
        form.get("categoria"),
        form.get("descricao"),
        float(form.get("valor") or 0),
        gasto_id
    ))

    conexao.commit()
    alterado = conexao.total_changes > 0
    conexao.close()

    return alterado


def excluir_gasto(gasto_id):

    conexao = conectar()

    conexao.execute("""
        DELETE FROM gastos
        WHERE id = ?
    """, (gasto_id,))

    conexao.commit()
    excluido = conexao.total_changes > 0
    conexao.close()

    return excluido


def cadastrar_gasto(form, usuario_id=None):

    conexao = conectar()

    conexao.execute("""
        INSERT INTO gastos (
            data,
            categoria,
            descricao,
            valor,
            usuario_id
        )

        VALUES (?, ?, ?, ?, ?)
    """, (
        form.get("data"),
        form.get("categoria"),
        form.get("descricao"),
        float(form.get("valor") or 0),
        usuario_id
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

    nome = (form.get("nome") or "").strip()
    categoria = (form.get("categoria") or "").strip()
    quantidade = float(form.get("quantidade") or 0)
    estoque_minimo = float(form.get("estoque_minimo") or 0)

    if not nome:
        return False, "Informe o nome do item."
    if quantidade < 0 or estoque_minimo < 0:
        return False, "Quantidade e estoque mínimo não podem ser negativos."

    conexao = conectar()
    conexao.execute("""
        INSERT INTO estoque (nome, categoria, quantidade, estoque_minimo)
        VALUES (?, ?, ?, ?)
    """, (nome, categoria, quantidade, estoque_minimo))
    conexao.commit()
    conexao.close()

    return True, "Item cadastrado no estoque."


def editar_estoque(estoque_id, form):

    nome = (form.get("nome") or "").strip()
    categoria = (form.get("categoria") or "").strip()
    quantidade = float(form.get("quantidade") or 0)
    estoque_minimo = float(form.get("estoque_minimo") or 0)

    if not nome:
        return False, "Informe o nome do item."
    if quantidade < 0 or estoque_minimo < 0:
        return False, "Quantidade e estoque mínimo não podem ser negativos."

    conexao = conectar()
    cursor = conexao.execute("""
        UPDATE estoque
        SET nome = ?, categoria = ?, quantidade = ?, estoque_minimo = ?
        WHERE id = ?
    """, (nome, categoria, quantidade, estoque_minimo, estoque_id))
    conexao.commit()
    alterado = cursor.rowcount > 0
    conexao.close()

    return (True, "Item alterado com sucesso.") if alterado else (False, "Item não encontrado.")


def excluir_estoque(estoque_id):

    conexao = conectar()
    existe = conexao.execute("SELECT id FROM estoque WHERE id = ?", (estoque_id,)).fetchone()

    if not existe:
        conexao.close()
        return False, "Item não encontrado."

    movimentos = conexao.execute(
        "SELECT COUNT(*) AS total FROM movimentacoes_estoque WHERE estoque_id = ?",
        (estoque_id,)
    ).fetchone()["total"]

    if movimentos > 0:
        conexao.close()
        return False, "Não é possível excluir um item que possui movimentações."

    conexao.execute("DELETE FROM estoque WHERE id = ?", (estoque_id,))
    conexao.commit()
    conexao.close()

    return True, "Item excluído com sucesso."


def registrar_movimentacao_estoque(form, usuario_id=None):

    try:
        estoque_id = int(form.get("estoque_id"))
        quantidade = float(form.get("quantidade") or 0)
    except (ValueError, TypeError):
        return False, "Informe uma quantidade válida."

    tipo = form.get("tipo")
    data_movimento = (form.get("data") or "").strip()

    if quantidade <= 0:
        return False, "A quantidade deve ser maior que zero."
    if tipo not in ("ENTRADA", "SAIDA"):
        return False, "Tipo de movimentação inválido."
    if not data_movimento:
        return False, "Informe a data da movimentação."

    conexao = conectar()
    item = conexao.execute(
        "SELECT nome, quantidade FROM estoque WHERE id = ?",
        (estoque_id,)
    ).fetchone()

    if not item:
        conexao.close()
        return False, "Item do estoque não encontrado."

    if tipo == "SAIDA" and quantidade > item["quantidade"]:
        conexao.close()
        return False, f"Estoque insuficiente. Saldo atual: {item['quantidade']:g}."

    quantidade_final = quantidade if tipo == "ENTRADA" else -quantidade

    conexao.execute("""
        UPDATE estoque
        SET quantidade = quantidade + ?
        WHERE id = ?
    """, (quantidade_final, estoque_id))

    conexao.execute("""
        INSERT INTO movimentacoes_estoque
            (estoque_id, data, tipo, quantidade, observacao, usuario_id)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        estoque_id,
        data_movimento,
        tipo,
        quantidade,
        form.get("observacao"),
        usuario_id
    ))

    conexao.commit()
    conexao.close()

    texto = "Entrada" if tipo == "ENTRADA" else "Saída"
    return True, f"{texto} de estoque registrada com sucesso."


def listar_movimentacoes_estoque():
    conexao = conectar()
    movimentacoes = conexao.execute("""
        SELECT
            m.*,
            e.nome AS estoque_nome,
            u.nome AS usuario_nome
        FROM movimentacoes_estoque m
        LEFT JOIN estoque e ON e.id = m.estoque_id
        LEFT JOIN usuarios u ON u.id = m.usuario_id
        ORDER BY m.data DESC, m.id DESC
    """).fetchall()
    conexao.close()
    return movimentacoes


# ==========================================================
# CAIXA
# ==========================================================

def listar_caixa():

    conexao = conectar()

    caixas = conexao.execute("""
        SELECT
            c.*,

            COALESCE((
                SELECT SUM(v.valor)
                FROM vendas v
                WHERE v.data = c.data_abertura
            ), 0) AS total_vendas,

            COALESCE((
                SELECT SUM(g.valor)
                FROM gastos g
                WHERE g.data = c.data_abertura
            ), 0) AS total_gastos,

            (
                c.valor_abertura
                + COALESCE((
                    SELECT SUM(v.valor)
                    FROM vendas v
                    WHERE v.data = c.data_abertura
                ), 0)
                - COALESCE((
                    SELECT SUM(g.valor)
                    FROM gastos g
                    WHERE g.data = c.data_abertura
                ), 0)
            ) AS saldo_esperado

        FROM caixa c
        ORDER BY c.id DESC
    """).fetchall()

    conexao.close()

    return caixas


def abrir_caixa(form):

    conexao = conectar()

    # ------------------------------------------------------
    # VERIFICAR SE JÁ EXISTE UM CAIXA ABERTO
    # ------------------------------------------------------

    caixa_aberto = conexao.execute("""
        SELECT id
        FROM caixa
        WHERE status = 'ABERTO'
        LIMIT 1
    """).fetchone()

    if caixa_aberto:
        conexao.close()
        return False, "Já existe um caixa aberto."

    # ------------------------------------------------------
    # DATA E VALOR
    # ------------------------------------------------------

    data_abertura = form.get("data_abertura") or date.today().isoformat()
    valor_abertura = float(form.get("valor_abertura") or 0)

    # ------------------------------------------------------
    # ABRIR CAIXA
    # ------------------------------------------------------

    conexao.execute("""
        INSERT INTO caixa (
            data_abertura,
            valor_abertura,
            status
        )
        VALUES (?, ?, 'ABERTO')
    """, (
        data_abertura,
        valor_abertura
    ))

    conexao.commit()
    conexao.close()

    return True, "Caixa aberto com sucesso."

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

    caixa_id = int(form.get("caixa_id"))

    valor_fechamento = float(
        form.get("valor_fechamento") or 0
    )

    conexao = conectar()

    # ------------------------------------------------------
    # BUSCAR CAIXA ABERTO
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
        return False, "Caixa aberto não encontrado."

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
        date.today().isoformat(),
        valor_fechamento,
        diferenca,
        caixa_id
    ))

    conexao.commit()
    conexao.close()

    return True, "Caixa fechado com sucesso."


# ==========================================================
# RELATÓRIO DE VENDAS
# ==========================================================

def relatorio_vendas(data_inicio, data_fim):

    conexao = conectar()

    vendas = conexao.execute("""
        SELECT
            v.*,
            c.nome AS cliente_nome,
            d.nome AS despachante_nome
        FROM vendas v
        LEFT JOIN clientes c
            ON c.id = v.cliente_id
        LEFT JOIN despachantes d
            ON d.id = v.despachante_id
        WHERE v.data BETWEEN ? AND ?
        ORDER BY v.data DESC, v.id DESC
    """, (data_inicio, data_fim)).fetchall()

    resumo = conexao.execute("""
        SELECT
            COUNT(*) AS total_vendas,
            COALESCE(SUM(valor), 0) AS valor_bruto,
            COALESCE(SUM(valor_liquido), 0) AS valor_liquido
        FROM vendas
        WHERE data BETWEEN ? AND ?
    """, (data_inicio, data_fim)).fetchone()

    conexao.close()

    return vendas, resumo


# ==========================================================
# RELATÓRIO DE GASTOS
# ==========================================================

def relatorio_gastos(data_inicio, data_fim):

    conexao = conectar()

    gastos = conexao.execute("""
        SELECT *
        FROM gastos
        WHERE data BETWEEN ? AND ?
        ORDER BY data DESC, id DESC
    """, (data_inicio, data_fim)).fetchall()

    resumo = conexao.execute("""
        SELECT
            COUNT(*) AS total_gastos,
            COALESCE(SUM(valor), 0) AS valor_total
        FROM gastos
        WHERE data BETWEEN ? AND ?
    """, (data_inicio, data_fim)).fetchone()

    categorias = conexao.execute("""
        SELECT
            categoria,
            COALESCE(SUM(valor), 0) AS total
        FROM gastos
        WHERE data BETWEEN ? AND ?
        GROUP BY categoria
        ORDER BY total DESC
    """, (data_inicio, data_fim)).fetchall()

    conexao.close()

    return gastos, resumo, categorias


# ==========================================================
# RELATÓRIO DE VENDAS POR DESPACHANTE
# ==========================================================

def relatorio_despachantes(data_inicio, data_fim, despachante_id=None):

    conexao = conectar()

    sql = """
        SELECT
            d.nome AS despachante_nome,
            COUNT(v.id) AS total_vendas,
            COALESCE(SUM(v.valor), 0) AS valor_bruto,
            COALESCE(SUM(v.valor_liquido), 0) AS valor_liquido
        FROM vendas v
        LEFT JOIN despachantes d
            ON d.id = v.despachante_id
        WHERE v.data BETWEEN ? AND ?
    """

    parametros = [data_inicio, data_fim]

    if despachante_id:
        sql += " AND v.despachante_id = ? "
        parametros.append(int(despachante_id))

    sql += """
        GROUP BY v.despachante_id, d.nome
        ORDER BY valor_bruto DESC
    """

    resultado = conexao.execute(sql, parametros).fetchall()

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

            c.nome AS cliente_nome,

            d.nome AS despachante_nome

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

# ==========================================================
# USUÁRIOS
# ==========================================================

def listar_usuarios():
    conexao = conectar()
    usuarios = conexao.execute("""
        SELECT id, nome, usuario, perfil, ativo, criado_em
        FROM usuarios
        ORDER BY nome
    """).fetchall()
    conexao.close()
    return usuarios


def buscar_usuario_login(usuario, senha):
    conexao = conectar()
    registro = conexao.execute("""
        SELECT *
        FROM usuarios
        WHERE usuario = ? AND ativo = 1
    """, (usuario,)).fetchone()
    conexao.close()

    if registro and check_password_hash(registro["senha"], senha):
        return registro

    return None


def buscar_usuario(usuario_id):
    conexao = conectar()
    registro = conexao.execute("""
        SELECT * FROM usuarios WHERE id = ?
    """, (usuario_id,)).fetchone()
    conexao.close()
    return registro


def cadastrar_usuario(form):
    conexao = conectar()
    try:
        conexao.execute("""
            INSERT INTO usuarios (nome, usuario, senha, perfil, ativo)
            VALUES (?, ?, ?, ?, ?)
        """, (
            form.get("nome"),
            form.get("usuario"),
            generate_password_hash(form.get("senha")),
            form.get("perfil", "Funcionário"),
            1 if form.get("ativo", "1") == "1" else 0
        ))
        conexao.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conexao.close()


def editar_usuario(usuario_id, form):
    conexao = conectar()
    try:
        senha = form.get("senha", "").strip()
        if senha:
            conexao.execute("""
                UPDATE usuarios
                SET nome = ?, usuario = ?, senha = ?, perfil = ?, ativo = ?
                WHERE id = ?
            """, (
                form.get("nome"),
                form.get("usuario"),
                generate_password_hash(senha),
                form.get("perfil", "Funcionário"),
                1 if form.get("ativo", "1") == "1" else 0,
                usuario_id
            ))
        else:
            conexao.execute("""
                UPDATE usuarios
                SET nome = ?, usuario = ?, perfil = ?, ativo = ?
                WHERE id = ?
            """, (
                form.get("nome"),
                form.get("usuario"),
                form.get("perfil", "Funcionário"),
                1 if form.get("ativo", "1") == "1" else 0,
                usuario_id
            ))
        conexao.commit()
        return conexao.total_changes > 0
    except sqlite3.IntegrityError:
        return False
    finally:
        conexao.close()


def alterar_status_usuario(usuario_id):
    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("SELECT id, perfil, ativo FROM usuarios WHERE id = ?", (usuario_id,))
    usuario = cursor.fetchone()

    if usuario is None:
        conexao.close()
        return False, "Usuário não encontrado."

    if usuario["ativo"] == 1 and usuario["perfil"] == "Administrador":
        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM usuarios
            WHERE perfil = 'Administrador' AND ativo = 1
        """)
        total_admins = cursor.fetchone()["total"]

        if total_admins <= 1:
            conexao.close()
            return False, "Não é possível desativar o último administrador ativo."

    novo_status = 0 if usuario["ativo"] == 1 else 1

    cursor.execute(
        "UPDATE usuarios SET ativo = ? WHERE id = ?",
        (novo_status, usuario_id)
    )

    conexao.commit()
    conexao.close()
    return True, "Status alterado com sucesso."

def excluir_usuario(usuario_id):
    conexao = conectar()
    usuario = conexao.execute("SELECT perfil, ativo FROM usuarios WHERE id = ?", (usuario_id,)).fetchone()
    if not usuario:
        conexao.close()
        return False

    if usuario["perfil"] == "Administrador" and usuario["ativo"] == 1:
        total_admin = conexao.execute("""
            SELECT COUNT(*) AS total FROM usuarios
            WHERE perfil = 'Administrador' AND ativo = 1
        """).fetchone()["total"]
        if total_admin <= 1:
            conexao.close()
            return False

    conexao.execute("DELETE FROM usuarios WHERE id = ?", (usuario_id,))
    sucesso = conexao.total_changes > 0
    conexao.commit()
    conexao.close()
    return sucesso
