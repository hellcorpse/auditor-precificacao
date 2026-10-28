import os
from fastapi import FastAPI, Request, Form, Response, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from supabase import create_client, Client

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Configuração Oficial e Direta do Supabase (Sem depender de variáveis de ambiente)
SUPABASE_URL = "https://jfqbkdbirwkchejlaohg.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImpmcWJrZGJpcndrY2hlaWpsb2hnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTMxNzc3MzAsImV4cCI6MjEwODc1MzczMH0.emxXE8DIItb0GG3U6ZPdbUqxkxjQ3Ad1QAiBE9Vv7Hw"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Garantir utilizador Administrador padrão na inicialização
def init_db():
    try:
        res = supabase.table("utilizadores").select("*").eq("email", "admin@teste.com").execute()
        if not res.data:
            supabase.table("utilizadores").insert({
                "email": "admin@teste.com",
                "password": "123456"
            }).execute()
    except Exception as e:
        print(f"Aviso na inicialização: {e}")

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

        try:
            res = supabase.table("historico").select("*").eq("email", email_utilizador).order("id", desc=True).execute()
            historico = [[row["produto"], row["custo_total"], row["preco_venda"], row["lucro_liquido"], row.get("data_criacao", "")] for row in res.data]
        except Exception:
            historico = []

    return templates.TemplateResponse(request, "index.html", {
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
    try:
        existente = supabase.table("utilizadores").select("*").eq("email", email).execute()
        if existente.data:
            return templates.TemplateResponse(request, "index.html", {
                "logado": False,
                "is_pro": False,
                "erro": "Este e-mail já está registado.",
                "sucesso": ""
            })
        
        supabase.table("utilizadores").insert({"email": email, "password": password}).execute()
        return templates.TemplateResponse(request, "index.html", {
            "logado": False,
            "is_pro": False,
            "sucesso": "Conta criada com sucesso! Faça login abaixo.",
            "erro": ""
        })
    except Exception:
        return templates.TemplateResponse(request, "index.html", {
            "logado": False,
            "is_pro": False,
            "erro": "Erro ao criar conta. Tente novamente.",
            "sucesso": ""
        })

@app.post("/auth/login", response_class=HTMLResponse)
def login(request: Request, email: str = Form(...), password: str = Form(...)):
    try:
        res = supabase.table("utilizadores").select("*").eq("email", email).eq("password", password).execute()
        if res.data:
            response = RedirectResponse(url="/", status_code=303)
            response.set_cookie(key="user_session", value=email)
            return response
    except Exception:
        pass

    return templates.TemplateResponse(request, "index.html", {
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
        try:
            supabase.table("historico").insert({
                "email": email,
                "produto": produto,
                "custo_total": custo_total,
                "preco_venda": preco_venda_ideal,
                "lucro_liquido": lucro_liquido
            }).execute()
        except Exception:
            pass

    historico = []
    try:
        res = supabase.table("historico").select("*").eq("email", email).order("id", desc=True).execute()
        historico = [[row["produto"], row["custo_total"], row["preco_venda"], row["lucro_liquido"], row.get("data_criacao", "")] for row in res.data]
    except Exception:
        pass

    resultado_dict = {
        "custo_total": f"R$ {custo_total:.2f}",
        "preco_venda_ideal": f"R$ {preco_venda_ideal:.2f}",
        "lucro_liquido": f"R$ {lucro_liquido:.2f}"
    }

    return templates.TemplateResponse(request, "index.html", {
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
    
