from flask import Flask, render_template, request, redirect, url_for, session, flash
from functools import wraps
from datetime import date

from io import BytesIO
from flask import send_file
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from database.banco import (
    inicializar_banco,
    buscar_dashboard,
    listar_vendas,
    cadastrar_venda,
    listar_clientes,
    cadastrar_cliente,
    editar_cliente,
    excluir_cliente,
    listar_despachantes,
    cadastrar_despachante,
    listar_gastos,
    cadastrar_gasto,
    editar_gasto,
    excluir_gasto,
    buscar_gasto,
    listar_estoque,
    cadastrar_estoque,
    editar_estoque,
    excluir_estoque,
    registrar_movimentacao_estoque,
    listar_movimentacoes_estoque,
    listar_caixa,
    abrir_caixa,
    fechar_caixa,
    dados_fechamento_caixa,
    relatorio_vendas,
    relatorio_gastos,
    relatorio_despachantes,
    relatorio_pendentes,
    editar_venda,
    excluir_venda,
    listar_usuarios,
    buscar_usuario_login,
    buscar_usuario,
    cadastrar_usuario,
    editar_usuario,
    alterar_status_usuario,
    excluir_usuario
)

app = Flask(__name__)

app.secret_key = "mercoplacas-chave-secreta"

inicializar_banco()


def login_obrigatorio(funcao):
    @wraps(funcao)
    def verificar_login(*args, **kwargs):

        if not session.get("logado") or not session.get("usuario_id"):
            session.clear()
            return redirect(url_for("login"))

        return funcao(*args, **kwargs)

    return verificar_login


def administrador_obrigatorio(funcao):
    @wraps(funcao)
    def verificar_administrador(*args, **kwargs):
        if not session.get("logado") or not session.get("usuario_id"):
            session.clear()
            return redirect(url_for("login"))

        if session.get("usuario_perfil") != "Administrador":
            flash("Acesso permitido somente para administradores.", "erro")
            return redirect(url_for("vendas"))

        return funcao(*args, **kwargs)

    return verificar_administrador


@app.route("/")
def inicio():

    if session.get("logado") and session.get("usuario_id"):
        if session.get("usuario_perfil") == "Administrador":
            return redirect(url_for("dashboard"))
        return redirect(url_for("vendas"))

    session.clear()
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        usuario = request.form.get("usuario", "").strip()
        senha = request.form.get("senha", "")

        registro = buscar_usuario_login(usuario, senha)

        if registro:
            session.clear()
            session["logado"] = True
            session["usuario_id"] = registro["id"]
            session["usuario_nome"] = registro["nome"]
            session["usuario_perfil"] = registro["perfil"]

            if registro["perfil"] == "Administrador":
                return redirect(url_for("dashboard"))

            return redirect(url_for("vendas"))

        flash("Usuário ou senha inválidos, ou usuário desativado.", "erro")

    return render_template("login.html")

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


# ==========================================================
# USUÁRIOS
# ==========================================================

