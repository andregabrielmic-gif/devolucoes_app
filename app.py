import os
from flask import Flask, render_template, redirect, url_for, request, session, flash, send_file
from config import Config
from models import db, Usuario, Devolucao, DevolucaoPDF
from datetime import datetime, timezone, timedelta
from functools import wraps
from werkzeug.utils import secure_filename

# --- MIGRATE ---
from flask_migrate import Migrate

# --- RELATÓRIO EM PDF (SOMENTE GERENTE) ---
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from io import BytesIO

app = Flask(__name__)
app.config.from_object(Config)

# --- CORREÇÃO: caminho absoluto para uploads ---
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'static', 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db.init_app(app)

migrate = Migrate(app, db)

with app.app_context():
    db.create_all()

# --- Fuso horário de Brasília (UTC-3) ---
BRASILIA = timezone(timedelta(hours=-3))

def agora_brasilia():
    return datetime.now(timezone.utc).astimezone(BRASILIA).replace(tzinfo=None)

# Decorators
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session: return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def roles_required(*perfis):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if session.get('perfil') not in perfis:
                flash("Acesso restrito.")
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- ROTAS DE ACESSO ---
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = Usuario.query.filter_by(email=request.form['email']).first()
        if user and user.check_senha(request.form['senha']):
            session.update({'user_id': user.id, 'perfil': user.perfil, 'nome': user.nome})
            return redirect(url_for('dashboard'))
        flash("Email ou senha inválidos.")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    busca = request.args.get('q', '')
    status_filtro = request.args.get('status', '')

    query = Devolucao.query

    if session['perfil'] == 'vendedor':
        query = query.filter(Devolucao.vendedor_id == session['user_id'])

    if busca:
        query = query.filter(
            (Devolucao.cliente.ilike(f'%{busca}%')) |
            (Devolucao.nf_cliente.ilike(f'%{busca}%')) |
            (Devolucao.nf_interna.ilike(f'%{busca}%'))
        )

    if status_filtro:
        query = query.filter(Devolucao.status == status_filtro)

    # Ordena: pendentes primeiro, depois por data mais recente
    from sqlalchemy import case
    ordem_status = case(
        (Devolucao.status == 'aguardando_conferencia', 1),
        (Devolucao.status == 'aguardando_aprovacao', 2),
        (Devolucao.status == 'em_transito', 3),
        (Devolucao.status == 'aguardando_fiscal', 4),
        (Devolucao.status == 'entregue_fiscal', 5),
        (Devolucao.status == 'finalizado_pago', 6),
        else_=6
    )
    devolucoes = query.order_by(ordem_status, Devolucao.data_criacao.desc()).all()

    return render_template('dashboard.html', devolucoes=devolucoes, busca=busca, status_filtro=status_filtro)

# --- FLUXO DE DEVOLUÇÃO ---
@app.route('/nova', methods=['GET', 'POST'])
@login_required
@roles_required('vendedor', 'conferente', 'gerente')
def nova_devolucao():
    if request.method == 'POST':
        nova = Devolucao(
            cliente=request.form['cliente'], 
            nf_cliente=request.form['nf_cliente'],
            nf_interna=request.form['nf_interna'], 
            valor=float(request.form['valor']),
            motivo=request.form['motivo'], 
            vendedor_id=session['user_id']
        )
        db.session.add(nova)
        db.session.flush()
        
        arquivos = request.files.getlist('pdf_notas')
        
        for arquivo in arquivos:
            if arquivo and arquivo.filename != '':
                fname = secure_filename(arquivo.filename)
                nome_unico = f"{nova.id}_{fname}"
                arquivo.save(os.path.join(app.config['UPLOAD_FOLDER'], nome_unico))
                
                pdf = DevolucaoPDF(
                    devolucao_id=nova.id,
                    nome_arquivo=nome_unico
                )
                db.session.add(pdf)
        
        db.session.commit()
        return redirect(url_for('dashboard'))
    
    return render_template('nova_devolucao.html')

