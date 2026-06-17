from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    senha_hash = db.Column(db.String(200), nullable=False)
    perfil = db.Column(db.String(50), nullable=False) 

    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def check_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)

class Devolucao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cliente = db.Column(db.String(200))
    nf_cliente = db.Column(db.String(100))
    nf_interna = db.Column(db.String(100))
    valor = db.Column(db.Float)
    motivo = db.Column(db.Text)
    status = db.Column(db.String(50), default="aguardando_conferencia")
    pdf_nota = db.Column(db.String(200))
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    vendedor_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    vendedor = db.relationship('Usuario', foreign_keys=[vendedor_id])

    # Auditoria de Processo
    conferido_por = db.Column(db.String(100))
    data_conferencia = db.Column(db.DateTime)
    aprovado_por = db.Column(db.String(100))
    data_aprovacao = db.Column(db.DateTime)
    recebido_por = db.Column(db.String(100))
    data_recebimento = db.Column(db.DateTime)
    baixado_por = db.Column(db.String(100))
    data_baixa = db.Column(db.DateTime)
    entrada_fiscal_por = db.Column(db.String(100))
    data_entrada_fiscal = db.Column(db.DateTime)
    obs_baixa = db.Column(db.Text)

class DevolucaoPDF(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    devolucao_id = db.Column(db.Integer, db.ForeignKey('devolucao.id'), nullable=False)
    nome_arquivo = db.Column(db.String(200), nullable=False)
    data_upload = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamento
    devolucao = db.relationship('Devolucao', backref='pdfs')