@app.route("/usuarios", methods=["GET", "POST"])
@administrador_obrigatorio
def usuarios():

    if request.method == "POST":
        acao = request.form.get("acao")

        if acao == "cadastrar":
            if cadastrar_usuario(request.form):
                flash("Usuário cadastrado com sucesso.", "sucesso")
            else:
                flash("Não foi possível cadastrar. Verifique se o nome de usuário já existe.", "erro")

        elif acao == "editar":
            usuario_id = int(request.form.get("usuario_id"))
            if usuario_id == session.get("usuario_id") and request.form.get("perfil") != "Administrador":
                flash("Você não pode remover seu próprio perfil de administrador.", "erro")
                return redirect(url_for("usuarios", editar=usuario_id))

            if usuario_id == session.get("usuario_id") and request.form.get("ativo") != "1":
                flash("Você não pode desativar seu próprio usuário.", "erro")
            elif editar_usuario(usuario_id, request.form):
                flash("Usuário alterado com sucesso.", "sucesso")
            else:
                flash("Não foi possível alterar o usuário.", "erro")

        elif acao == "status":
            usuario_id = int(request.form.get("usuario_id"))
            if usuario_id == session.get("usuario_id"):
                flash("Você não pode desativar seu próprio usuário.", "erro")
            elif alterar_status_usuario(usuario_id):
                flash("Status do usuário alterado.", "sucesso")
            else:
                flash("Usuário não encontrado.", "erro")

        elif acao == "excluir":
            usuario_id = int(request.form.get("usuario_id"))
            if usuario_id == session.get("usuario_id"):
                flash("Você não pode excluir o usuário conectado.", "erro")
            elif excluir_usuario(usuario_id):
                flash("Usuário excluído com sucesso.", "sucesso")
            else:
                flash("Não é possível excluir este usuário. O sistema precisa manter pelo menos um administrador ativo.", "erro")

        return redirect(url_for("usuarios"))

    editar_id = request.args.get("editar", type=int)
    usuario_edicao = buscar_usuario(editar_id) if editar_id else None

    return render_template(
        "usuarios.html",
        usuarios=listar_usuarios(),
        usuario_edicao=usuario_edicao
    )


# ==========================================================
# DASHBOARD
# ==========================================================

@app.route("/dashboard")
@administrador_obrigatorio
def dashboard():

    dados = buscar_dashboard()

    return render_template(
        "dashboard.html",
        dados=dados
    )


# ==========================================================
# VENDAS
# ==========================================================

@app.route("/vendas", methods=["GET", "POST"])
@login_obrigatorio
def vendas():

    if request.method == "POST":

        sucesso, mensagem = cadastrar_venda(
            request.form,
            session.get("usuario_id")
        )

        flash(mensagem, "sucesso" if sucesso else "erro")
        return redirect(url_for("vendas"))

    return render_template(
        "vendas.html",
        vendas=listar_vendas(),
        clientes=listar_clientes(),
        despachantes=listar_despachantes(),
        venda_edicao=None,
        hoje=date.today().isoformat()
    )


# ==========================================================
# EDITAR VENDA
# ==========================================================

@app.route("/vendas/editar/<int:venda_id>", methods=["GET", "POST"])
@login_obrigatorio
def editar_venda_rota(venda_id):

    vendas = listar_vendas()

    venda = None

    for item in vendas:

        if item["id"] == venda_id:
            venda = item
            break

    if venda is None:

        flash(
            "Venda não encontrada.",
            "erro"
        )

        return redirect(url_for("vendas"))

    if request.method == "POST":

        sucesso = editar_venda(
            venda_id,
            request.form
        )

        if sucesso:

            flash(
                "Venda alterada com sucesso.",
                "sucesso"
            )

        else:

            flash(
                "Não foi possível alterar a venda.",
                "erro"
            )

        return redirect(url_for("vendas"))

    return render_template(
        "vendas.html",
        vendas=vendas,
        clientes=listar_clientes(),
        despachantes=listar_despachantes(),
        venda_edicao=venda,
        hoje=date.today().isoformat()
    )


# ==========================================================
# EXCLUIR VENDA
# ==========================================================

@app.route("/vendas/excluir/<int:venda_id>", methods=["POST"])
@login_obrigatorio
def excluir_venda_rota(venda_id):

    sucesso = excluir_venda(venda_id)

    if sucesso:

        flash(
            "Venda excluída com sucesso.",
            "sucesso"
        )

    else:

        flash(
            "Venda não encontrada.",
            "erro"
        )

    return redirect(url_for("vendas"))


# ==========================================================
# CLIENTES
# ==========================================================

@app.route("/clientes", methods=["GET", "POST"])
@login_obrigatorio
def clientes():
    if request.method == "POST":
        cadastrar_cliente(request.form)
        flash("Cliente cadastrado com sucesso.", "sucesso")
        return redirect(url_for("clientes"))

    return render_template(
        "clientes.html",
        clientes=listar_clientes(),
        cliente_edicao=None
    )