@app.route('/conferir_nota/<int:id>')
@roles_required('conferente', 'gerente')
def conferir_nota(id):
    d = Devolucao.query.get_or_404(id)
    d.status, d.conferido_por, d.data_conferencia = "aguardando_aprovacao", session['nome'], agora_brasilia()
    db.session.commit(); return redirect(url_for('dashboard'))

@app.route('/aprovar_envio/<int:id>')
@roles_required('gerente')
def aprovar_envio(id):
    d = Devolucao.query.get_or_404(id)
    d.status, d.aprovado_por, d.data_aprovacao = "em_transito", session['nome'], agora_brasilia()
    db.session.commit(); return redirect(url_for('dashboard'))

@app.route('/receber_mercadoria/<int:id>')
@roles_required('vendedor', 'conferente', 'gerente')
def receber_mercadoria(id):
    d = Devolucao.query.get_or_404(id)
    d.status = "aguardando_fiscal"
    d.recebido_por = session['nome']
    d.data_recebimento = agora_brasilia()
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/baixar_boleto/<int:id>')
@roles_required('financeiro')
def baixar_boleto(id):
    d = Devolucao.query.get_or_404(id)
    d.status, d.baixado_por, d.data_baixa = "finalizado_pago", session['nome'], agora_brasilia()
    db.session.commit(); return redirect(url_for('dashboard'))


