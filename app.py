import os
from flask import Flask, render_template, redirect, url_for, request, session, flash
from config import Config
from models import db, Usuario, Devolucao
from datetime import datetime
from functools import wraps
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config.from_object(Config)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db.init_app(app)

with app.app_context():
    db.create_all()

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
    busca = request.args.get('q', '') # Pega o termo de pesquisa da URL
    
    # Base da consulta (Query)
    query = Devolucao.query

    # Regra 1: Se for vendedor, filtra logo de cara apenas as dele
    if session['perfil'] == 'vendedor':
        query = query.filter(Devolucao.vendedor_id == session['user_id'])

    # Regra 2: Se houver termo de busca, aplica os filtros de texto
    if busca:
        query = query.filter(
            (Devolucao.cliente.ilike(f'%{busca}%')) | 
            (Devolucao.nf_cliente.ilike(f'%{busca}%')) | 
            (Devolucao.nf_interna.ilike(f'%{busca}%'))
        )

    # Ordena pelas mais recentes
    devolucoes = query.order_by(Devolucao.data_criacao.desc()).all()
    
    return render_template('dashboard.html', devolucoes=devolucoes, busca=busca)

# --- FLUXO DE DEVOLUÇÃO ---
@app.route('/nova', methods=['GET', 'POST'])
@login_required
@roles_required('vendedor', 'conferente', 'gerente')
def nova_devolucao():
    if request.method == 'POST':
        f = request.files.get('pdf_nota')
        fname = secure_filename(f.filename) if f and f.filename != '' else None
        if fname: f.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
        
        nova = Devolucao(
            cliente=request.form['cliente'], nf_cliente=request.form['nf_cliente'],
            nf_interna=request.form['nf_interna'], valor=float(request.form['valor']),
            motivo=request.form['motivo'], pdf_nota=fname, vendedor_id=session['user_id']
        )
        db.session.add(nova); db.session.commit()
        return redirect(url_for('dashboard'))
    return render_template('nova_devolucao.html')

@app.route('/conferir_nota/<int:id>')
@roles_required('conferente', 'gerente')
def conferir_nota(id):
    d = Devolucao.query.get_or_404(id)
    d.status, d.conferido_por, d.data_conferencia = "aguardando_aprovacao", session['nome'], datetime.now()
    db.session.commit(); return redirect(url_for('dashboard'))

@app.route('/aprovar_envio/<int:id>')
@roles_required('gerente')
def aprovar_envio(id):
    d = Devolucao.query.get_or_404(id)
    d.status, d.aprovado_por, d.data_aprovacao = "em_transito", session['nome'], datetime.now()
    db.session.commit(); return redirect(url_for('dashboard'))

@app.route('/receber_mercadoria/<int:id>')
@roles_required('vendedor', 'conferente', 'gerente')
def receber_mercadoria(id):
    d = Devolucao.query.get_or_404(id)
    d.status = "entregue_fiscal"
    d.recebido_por = session['nome'] # Esta linha grava o nome de quem clicou
    d.data_recebimento = datetime.now() # Esta grava o horário
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/baixar_boleto/<int:id>')
@roles_required('financeiro')
def baixar_boleto(id):
    d = Devolucao.query.get_or_404(id)
    d.status, d.baixado_por, d.data_baixa = "finalizado_pago", session['nome'], datetime.now()
    db.session.commit(); return redirect(url_for('dashboard'))

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

# --- Bloco de Auto-Setup para o Render ---
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
        {"nome": "Francielle", "email": "francielle.oliveira@mic.ind.br", "perfil": "vendedor"}
    ]

    with app.app_context():
        db.create_all()  # Cria o banco e as colunas novas se não existirem
        
        for dado in usuarios_fixos:
            # Só cria se o e-mail não existir no banco
            if not Usuario.query.filter_by(email=dado["email"]).first():
                novo_u = Usuario(nome=dado["nome"], email=dado["email"], perfil=dado["perfil"])
                novo_u.set_senha("Mic@2026")
                db.session.add(novo_u)
        
        db.session.commit()
        print(">>> Sistema MIC: Usuários verificados/criados com sucesso!")

# --- Inicialização do Servidor ---
if __name__ == "__main__":
    inicializar_usuarios() # Roda a criação de usuários ANTES do site subir
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)