@app.route("/clientes/editar/<int:cliente_id>", methods=["GET", "POST"])
@login_obrigatorio
def editar_cliente_rota(cliente_id):

    clientes_lista = listar_clientes()

    cliente = None

    for item in clientes_lista:
        if item["id"] == cliente_id:
            cliente = item
            break

    if cliente is None:
        flash("Cliente não encontrado.", "erro")
        return redirect(url_for("clientes"))

    if request.method == "POST":

        sucesso = editar_cliente(
            cliente_id,
            request.form
        )

        if sucesso:
            flash(
                "Cliente alterado com sucesso.",
                "sucesso"
            )
        else:
            flash(
                "Não foi possível alterar o cliente.",
                "erro"
            )

        return redirect(url_for("clientes"))

    return render_template(
        "clientes.html",
        clientes=clientes_lista,
        cliente_edicao=cliente
    )


@app.route("/clientes/excluir/<int:cliente_id>", methods=["POST"])
@login_obrigatorio
def excluir_cliente_rota(cliente_id):

    sucesso = excluir_cliente(cliente_id)

    if sucesso:
        flash(
            "Cliente excluído com sucesso.",
            "sucesso"
        )
    else:
        flash(
            "Cliente não encontrado.",
            "erro"
        )

    return redirect(url_for("clientes"))


# ==========================================================
# DESPACHANTES
# ==========================================================

@app.route("/despachantes", methods=["GET", "POST"])
@login_obrigatorio
def despachantes():

    if request.method == "POST":

        cadastrar_despachante(request.form)

        flash(
            "Despachante cadastrado com sucesso.",
            "sucesso"
        )

        return redirect(url_for("despachantes"))

    return render_template(
        "despachantes.html",
        despachantes=listar_despachantes()
    )


# ==========================================================
# GASTOS
# ==========================================================

@app.route("/gastos", methods=["GET", "POST"])
@login_obrigatorio
def gastos():

    if request.method == "POST":

        cadastrar_gasto(request.form, session.get("usuario_id"))

        flash(
            "Gasto cadastrado com sucesso.",
            "sucesso"
        )

        return redirect(url_for("gastos"))

    hoje = date.today().isoformat()
    data_inicio = request.args.get("data_inicio", hoje)
    data_fim = request.args.get("data_fim", hoje)

    gastos_lista = listar_gastos(data_inicio, data_fim) if data_inicio and data_fim else listar_gastos()

    return render_template(
        "gastos.html",
        gastos=gastos_lista,
        data_inicio=data_inicio,
        data_fim=data_fim,
        hoje=hoje
    )


@app.route("/gastos/editar/<int:gasto_id>", methods=["GET", "POST"])
@login_obrigatorio
def editar_gasto_rota(gasto_id):

    gasto = buscar_gasto(gasto_id)

    if not gasto:
        flash("Gasto não encontrado.", "erro")
        return redirect(url_for("gastos"))

    if request.method == "POST":

        if editar_gasto(gasto_id, request.form):
            flash("Gasto alterado com sucesso.", "sucesso")
        else:
            flash("Não foi possível alterar o gasto.", "erro")

        return redirect(url_for("gastos"))

    return render_template(
        "gasto_editar.html",
        gasto=gasto
    )


@app.route("/gastos/excluir/<int:gasto_id>", methods=["POST"])
@login_obrigatorio
def excluir_gasto_rota(gasto_id):

    if excluir_gasto(gasto_id):
        flash("Gasto excluído com sucesso.", "sucesso")
    else:
        flash("Gasto não encontrado.", "erro")

    return redirect(url_for("gastos"))


# ==========================================================
# ESTOQUE
# ==========================================================