@app.route('/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@roles_required('vendedor', 'conferente', 'gerente')
def editar_devolucao(id):
    d = Devolucao.query.get_or_404(id)

    # Só quem criou pode editar, e só se ainda estiver aguardando validação
    if d.vendedor_id != session['user_id'] and session['perfil'] not in ['gerente']:
        flash("Você não tem permissão para editar esta devolução.")
        return redirect(url_for('dashboard'))

    if d.status != 'aguardando_conferencia':
        flash("Esta devolução não pode mais ser editada pois já passou da etapa de validação.")
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        d.cliente = request.form['cliente']
        d.nf_cliente = request.form['nf_cliente']
        d.nf_interna = request.form['nf_interna']
        d.valor = float(request.form['valor'])
        d.motivo = request.form['motivo']

        # Remover PDFs marcados
        ids_remover = request.form.getlist('remover_pdf')
        for pdf_id in ids_remover:
            pdf = DevolucaoPDF.query.get(int(pdf_id))
            if pdf and pdf.devolucao_id == d.id:
                try:
                    os.remove(os.path.join(app.config['UPLOAD_FOLDER'], pdf.nome_arquivo))
                except:
                    pass
                db.session.delete(pdf)

        # Adicionar novos PDFs
        arquivos = request.files.getlist('pdf_notas')
        for arquivo in arquivos:
            if arquivo and arquivo.filename != '':
                fname = secure_filename(arquivo.filename)
                nome_unico = f"{d.id}_{fname}"
                arquivo.save(os.path.join(app.config['UPLOAD_FOLDER'], nome_unico))
                pdf = DevolucaoPDF(devolucao_id=d.id, nome_arquivo=nome_unico)
                db.session.add(pdf)

        db.session.commit()
        flash("Devolução atualizada com sucesso!")
        return redirect(url_for('dashboard'))

    return render_template('editar_devolucao.html', d=d)


@app.route('/dar_entrada_fiscal/<int:id>')
@login_required
@roles_required('fiscal', 'gerente')
def dar_entrada_fiscal(id):
    d = Devolucao.query.get_or_404(id)
    d.status = "entregue_fiscal"
    d.entrada_fiscal_por = session['nome']
    d.data_entrada_fiscal = agora_brasilia()
    db.session.commit()
    return redirect(url_for('dashboard'))

# --- USUÁRIOS ---
@app.route('/usuarios')
@roles_required('gerente')
def listar_usuarios():
    return render_template('usuario.html', usuarios=Usuario.query.all())

@app.route('/usuarios/novo', methods=['GET', 'POST'])
@roles_required('gerente')
def novo_usuario():
    if request.method == 'POST':
        u = Usuario(nome=request.form['nome'], email=request.form['email'], perfil=request.form['perfil'])
        u.set_senha(request.form['senha'])
        db.session.add(u); db.session.commit()
        return redirect(url_for('listar_usuarios'))
    return render_template('novo_usuario.html')

@app.route('/usuarios/editar/<int:id>', methods=['GET', 'POST'])
@roles_required('gerente')
def editar_usuario(id):
    u = Usuario.query.get_or_404(id)
    if request.method == 'POST':
        u.nome, u.email, u.perfil = request.form['nome'], request.form['email'], request.form['perfil']
        if request.form.get('senha'): u.set_senha(request.form['senha'])
        db.session.commit(); return redirect(url_for('listar_usuarios'))
    return render_template('editar_usuario.html', u=u)

# --- RELATÓRIO EM PDF (SOMENTE GERENTE) ---
@app.route('/relatorio', methods=['GET', 'POST'])
@login_required
@roles_required('gerente')
def relatorio():
    if request.method == 'POST':
        data_inicio = request.form.get('data_inicio')
        data_fim = request.form.get('data_fim')
        
        if data_inicio and data_fim:
            return redirect(url_for('gerar_relatorio_pdf', 
                                  data_inicio=data_inicio, 
                                  data_fim=data_fim))
    
    return render_template('relatorio.html')

@app.route('/relatorio/pdf')
@login_required
@roles_required('gerente')
def gerar_relatorio_pdf():
    data_inicio_str = request.args.get('data_inicio')
    data_fim_str = request.args.get('data_fim')
    
    if not data_inicio_str or not data_fim_str:
        flash("Selecione as datas inicial e final.")
        return redirect(url_for('relatorio'))
    
    data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d')
    data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d')
    data_fim = data_fim.replace(hour=23, minute=59, second=59)
    
    devolucoes = Devolucao.query.filter(
        Devolucao.data_criacao >= data_inicio,
        Devolucao.data_criacao <= data_fim
    ).order_by(Devolucao.data_criacao.desc()).all()
    
    total_valor = sum(d.valor for d in devolucoes if d.valor)
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4),
                           rightMargin=2*cm, leftMargin=2*cm,
                           topMargin=2*cm, bottomMargin=2*cm)
    
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=20,
        alignment=1
    )

    # Estilo para células com quebra de linha automática
    cell_style = ParagraphStyle(
        'CellStyle',
        parent=styles['Normal'],
        fontSize=8,
        leading=11,
        wordWrap='CJK',
    )

    cell_style_center = ParagraphStyle(
        'CellStyleCenter',
        parent=cell_style,
        alignment=1,
    )
    
    elements = []
    
    elements.append(Paragraph("MIC - Relatório de Devoluções", title_style))
    elements.append(Paragraph(f"<b>Período:</b> {data_inicio_str} até {data_fim_str}", styles['Normal']))
    elements.append(Paragraph(f"<b>Total de registros:</b> {len(devolucoes)}", styles['Normal']))
    elements.append(Spacer(1, 20))
    
    # Cabeçalho
    data = [[
        Paragraph('<b>Data Entrada</b>', cell_style_center),
        Paragraph('<b>Cliente</b>', cell_style_center),
        Paragraph('<b>Vendedor</b>', cell_style_center),
        Paragraph('<b>NF Cliente</b>', cell_style_center),
        Paragraph('<b>NF Interna</b>', cell_style_center),
        Paragraph('<b>Status</b>', cell_style_center),
        Paragraph('<b>Valor</b>', cell_style_center),
    ]]
    
    for d in devolucoes:
        vendedor_nome = d.vendedor.nome if d.vendedor else '-'
        # Quebra as NFs em linhas separadas quando há múltiplos valores
        nf_cliente = (d.nf_cliente or '-').replace(' / ', '\n')
        nf_interna = (d.nf_interna or '-').replace(' / ', '\n')
        data.append([
            Paragraph(d.data_criacao.strftime('%d/%m/%Y'), cell_style_center),
            Paragraph(d.cliente or '-', cell_style),
            Paragraph(vendedor_nome, cell_style_center),
            Paragraph(nf_cliente, cell_style_center),
            Paragraph(nf_interna, cell_style_center),
            Paragraph(d.status.replace('_', ' ').title(), cell_style_center),
            Paragraph(f"R$ {d.valor:.2f}" if d.valor else "R$ 0.00", cell_style_center),
        ])
    
    table = Table(data, colWidths=[2.8*cm, 5*cm, 3*cm, 3.5*cm, 3.5*cm, 3.5*cm, 2.5*cm])
    
    table_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f4f7f6')])
    ])
    table.setStyle(table_style)
    
    elements.append(table)
    elements.append(Spacer(1, 20))
    
    total_style = ParagraphStyle(
        'Total',
        parent=styles['Normal'],
        fontSize=12,
        textColor=colors.HexColor('#27ae60'),
        alignment=2
    )
    elements.append(Paragraph(f"<b>Valor Total no Período: R$ {total_valor:.2f}</b>", total_style))
    
    elements.append(Spacer(1, 30))
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.grey,
        alignment=1
    )
    agora = agora_brasilia().strftime('%d/%m/%Y às %H:%M')
    elements.append(Paragraph(f"Relatório gerado em {agora} | Sistema MIC", footer_style))
    
    doc.build(elements)
    buffer.seek(0)
    
    nome_arquivo = f"relatorio_devolucoes_{data_inicio_str}_a_{data_fim_str}.pdf"
    
    return send_file(buffer, 
                     download_name=nome_arquivo,
                     as_attachment=True,
                     mimetype='application/pdf')

