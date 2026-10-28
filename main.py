from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

app = FastAPI()

# Configura a pasta onde ficam os arquivos visuais (HTML)
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    # Mostra a página inicial vazia
    return templates.TemplateResponse("index.html", {"request": request, "resultado": None})

@app.post("/", response_class=HTMLResponse)
async def calcular(
    request: Request,
    custo_produto: float = Form(...),
    frete: float = Form(...),
    taxa_maquininha: float = Form(...),
    margem_desejada: float = Form(...)
):
    # Lógica de cálculo
    custo_total_inicial = custo_produto + frete
    taxa_decimal = taxa_maquininha / 100
    margem_decimal = margem_desejada / 100
    
    divisor = 1 - (taxa_decimal + margem_decimal)
    
    if divisor <= 0:
        erro = "A soma das taxas e da margem de lucro não pode ser igual ou maior que 100%!"
        return templates.TemplateResponse("index.html", {"request": request, "erro": erro, "resultado": None})
    
    preco_venda_ideal = custo_total_inicial / divisor
    valor_taxa = preco_venda_ideal * taxa_decimal
    lucro_liquido = preco_venda_ideal - (custo_total_inicial + valor_taxa)
    
    resultado = {
        "preco_venda_ideal": f"R$ {preco_venda_ideal:.2f}",
        "lucro_liquido": f"R$ {lucro_liquido:.2f}",
        "custo_total": f"R$ {custo_total_inicial:.2f}"
    }
    
    return templates.TemplateResponse("index.html", {"request": request, "resultado": resultado, "erro": None})