@app.route("/estoque", methods=["GET", "POST"])
@login_obrigatorio
def estoque():

    if request.method == "POST":

        acao = request.form.get("acao")

        try:
            if acao == "movimentar":
                sucesso, mensagem = registrar_movimentacao_estoque(
                    request.form,
                    session.get("usuario_id")
                )
                flash(mensagem, "sucesso" if sucesso else "erro")

            else:
                sucesso, mensagem = cadastrar_estoque(request.form)
                flash(mensagem, "sucesso" if sucesso else "erro")

        except (ValueError, TypeError):
            flash("Informe valores válidos para o estoque.", "erro")

        return redirect(url_for("estoque"))

    return render_template(
        "estoque.html",
        estoque=listar_estoque(),
        movimentacoes=listar_movimentacoes_estoque(),
        hoje=date.today().isoformat()
    )


@app.route("/estoque/editar/<int:estoque_id>", methods=["GET", "POST"])
@login_obrigatorio
def editar_estoque_rota(estoque_id):

    item = next((x for x in listar_estoque() if x["id"] == estoque_id), None)

    if item is None:
        flash("Item do estoque não encontrado.", "erro")
        return redirect(url_for("estoque"))

    if request.method == "POST":
        try:
            sucesso, mensagem = editar_estoque(estoque_id, request.form)
            flash(mensagem, "sucesso" if sucesso else "erro")
        except (ValueError, TypeError):
            flash("Informe valores válidos para o estoque.", "erro")
        return redirect(url_for("estoque"))

    return render_template("estoque_editar.html", item=item)


@app.route("/estoque/excluir/<int:estoque_id>", methods=["POST"])
@login_obrigatorio
def excluir_estoque_rota(estoque_id):
    sucesso, mensagem = excluir_estoque(estoque_id)
    flash(mensagem, "sucesso" if sucesso else "erro")
    return redirect(url_for("estoque"))


# ==========================================================
# CAIXA
# ==========================================================

@app.route("/caixa", methods=["GET", "POST"])
@login_obrigatorio
@administrador_obrigatorio
def caixa():

    if request.method == "POST":

        acao = request.form.get("acao")

        # ==================================================
        # ABRIR CAIXA
        # ==================================================

        if acao == "abrir":

            sucesso, mensagem = abrir_caixa(request.form)

            flash(
                mensagem,
                "sucesso" if sucesso else "erro"
            )

        # ==================================================
        # FECHAR CAIXA
        # ==================================================

        elif acao == "fechar":

            sucesso, mensagem = fechar_caixa(request.form)

            flash(
                mensagem,
                "sucesso" if sucesso else "erro"
            )

        return redirect(url_for("caixa"))

    # ======================================================
    # EXIBIR CAIXA
    # ======================================================

    caixas = listar_caixa()

    return render_template(
        "caixa.html",
        caixas=caixas
    )


# ==========================================================
# RELATÓRIOS
# ==========================================================

@app.route("/relatorios", methods=["GET", "POST"])
@login_obrigatorio
@administrador_obrigatorio
def relatorios():

    tipo = None
    data_inicio = None
    data_fim = None
    despachante_id = None
    resultado = None

    if request.method == "POST":

        tipo = request.form.get("tipo")
        data_inicio = request.form.get("data_inicio")
        data_fim = request.form.get("data_fim")
        despachante_id = request.form.get("despachante_id")

        # ==============================
        # RELATÓRIO DE VENDAS
        # ==============================
        if tipo == "vendas":

            vendas, resumo = relatorio_vendas(
                data_inicio,
                data_fim
            )

            resultado = {
                "tipo": "vendas",
                "vendas": vendas,
                "resumo": resumo
            }

        # ==============================
        # RELATÓRIO DE GASTOS
        # ==============================
        elif tipo == "gastos":

            gastos, resumo, categorias = relatorio_gastos(
                data_inicio,
                data_fim
            )

            resultado = {
                "tipo": "gastos",
                "gastos": gastos,
                "resumo": resumo,
                "categorias": categorias
            }

        # ==============================
        # RELATÓRIO POR DESPACHANTE
        # ==============================
        elif tipo == "despachantes":

            dados = relatorio_despachantes(
                data_inicio,
                data_fim,
                despachante_id
            )

            resultado = {
                "tipo": "despachantes",
                "dados": dados
            }

        # ==============================
        # CONTAS PENDENTES
        # ==============================
        elif tipo == "pendentes":

            pendentes = relatorio_pendentes()

            resultado = {
                "tipo": "pendentes",
                "pendentes": pendentes
            }

    # ==============================
    # SEMPRE RETORNA A PÁGINA
    # ==============================

    return render_template(
        "relatorios.html",
        resultado=resultado,
        data_inicio=data_inicio,
        data_fim=data_fim,
        despachantes=listar_despachantes(),
        despachante_id=despachante_id
    )