# --- Bloco de Auto-Setup ---
def inicializar_usuarios():
    usuarios_fixos = [
        {"nome": "André", "email": "andre.oliveira@mic.ind.br", "perfil": "gerente"},
        {"nome": "Eloah", "email": "eloah@mic.ind.br", "perfil": "gerente"},
        {"nome": "Andrea Financeiro", "email": "andrea.santos@mic.ind.br", "perfil": "financeiro"},
        {"nome": "Marinete", "email": "marinete.goncalves@mic.ind.br", "perfil": "conferente"},
        {"nome": "Renata", "email": "renata.caetano@mic.ind.br", "perfil": "vendedor"},
        {"nome": "Luan", "email": "luan.costa@mic.ind.br", "perfil": "vendedor"},
        {"nome": "Talita", "email": "talita.stevanelli@mic.ind.br", "perfil": "vendedor"},
        {"nome": "Kevilly", "email": "kevvilly.dantas@mic.ind.br", "perfil": "vendedor"},
        {"nome": "Viviane", "email": "viviane.santos@mic.ind.br", "perfil": "vendedor"},
        {"nome": "Francielle", "email": "francielle.oliveira@mic.ind.br", "perfil": "vendedor"},
        {"nome": "Thais", "email": "thais.kovacic@mic.ind.br", "perfil": "gerente"},
    ]

    with app.app_context():
        db.create_all()
        
        for dado in usuarios_fixos:
            if not Usuario.query.filter_by(email=dado["email"]).first():
                novo_u = Usuario(nome=dado["nome"], email=dado["email"], perfil=dado["perfil"])
                novo_u.set_senha("Mic@2026")
                db.session.add(novo_u)
        
        db.session.commit()
        print(">>> Sistema MIC: Usuários verificados/criados com sucesso!")

# --- Inicialização do Servidor ---
if __name__ == "__main__":
    inicializar_usuarios()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)