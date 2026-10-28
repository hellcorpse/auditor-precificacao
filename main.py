from fastapi import FastAPI, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import sqlite3
import hashlib

app = FastAPI()
templates = Jinja2Templates(directory="templates")

DB_NAME = "database.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Tabela de Utilizadores (com campo is_pro para a versão paga)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            is_pro INTEGER DEFAULT 0,
            verified INTEGER DEFAULT 1
        )
    ''')
    
    # Tabela de Histórico de Cálculos (Versão Paga)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            produto TEXT,
            custo_total REAL,
            preco_venda REAL,
            lucro_liquido REAL,
            data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Inserir o Login Mestre Automático (já como PRO para testes)
    master_email = "admin@teste.com"
    master_pass = hashlib.sha256("@Leagueoflegens0".encode()).hexdigest()
    cursor.execute("INSERT OR IGNORE INTO users (email, password, is_pro, verified) VALUES (?, ?, 1, 1)", (master_email, master_pass))
    
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
        "is_pro": False,
        "historico": [],
        "resultado": None, 
        "erro": erro, 
        "sucesso": sucesso
    })

@app.post("/auth/login", response_class=HTMLResponse)
async def login(request: Request, email: str = Form(...), password: str = Form(...)):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    hashed_pw = hash_password(password)
    cursor.execute("SELECT email, is_pro FROM users WHERE email = ? AND password = ?", (email, hashed_pw))
    user = cursor.fetchone()
    
    if not user:
        conn.close()
        return templates.TemplateResponse("index.html", {
            "request": request, 
            "logado": False, 
            "resultado": None, 
            "erro": "E-mail ou palavra-passe incorretos.", 
            "sucesso": None
        })
    
    email_utilizador = user[0]
    is_pro = bool(user[1])
    
    # Buscar histórico do utilizador se for PRO
    historico = []
    if is_pro:
        cursor.execute("SELECT produto, custo_total, preco_venda, lucro_liquido, data_criacao FROM historico WHERE email = ? ORDER BY id DESC LIMIT 10", (email_utilizador,))
        historico = cursor.fetchall()
        
    conn.close()
    
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "logado": True, 
        "email_utilizador": email_utilizador,
        "is_pro": is_pro,
        "historico": historico,
        "resultado": None, 
        "erro": None
    })

@app.post("/auth/register", response_class=HTMLResponse)
async def register(request: Request, email: str = Form(...), password: str = Form(...)):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        hashed_pw = hash_password(password)
        cursor.execute("INSERT INTO users (email, password, is_pro) VALUES (?, ?, 0)", (email, hashed_pw))
        conn.commit()
    except sqlite3.IntegrityError:
        return templates.TemplateResponse("index.html", {
            "request": request, 
            "logado": False, 
            "resultado": None, 
            "erro": "Este e-mail já está registado.", 
            "sucesso": None
        })
    finally:
        conn.close()
    
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "logado": False, 
        "resultado": None, 
        "erro": None, 
        "sucesso": "Conta criada com sucesso! Faça login abaixo."
    })

@app.post("/calcular", response_class=HTMLResponse)
async def calcular(
    request: Request,
    email: str = Form(...),
    produto: str = Form("Produto Geral"),
    custo_produto: float = Form(...),
    frete: float = Form(...),
    taxa_maquininha: float = Form(...),
    margem_desejada: float = Form(...)
):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT is_pro FROM users WHERE email = ?", (email,))
    user_row = cursor.fetchone()
    is_pro = bool(user_row[0]) if user_row else False
    
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

        # Se for PRO, guarda automaticamente no histórico
        if is_pro:
            cursor.execute(
                "INSERT INTO historico (email, produto, custo_total, preco_venda, lucro_liquido) VALUES (?, ?, ?, ?, ?)",
                (email, produto, custo_total, preco_venda_ideal, lucro_liquido)
            )
            conn.commit()

        # Atualizar histórico para exibir na tela
        historico = []
        if is_pro:
            cursor.execute("SELECT produto, custo_total, preco_venda, lucro_liquido, data_criacao FROM historico WHERE email = ? ORDER BY id DESC LIMIT 10", (email,))
            historico = cursor.fetchall()
            
        conn.close()

        resultado = {
            "custo_total": f"R$ {custo_total:.2f}",
            "preco_venda_ideal": f"R$ {preco_venda_ideal:.2f}",
            "lucro_liquido": f"R$ {lucro_liquido:.2f}"
        }

        return templates.TemplateResponse("index.html", {
            "request": request, 
            "logado": True, 
            "email_utilizador": email,
            "is_pro": is_pro,
            "historico": historico,
            "resultado": resultado, 
            "erro": None
        })
    
    except ValueError as e:
        conn.close()
        return templates.TemplateResponse("index.html", {
            "request": request, 
            "logado": True, 
            "email_utilizador": email,
            "is_pro": is_pro,
            "historico": [],
            "resultado": None, 
            "erro": str(e)
        })
        