# ==========================================================
# PDF - RELATÓRIO DE VENDAS
# ==========================================================

@app.route("/relatorios/vendas/pdf")
@login_obrigatorio
@administrador_obrigatorio
def relatorio_vendas_pdf():

    data_inicio = request.args.get("data_inicio")
    data_fim = request.args.get("data_fim")

    if not data_inicio or not data_fim:
        return "Informe o período do relatório.", 400

    vendas, resumo = relatorio_vendas(data_inicio, data_fim)

    memoria = BytesIO()

    documento = SimpleDocTemplate(
        memoria,
        pagesize=landscape(A4),
        rightMargin=25,
        leftMargin=25,
        topMargin=25,
        bottomMargin=25
    )

    estilos = getSampleStyleSheet()

    titulo = ParagraphStyle(
        "TituloVendasPDF",
        parent=estilos["Title"],
        alignment=TA_CENTER,
        fontSize=20,
        spaceAfter=6
    )

    subtitulo = ParagraphStyle(
        "SubtituloVendasPDF",
        parent=estilos["Normal"],
        alignment=TA_CENTER,
        fontSize=10,
        spaceAfter=15
    )

    direita = ParagraphStyle(
        "DireitaVendasPDF",
        parent=estilos["Normal"],
        alignment=TA_RIGHT
    )

    elementos = []
    elementos.append(Paragraph("MERCOPLACAS", titulo))
    elementos.append(Paragraph("RELATÓRIO DE VENDAS", subtitulo))

    data_inicio_br = f"{data_inicio[8:10]}/{data_inicio[5:7]}/{data_inicio[0:4]}"
    data_fim_br = f"{data_fim[8:10]}/{data_fim[5:7]}/{data_fim[0:4]}"

    elementos.append(Paragraph(
        f"<b>Período:</b> {data_inicio_br} até {data_fim_br}",
        estilos["Normal"]
    ))
    elementos.append(Spacer(1, 12))

    def moeda(valor):
        return f"R$ {float(valor or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    resumo_dados = [
        ["TOTAL DE VENDAS", "VALOR BRUTO", "VALOR LÍQUIDO"],
        [
            str(resumo["total_vendas"]),
            moeda(resumo["valor_bruto"]),
            moeda(resumo["valor_liquido"])
        ]
    ]

    tabela_resumo = Table(resumo_dados, colWidths=[220, 220, 220])
    tabela_resumo.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a5f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    elementos.append(tabela_resumo)
    elementos.append(Spacer(1, 18))

    dados = [["Data", "Despachante", "Cliente", "Placa", "Serviço", "Pagamento", "Status", "Valor"]]

    for venda in vendas:
        data = venda["data"]
        data_br = f"{data[8:10]}/{data[5:7]}/{data[0:4]}" if data else "-"
        status = "PAGO" if venda["pago"] else "PENDENTE"
        dados.append([
            data_br,
            venda["despachante_nome"] or "Não informado",
            venda["cliente_nome"] or "Não informado",
            venda["placa"] or "-",
            venda["servico"] or "-",
            venda["forma_pagamento"] or "-",
            status,
            moeda(venda["valor"])
        ])

    tabela = Table(
        dados,
        repeatRows=1,
        colWidths=[65, 120, 130, 75, 115, 90, 70, 80]
    )
    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a5f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (-1, 1), (-1, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))

    elementos.append(tabela)
    elementos.append(Spacer(1, 15))
    elementos.append(Paragraph("Relatório gerado pelo Sistema MERCOPLACAS", direita))

    documento.build(elementos)
    memoria.seek(0)

    nome_arquivo = f"relatorio_vendas_{data_inicio}_{data_fim}.pdf"

    return send_file(
        memoria,
        as_attachment=True,
        download_name=nome_arquivo,
        mimetype="application/pdf"
    )


