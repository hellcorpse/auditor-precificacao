import os
import psycopg2
from fastapi import FastAPI, Request, Form, Response, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# URL de Conexão Oficial do Supabase (PostgreSQL)
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://postgres:Q3p4hXkwbN9fTIB6@db.jfqb-kdbirwkchejlaohg.supabase.co:5432/postgres"
)

def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

# Inicializar Tabelas na Nuvem (Supabase)
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Tabela de Utilizadores
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS utilizadores (
            id SERIAL PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)
    
    # Tabela de Histórico de Cálculos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historico (
            id SERIAL PRIMARY KEY,
            email TEXT NOT NULL,
            produto TEXT NOT NULL,
            custo_total REAL NOT NULL,
            preco_venda REAL NOT NULL,
            lucro_liquido REAL NOT NULL,
            data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    
    # Criar utilizador Administrador/PRO padrão se não existir
    cursor.execute("SELECT * FROM utilizadores WHERE email = %s", ("admin@teste.com",))
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO utilizadores (email, password) VALUES (%s, %s)",
            ("admin@teste.com", "123456")
        )
        conn.commit()
        
    cursor.close()
    conn.close()

init_db()

@app.get("/", response_class=HTMLResponse)
def index(request: Request, user_session: str = Cookie(None)):
    logado = False
    is_pro = False
    email_utilizador = ""
    historico = []

    if user_session:
        logado = True
        email_utilizador = user_session
        if email_utilizador == "admin@teste.com":
            is_pro = True

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT produto, custo_total, preco_venda, lucro_liquido, TO_CHAR(data_criacao, 'YYYY-MM-DD HH24:MI:SS') FROM historico WHERE email = %s ORDER BY id DESC",
            (email_utilizador,)
        )
        historico = cursor.fetchall()
        cursor.close()
        conn.close()

    return templates.TemplateResponse("index.html", {
        "request": request,
        "logado": logado,
        "is_pro": is_pro,
        "email_utilizador": email_utilizador,
        "historico": historico,
        "resultado": None,
        "erro": "",
        "sucesso": ""
    })

@app.post("/auth/register", response_class=HTMLResponse)
def register(request: Request, email: str = Form(...), password: str = Form(...)):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO utilizadores (email, password) VALUES (%s, %s)",
            (email, password)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return templates.TemplateResponse("index.html", {
            "request": request,
            "logado": False,
            "is_pro": False,
            "sucesso": "Conta criada com sucesso! Faça login abaixo.",
            "erro": ""
        })
    except Exception:
        conn.rollback()
        cursor.close()
        conn.close()
        return templates.TemplateResponse("index.html", {
            "request": request,
            "logado": False,
            "is_pro": False,
            "erro": "Este e-mail já está registado.",
            "sucesso": ""
        })

@app.post("/auth/login", response_class=HTMLResponse)
def login(request: Request, email: str = Form(...), password: str = Form(...)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM utilizadores WHERE email = %s AND password = %s",
        (email, password)
    )
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if user:
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(key="user_session", value=email)
        return response
    else:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "logado": False,
            "is_pro": False,
            "erro": "E-mail ou palavra-passe incorretos.",
            "sucesso": ""
        })

@app.post("/calcular", response_class=HTMLResponse)
def calcular(
    request: Request,
    email: str = Form(...),
    produto: str = Form(...),
    custo_produto: float = Form(...),
    frete: float = Form(...),
    taxa_maquininha: float = Form(...),
    margem_desejada: float = Form(...)
):
    custo_total = custo_produto + frete
    fator_taxas = 1 - ((taxa_maquininha + margem_desejada) / 100)
    
    if fator_taxas <= 0:
        preco_venda_ideal = custo_total * 2
    else:
        preco_venda_ideal = custo_total / fator_taxas

    comissao_cartao_val = preco_venda_ideal * (taxa_maquininha / 100)
    lucro_liquido = preco_venda_ideal - custo_total - comissao_cartao_val

    is_pro = (email == "admin@teste.com")

    if is_pro:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO historico (email, produto, custo_total, preco_venda, lucro_liquido) VALUES (%s, %s, %s, %s, %s)",
            (email, produto, custo_total, preco_venda_ideal, lucro_liquido)
        )
        conn.commit()
        cursor.close()
        conn.close()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT produto, custo_total, preco_venda, lucro_liquido, TO_CHAR(data_criacao, 'YYYY-MM-DD HH24:MI:SS') FROM historico WHERE email = %s ORDER BY id DESC",
        (email,)
    )
    historico = cursor.fetchall()
    cursor.close()
    conn.close()

    resultado_dict = {
        "custo_total": f"R$ {custo_total:.2f}",
        "preco_venda_ideal": f"R$ {preco_venda_ideal:.2f}",
        "lucro_liquido": f"R$ {lucro_liquido:.2f}"
    }

    return templates.TemplateResponse("index.html", {
        "request": request,
        "logado": True,
        "is_pro": is_pro,
        "email_utilizador": email,
        "historico": historico,
        "resultado": resultado_dict,
        "erro": "",
        "sucesso": "Cálculo efetuado e salvo com sucesso!"
    })

@app.get("/logout")
def logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(key="user_session")
    return response
    
