from fastapi import FastAPI, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import sqlite3
import hashlib
import random

app = FastAPI()
templates = Jinja2Templates(directory="templates")

DB_NAME = "database.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            verified INTEGER DEFAULT 1
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS verification_codes (
            email TEXT PRIMARY KEY,
            code TEXT NOT NULL
        )
    ''')
    
    # Inserir o Login Mestre Automático
    master_email = "admin@teste.com"
    master_pass = hashlib.sha256("@Leagueoflegens0".encode()).hexdigest()
    cursor.execute("INSERT OR IGNORE INTO users (email, password, verified) VALUES (?, ?, 1)", (master_email, master_pass))
    
    conn.commit()
    conn.close()

init_db()

def hash_password(password: str):
    return hashlib.sha256(password.encode()).hexdigest()

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, erro: str = None, sucesso: str = None):
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "logado": False, 
        "etapa_codigo": False,
        "email_pendente": None,
        "resultado": None, 
        "erro": erro, 
        "sucesso": sucesso
    })

# Iniciar Login por E-mail ou Senha
@app.post("/auth/login", response_class=HTMLResponse)
async def login(request: Request, email: str = Form(...), password: str = Form(...)):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    hashed_pw = hash_password(password)
    cursor.execute("SELECT * FROM users WHERE email = ? AND password = ?", (email, hashed_pw))
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        return templates.TemplateResponse("index.html", {
            "request": request, 
            "logado": False, 
            "etapa_codigo": False,
            "resultado": None, 
            "erro": "E-mail ou palavra-passe incorretos.", 
            "sucesso": None
        })
    
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "logado": True, 
        "email_utilizador": email,
        "resultado": None, 
        "erro": None
    })

# Iniciar o fluxo de Login Social (Google / Facebook) enviando código de verificação
@app.post("/auth/social-init", response_class=HTMLResponse)
async def social_init(request: Request, social_provider: str = Form(...), email: str = Form(...)):
    if not email or "@" not in email:
        return templates.TemplateResponse("index.html", {
            "request": request, 
            "logado": False, 
            "etapa_codigo": False,
            "resultado": None, 
            "erro": "Por favor, insira um e-mail válido para continuar com o " + social_provider, 
            "sucesso": None
        })
    
    # Gerar código aleatório de 6 dígitos
    codigo_verificacao = str(random.randint(100000, 999999))
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("REPLACE INTO verification_codes (email, code) VALUES (?, ?)", (email, codigo_verificacao))
    
    # Garantir que o utilizador existe na base de dados para aceitar o login social
    cursor.execute("INSERT OR IGNORE INTO users (email, password, verified) VALUES (?, ?, 1)", (email, hash_password("social_login_secure")))
    conn.commit()
    conn.close()
    
    # Mensagem informativa simulando o envio real do e-mail com o código (para testes práticos)
    mensagem_sucesso = f"Código de verificação enviado para {email} via {social_provider}! (Código de teste simulado: {codigo_verificacao})"

    return templates.TemplateResponse("index.html", {
        "request": request, 
        "logado": False, 
        "etapa_codigo": True,
        "email_pendente": email,
        "resultado": None, 
        "erro": None, 
        "sucesso": mensagem_sucesso
    })

# Verificar o código enviado por e-mail para concluir o login social
@app.post("/auth/social-verify", response_class=HTMLResponse)
async def social_verify(request: Request, email: str = Form(...), codigo: str = Form(...)):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT code FROM verification_codes WHERE email = ?", (email,))
    row = cursor.fetchone()
    conn.close()
    
    if not row or row[0] != codigo:
        return templates.TemplateResponse("index.html", {
            "request": request, 
            "logado": False, 
            "etapa_codigo": True,
            "email_pendente": email,
            "resultado": None, 
            "erro": "Código de verificação inválido. Tente novamente.", 
            "sucesso": None
        })
    
    # Código correto: Autenticação bem-sucedida via Social
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "logado": True, 
        "email_utilizador": email,
        "resultado": None, 
        "erro": None
    })

@app.post("/auth/register", response_class=HTMLResponse)
async def register(request: Request, email: str = Form(...), password: str = Form(...)):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        hashed_pw = hash_password(password)
        cursor.execute("INSERT INTO users (email, password) VALUES (?, ?)", (email, hashed_pw))
        conn.commit()
    except sqlite3.IntegrityError:
        return templates.TemplateResponse("index.html", {
            "request": request, 
            "logado": False, 
            "etapa_codigo": False,
            "resultado": None, 
            "erro": "Este e-mail já está registado.", 
            "sucesso": None
        })
    finally:
        conn.close()
    
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "logado": False, 
        "etapa_codigo": False,
        "resultado": None, 
        "erro": None, 
        "sucesso": "Conta criada com sucesso! Faça login abaixo."
    })

@app.post("/calcular", response_class=HTMLResponse)
async def calcular(
    request: Request,
    email: str = Form(...),
    custo_produto: float = Form(...),
    frete: float = Form(...),
    taxa_maquininha: float = Form(...),
    margem_desejada: float = Form(...)
):
    try:
        if custo_produto <= 0 or frete < 0 or taxa_maquininha < 0 or margem_desejada < 0:
            raise ValueError("Os valores devem ser positivos.")

        custo_total = custo_produto + frete
        taxa_decimal = taxa_maquininha / 100.0
        margem_decimal = margem_desejada / 100.0

        divisor = 1 - (taxa_decimal + margem_decimal)
        if divisor <= 0:
            raise ValueError("A soma da taxa da maquininha e da margem desejada não pode atingir ou superar 100%.")

        preco_venda_ideal = custo_total / divisor
        valor_taxa = preco_venda_ideal * taxa_decimal
        lucro_liquido = preco_venda_ideal - (custo_total + valor_taxa)

        resultado = {
            "custo_total": f"R$ {custo_total:.2f}",
            "preco_venda_ideal": f"R$ {preco_venda_ideal:.2f}",
            "lucro_liquido": f"R$ {lucro_liquido:.2f}"
        }

        return templates.TemplateResponse("index.html", {
            "request": request, 
            "logado": True, 
            "email_utilizador": email,
            "resultado": resultado, 
            "erro": None
        })
    
    except ValueError as e:
        return templates.TemplateResponse("index.html", {
            "request": request, 
            "logado": True, 
            "email_utilizador": email,
            "resultado": None, 
            "erro": str(e)
        })
        