# ==========================================================
# PDF - RELATÓRIO DE GASTOS
# ==========================================================

@app.route("/relatorios/gastos/pdf")
@login_obrigatorio
@administrador_obrigatorio
def relatorio_gastos_pdf():

    data_inicio = request.args.get("data_inicio")
    data_fim = request.args.get("data_fim")

    if not data_inicio or not data_fim:
        return "Informe o período do relatório.", 400

    gastos, resumo, categorias = relatorio_gastos(data_inicio, data_fim)

    memoria = BytesIO()

    documento = SimpleDocTemplate(
        memoria,
        pagesize=landscape(A4),
        rightMargin=25,
        leftMargin=25,
        topMargin=25,
        bottomMargin=25
    )

    estilos = getSampleStyleSheet()

    titulo = ParagraphStyle(
        "TituloGastosPDF",
        parent=estilos["Title"],
        alignment=TA_CENTER,
        fontSize=20,
        spaceAfter=6
    )

    subtitulo = ParagraphStyle(
        "SubtituloGastosPDF",
        parent=estilos["Normal"],
        alignment=TA_CENTER,
        fontSize=10,
        spaceAfter=15
    )

    direita = ParagraphStyle(
        "DireitaGastosPDF",
        parent=estilos["Normal"],
        alignment=TA_RIGHT
    )

    def moeda(valor):
        return f"R$ {float(valor or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    elementos = []
    elementos.append(Paragraph("MERCOPLACAS", titulo))
    elementos.append(Paragraph("RELATÓRIO DE GASTOS", subtitulo))

    data_inicio_br = f"{data_inicio[8:10]}/{data_inicio[5:7]}/{data_inicio[0:4]}"
    data_fim_br = f"{data_fim[8:10]}/{data_fim[5:7]}/{data_fim[0:4]}"

    elementos.append(Paragraph(
        f"<b>Período:</b> {data_inicio_br} até {data_fim_br}",
        estilos["Normal"]
    ))
    elementos.append(Spacer(1, 12))

    resumo_dados = [
        ["TOTAL DE GASTOS", "VALOR TOTAL"],
        [str(resumo["total_gastos"]), moeda(resumo["valor_total"])]
    ]

    tabela_resumo = Table(resumo_dados, colWidths=[330, 330])
    tabela_resumo.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a5f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    elementos.append(tabela_resumo)
    elementos.append(Spacer(1, 18))

    dados = [["Data", "Categoria", "Descrição", "Valor"]]

    for gasto in gastos:
        data = gasto["data"]
        data_br = f"{data[8:10]}/{data[5:7]}/{data[0:4]}" if data else "-"
        dados.append([
            data_br,
            gasto["categoria"] or "-",
            gasto["descricao"] or "-",
            moeda(gasto["valor"])
        ])

    if len(dados) == 1:
        dados.append(["-", "-", "Nenhum gasto encontrado no período.", "R$ 0,00"])

    tabela = Table(
        dados,
        repeatRows=1,
        colWidths=[80, 150, 400, 90]
    )
    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a5f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (-1, 1), (-1, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    elementos.append(tabela)
    elementos.append(Spacer(1, 15))
    elementos.append(Paragraph("Relatório gerado pelo Sistema MERCOPLACAS", direita))

    documento.build(elementos)
    memoria.seek(0)

    nome_arquivo = f"relatorio_gastos_{data_inicio}_{data_fim}.pdf"

    return send_file(
        memoria,
        as_attachment=True,
        download_name=nome_arquivo,
        mimetype="application/pdf"
    )


if __name__ == "__main__":
    app.run(debug=True)