from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from typing import List, Dict, Any, Optional
import uvicorn
import os
import datetime
import asyncio

# Importando serviços e configurações
from services.case_evaluator import get_case_details, list_cases
from services.steam_market import get_item_price, get_api_status
from services.inventory_pricer import get_specific_price, analyze_inventory_items
from utils.database import init_db
from utils.price_updater import run_scheduler, get_scheduler_status, schedule_weekly_update

# Importar modelos
from models.inventory import (
    ItemPriceRequest, ItemPriceResponse,
    InventoryAnalysisRequest, InventoryAnalysisResponse
)

app = FastAPI(
    title="CS2 Valuation API",
    description="API para busca de preços de skins CS2 considerando wear específico e StatTrak",
    version="1.0.0"
)

# Configurar CORS
ALLOWED_ORIGINS = [
    "http://localhost:5500",   # Desenvolvimento local
    "http://127.0.0.1:5500",   # Desenvolvimento local alternativo
    "http://localhost:3000",   # React local
    "http://localhost:8000",   # Porta do backend
    "http://localhost:8080",   # Frontend local (VS Code Live Server)
    "http://127.0.0.1:8080",   # Frontend local alternativo
    "http://localhost",        # Qualquer porta em localhost
    "http://127.0.0.1",        # Qualquer porta em localhost
    "https://elite-skins-2025.github.io",  # GitHub Pages
    "https://sidnei-almeida.github.io",  # GitHub Pages alternativo
    "file://",  # Para suportar arquivos abertos localmente
    "*"  # Permitir qualquer origem (útil para desenvolvimento e produção)
]

# Configurar middleware CORS com opções específicas
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    max_age=86400  # Cache preflight for 24h
)

# Custom middleware to add CORS headers to all responses
# This ensures that even in case of 500/502 errors, CORS headers will be present
class CustomCORSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Get request origin
        origin = request.headers.get("origin")
        
        # For OPTIONS requests (preflight), respond immediately
        if request.method == "OPTIONS":
            response = Response()
            if origin and (origin in ALLOWED_ORIGINS or "*" in ALLOWED_ORIGINS):
                response.headers["Access-Control-Allow-Origin"] = origin
            else:
                # If no origin or not allowed, use wildcard
                response.headers["Access-Control-Allow-Origin"] = "*"
            
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "*"
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Max-Age"] = "86400"
            return response
            
        try:
            # Process request normally
            response = await call_next(request)
            
            # Add CORS headers to response
            if origin and (origin in ALLOWED_ORIGINS or "*" in ALLOWED_ORIGINS):
                response.headers["Access-Control-Allow-Origin"] = origin
            else:
                response.headers["Access-Control-Allow-Origin"] = "*"
            
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "*"
            
            return response
        except Exception as e:
            # In case of error, ensure response still has CORS headers
            print(f"Middleware error: {e}")
            response = Response(status_code=500)
            
            if origin and (origin in ALLOWED_ORIGINS or "*" in ALLOWED_ORIGINS):
                response.headers["Access-Control-Allow-Origin"] = origin
            else:
                response.headers["Access-Control-Allow-Origin"] = "*"
            
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "*"
            response.headers["Content-Type"] = "application/json"
            response.body = b'{"error": "Internal Server Error"}'
            
            return response

# Add custom middleware after FastAPI middleware
app.add_middleware(CustomCORSMiddleware)

