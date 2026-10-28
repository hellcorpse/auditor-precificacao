from fastapi import FastAPI, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import sqlite3
import hashlib

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Configuração da Base de Dados SQLite
DB_NAME = "database.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            verified INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def hash_password(password: str):
    return hashlib.sha256(password.encode()).hexdigest()

# Rota Principal / Dashboard de Precificação
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "resultado": None, "erro": None})

@app.post("/", response_class=HTMLResponse)
async def calcular(
    request: Request,
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
            raise ValueError("A soma da taxa da maquininha e da margem desejada não pode ser igual ou superior a 100%.")

        preco_venda_ideal = custo_total / divisor
        valor_taxa = preco_venda_ideal * taxa_decimal
        lucro_liquido = preco_venda_ideal - (custo_total + valor_taxa)

        resultado = {
            "custo_total": f"R$ {custo_total:.2f}",
            "preco_venda_ideal": f"R$ {preco_venda_ideal:.2f}",
            "lucro_liquido": f"R$ {lucro_liquido:.2f}"
        }

        return templates.TemplateResponse("index.html", {"request": request, "resultado": resultado, "erro": None})
    
    except ValueError as e:
        return templates.TemplateResponse("index.html", {"request": request, "resultado": None, "erro": str(e)})

# Rotas de Autenticação (Registo e Login)
@app.post("/auth/register")
async def register(email: str = Form(...), password: str = Form(...)):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        hashed_pw = hash_password(password)
        cursor.execute("INSERT INTO users (email, password, verified) VALUES (?, ?, 1)", (email, hashed_pw))
        conn.commit()
    except sqlite3.IntegrityError:
        return RedirectResponse(url="/?erro=email_existente", status_code=status.HTTP_303_SEE_OTHER)
    finally:
        conn.close()
    return RedirectResponse(url="/?sucesso=registado", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/auth/login")
async def login(email: str = Form(...), password: str = Form(...)):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    hashed_pw = hash_password(password)
    cursor.execute("SELECT * FROM users WHERE email = ? AND password = ?", (email, hashed_pw))
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        return RedirectResponse(url="/?erro=credenciais_invalidas", status_code=status.HTTP_303_SEE_OTHER)
    
    return RedirectResponse(url="/?sucesso=login", status_code=status.HTTP_303_SEE_OTHER)
    