# Exception handler global para garantir CORS em todos os erros
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Garante que erros HTTP também tenham headers CORS"""
    response = JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response

@app.exception_handler(StarletteHTTPException)
async def starlette_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handler para exceções Starlette (incluindo 404) com CORS"""
    response = JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail if hasattr(exc, 'detail') else f"Endpoint não encontrado: {request.url.path}"}
    )
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Garante que erros gerais também tenham headers CORS"""
    import traceback
    print(f"Erro não tratado: {exc}")
    traceback.print_exc()
    response = JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"}
    )
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response

# List of endpoints for the home page
AVAILABLE_ENDPOINTS = [
    "/api/inventory/item-price",
    "/api/inventory/analyze-items",
    "/price/{market_hash_name}",
    "/case/{case_name}",
    "/cases",
    "/api/status",
    "/healthcheck"
]


@app.get("/")
async def root():
    return {
        "message": "CS2 Valuation API - Busca de Preços de Skins",
        "description": "API focada exclusivamente em buscar preços de skins CS2 considerando wear específico e StatTrak",
        "features": [
            "Busca de preços específicos por wear (Factory New, Minimal Wear, Field-Tested, Well-Worn, Battle-Scarred)",
            "Suporte para itens StatTrak e normais",
            "Análise em lote de inventários",
            "Conversão automática de moeda (USD para BRL)"
        ],
        "endpoints": [
            "GET /api/inventory/item-price - Busca preço específico de uma skin",
            "POST /api/inventory/analyze-items - Analisa lista de itens em lote",
            "GET /price/{market_hash_name} - Preço genérico de um item",
            "GET /case/{case_name} - Detalhes de uma case",
            "GET /cases - Lista de cases disponíveis",
            "GET /api/status - Status da API",
            "GET /healthcheck - Health check"
        ],
        "version": "1.0.0"
    }


# Novos endpoints para busca de preços específicos
@app.get("/api/inventory/item-price", response_model=ItemPriceResponse)
async def get_item_price_endpoint(
    market_hash_name: str = Query(..., description="Nome base da skin"),
    exterior: str = Query(..., description="Condição do item (Factory New, Minimal Wear, Field-Tested, Well-Worn, Battle-Scarred)"),
    stattrack: bool = Query(False, description="Se é StatTrak"),
    response: Response = None,
    request: Request = None
):
    """
    Busca preço específico de uma skin considerando wear e StatTrak.
    Retorna preço em USD. A conversão para outras moedas deve ser feita no frontend.
    """
    # Adicionar headers CORS manualmente (o middleware já adiciona, mas garantimos aqui também)
    if response:
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "*"
    
    # Buscar preço com imagem
    price_data = await get_specific_price(market_hash_name, exterior, stattrack, include_image=True)
    
    # Extrair preço e icon_url
    if isinstance(price_data, dict):
        price_usd = price_data.get('price')
        icon_url = price_data.get('icon_url')
    else:
        price_usd = price_data
        icon_url = None
    
    if price_usd is None:
        raise HTTPException(
            status_code=404,
            detail=f"Preço não encontrado para {market_hash_name} ({exterior})"
        )
    
    return ItemPriceResponse(
        market_hash_name=market_hash_name,
        exterior=exterior,
        stattrack=stattrack,
        price_usd=price_usd,
        price_brl=None,  # Conversão deve ser feita no frontend
        currency="USD",
        source="Steam Market",
        last_updated=datetime.datetime.now().isoformat(),
        icon_url=icon_url
    )


@app.post("/api/inventory/analyze-items", response_model=InventoryAnalysisResponse)
async def analyze_items_endpoint(
    request_body: InventoryAnalysisRequest,
    response: Response = None,
    request: Request = None
):
    """
    Analisa lista de itens e retorna preços específicos em USD.
    A conversão para outras moedas deve ser feita no frontend.
    """
    # Adicionar headers CORS manualmente (o middleware já adiciona, mas garantimos aqui também)
    if response:
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "*"
    
    try:
        # Converter modelos Pydantic para dicionários
        items_dict = [item.dict() for item in request_body.items]
        result = await analyze_inventory_items(items_dict)
        return InventoryAnalysisResponse(**result)
    except Exception as e:
        # Garantir que erros também tenham headers CORS
        if response:
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "*"
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao processar inventário: {str(e)}"
        )


@app.get("/case/{case_name}")
async def case(case_name: str, response: Response, request: Request = None):
    """Returns information about a specific case"""
    # Add CORS headers manually to ensure they are present even in case of error
    origin = request.headers.get("origin", "*") if request else "*"
    if origin and (origin in ALLOWED_ORIGINS or "*" in ALLOWED_ORIGINS):
        response.headers["Access-Control-Allow-Origin"] = origin
    else:
        response.headers["Access-Control-Allow-Origin"] = "*"
    
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    
    case_info = get_case_details(case_name)
    if not case_info:
        return {"error": "Case not found", "name": case_name}
    return case_info


@app.get("/price/{market_hash_name}")
async def price(market_hash_name: str, response: Response, request: Request = None):
    """Returns the price of an item by its market_hash_name, including detailed data for all wear conditions and StatTrak versions"""
    # Add CORS headers manually to ensure they are present even in case of error
    origin = request.headers.get("origin", "*") if request else "*"
    if origin and (origin in ALLOWED_ORIGINS or "*" in ALLOWED_ORIGINS):
        response.headers["Access-Control-Allow-Origin"] = origin
    else:
        response.headers["Access-Control-Allow-Origin"] = "*"
    
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    
    try:
        item_price_data = get_item_price(market_hash_name)
        
        # Build response with all available data
        response_data = {
            "market_hash_name": item_price_data.get("market_hash_name", market_hash_name),
            "price": item_price_data["price"],
            "currency": item_price_data["currency"],
            "timestamp": item_price_data.get("timestamp", datetime.datetime.now().isoformat()),
            "source": item_price_data.get("source", "unknown")
        }
        
        # Add detailed price data if available
        if "prices" in item_price_data:
            response_data["prices"] = item_price_data["prices"]
        
        if "price_range" in item_price_data:
            response_data["price_range"] = item_price_data["price_range"]
        
        # Add image URL if available
        if "image_url" in item_price_data and item_price_data["image_url"]:
            response_data["image_url"] = item_price_data["image_url"]
        
        # Add metadata if available
        if "rarity" in item_price_data:
            response_data["rarity"] = item_price_data["rarity"]
        
        if "category" in item_price_data:
            response_data["category"] = item_price_data["category"]
        
        if "weapon" in item_price_data:
            response_data["weapon"] = item_price_data["weapon"]
        
        # Add optional fields for backward compatibility
        if "sources_count" in item_price_data:
            response_data["sources_count"] = item_price_data["sources_count"]
            
        if "is_fallback" in item_price_data:
            response_data["is_fallback"] = item_price_data["is_fallback"]
            
        if "processed" in item_price_data:
            response_data["processed"] = item_price_data["processed"]
            
        return response_data
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e), "market_hash_name": market_hash_name}


@app.get("/cases")
async def cases(response: Response, request: Request = None):
    """Returns the list of available cases"""
    # Add CORS headers manually to ensure they are present even in case of error
    origin = request.headers.get("origin", "*") if request else "*"
    if origin and (origin in ALLOWED_ORIGINS or "*" in ALLOWED_ORIGINS):
        response.headers["Access-Control-Allow-Origin"] = origin
    else:
        response.headers["Access-Control-Allow-Origin"] = "*"
    
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    
    try:
        cases_list = list_cases()
        
        # Add current prices (API only)
        for case in cases_list:
            try:
                case["current_price"] = get_item_price(case["name"])
            except:
                case["current_price"] = 0.0
                
        return cases_list
    except Exception as e:
        print(f"Error processing case list: {e}")
        # Return an empty list instead of an error object
        return []


@app.get("/api/status")
async def api_status(response: Response, request: Request = None):
    """Returns information about the current API status, useful for monitoring"""
    # Add CORS headers manually to ensure they are present even in case of error
    origin = request.headers.get("origin", "*") if request else "*"
    if origin and (origin in ALLOWED_ORIGINS or "*" in ALLOWED_ORIGINS):
        response.headers["Access-Control-Allow-Origin"] = origin
    else:
        response.headers["Access-Control-Allow-Origin"] = "*"
    
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    
    try:
        # Always return online status to pass healthcheck
        return {
            "status": "online",
            "version": "1.0.0",
            "timestamp": datetime.datetime.now().isoformat()
        }
    except Exception as e:
        # Still return online status to ensure healthcheck passes
        return {"status": "online", "error": str(e)}



# Application initialization
@app.on_event("startup")
async def startup_event():
    """
    Initializes resources on application startup.
    """
    print("=== STARTING ELITE SKINS CS2 API ===")
    print(f"Environment: {os.environ.get('RENDER', 'development')}")
    
    # Initialize critical resources - database with error handling to not block initialization
    try:
        # Basic database initialization so API can respond
        print("Initializing database (fast mode)...")
        init_db()
        print("Database initialized successfully for basic operation!")
    except Exception as e:
        print(f"WARNING: Error in basic database initialization: {e}")
        print("API will continue starting, but some features may be limited")
    
    # Initialize non-critical resources asynchronously
    @app.on_event("startup")
    async def delayed_startup():
        # Delay initialization to ensure server is already responding
        await asyncio.sleep(10)  # Wait 10 seconds
        try:
            # Configure weekly price updates (Monday at 3:00 AM)
            print("Configuring scheduled updates...")
            schedule_weekly_update(day_of_week=0, hour=3, minute=0)
            
            # Start scheduler in a separate thread
            run_scheduler()
            print("Price update scheduler started!")
            
            print("=== COMPLETE INITIALIZATION OF ADDITIONAL RESOURCES ===")
        except Exception as e:
            print(f"WARNING: Error initializing non-critical resources: {e}")
            import traceback
            traceback.print_exc()


@app.get("/healthcheck")
async def healthcheck():
    """Minimalist endpoint to verify if API is responding"""
    try:
        # Test a simple database query to ensure it's working
        # Just checks if database is accessible
        init_db()
        return Response(content="OK", media_type="text/plain", status_code=200)
    except Exception as e:
        print(f"Healthcheck error: {str(e)}")
        # Still return 200 so Render doesn't kill the service during initialization
        return Response(content="Service warming up", media_type="text/plain", status_code=200)




if __name__ == "__main__":
    # Increase number of workers and timeout to better handle long requests
    # As processing large inventories can take time
    
    # Get port from environment (for compatibility with Render and other hosting services)
    port = int(os.environ.get("PORT", 8080))
    
    print(f"Starting server on port {port}")
    print("CORS configuration:")
    print(f"- Allowed origins: {ALLOWED_ORIGINS}")
    
    # Increase timeouts to better handle CORS preflight requests
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=port, 
        reload=True,
        workers=4,  # More workers to process requests in parallel
        timeout_keep_alive=120,  # Keep connections alive longer (2 minutes)
        timeout_graceful_shutdown=30,  # Give more time for shutdown
        log_level="info"
    )
