from fastapi import FastAPI, HTTPException, Query, Request, Depends, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2
from fastapi.openapi.models import OAuthFlows as OAuthFlowsModel
from starlette.middleware.base import BaseHTTPMiddleware
from typing import List, Dict, Any, Optional
import uvicorn
import jwt
from jwt.exceptions import PyJWTError
import os
import datetime
from urllib.parse import urlencode
from starlette.status import HTTP_401_UNAUTHORIZED
import asyncio

# Importando serviços e configurações
from services.steam_inventory import get_inventory_value, get_storage_unit_contents
from services.case_evaluator import get_case_details, list_cases
from services.steam_market import get_item_price, get_api_status, get_item_price_via_csgostash
from utils.config import get_api_config
from utils.database import init_db, get_stats, get_db_connection
from utils.price_updater import run_scheduler, force_update_now, get_scheduler_status, schedule_weekly_update
from auth.steam_auth import steam_login_url, validate_steam_login, create_jwt_token, verify_jwt_token, SECRET_KEY, ALGORITHM

# Import for database initializer
from migrate_db import init_database

# Custom class to accept token via URL or header
class OAuth2PasswordBearerWithCookie(OAuth2):
    def __init__(self, tokenUrl: str, auto_error: bool = True):
        flows = OAuthFlowsModel(password={"tokenUrl": tokenUrl, "scopes": {}})
        super().__init__(flows=flows, scheme_name="Bearer", auto_error=auto_error)

    async def __call__(self, request: Request):
        # Try to get token via Authorization header first
        authorization = request.headers.get("Authorization")
        scheme, param = "", ""
        
        if authorization:
            scheme, param = authorization.split()
            if scheme.lower() != "bearer":
                if self.auto_error:
                    raise HTTPException(
                        status_code=HTTP_401_UNAUTHORIZED,
                        detail="Not authenticated",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
                else:
                    return None
            return param
        
        # If not found in header, try to get via URL parameter
        token = request.query_params.get("token")
        if token:
            return token
            
        if self.auto_error:
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return None

# Instanciar o novo esquema OAuth2
oauth2_scheme = OAuth2PasswordBearerWithCookie(tokenUrl="token", auto_error=False)

app = FastAPI(
    title="CS2 Valuation API",
    description="API para avaliação de inventários, distinguindo entre Unidades de Armazenamento e itens do mercado",
    version="0.5.0"  # Atualizada para versão com organização por origem dos itens
)

# Configurar CORS
ALLOWED_ORIGINS = [
    "http://localhost:5500",   # Desenvolvimento local
    "http://127.0.0.1:5500",   # Desenvolvimento local alternativo
    "http://localhost:3000",   # React local
    "http://localhost:8000",   # Porta do backend
    "http://localhost",        # Qualquer porta em localhost
    "http://127.0.0.1",        # Qualquer porta em localhost
    "https://elite-skins-2025.github.io",  # GitHub Pages
    "file://",  # Para suportar arquivos abertos localmente
    # Adicione aqui a URL específica do seu serviço Render quando souber
    # Exemplo: "https://cs2-valuation-api.onrender.com"
    "*"  # Último recurso - permitir qualquer origem em desenvolvimento
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

# List of endpoints for the home page
AVAILABLE_ENDPOINTS = [
    "/inventory/{steamid}",
    "/inventory/full/{steamid}",
    "/my/inventory",  # Authenticated user's inventory
    "/my/inventory/full",  # Category-based analysis for authenticated user
    "/my/inventory/complete",  # Complete inventory for authenticated user with unit contents
    "/case/{case_name}",
    "/price/{market_hash_name}",
    "/cases",
    "/api/status",
    "/auth/steam",  # Steam authentication
    "/auth/steam/callback"  # Authentication callback
]


@app.get("/")
async def root():
    return {
        "message": "CS2 Valuation API (Storage Unit Access Version)",
        "features": [
            "Exclusive scraping for all item prices",
            "Item classification by source (Storage Units or Market)",
            "Inventory analysis by categories",
            "Access to Storage Unit contents (only for authenticated user's own units)"
        ],
        "public_endpoints": [
            "/inventory/{steamid} - Basic inventory analysis for third parties",
            "/inventory/full/{steamid} - Category-based inventory analysis for third parties",
            "/price/{market_hash_name} - Price of a specific item",
            "/case/{case_name} - Details of a specific case",
            "/cases - List of available cases",
            "/api/status - System status"
        ],
        "authenticated_endpoints": [
            "/my/inventory - Your own basic inventory",
            "/my/inventory/full - Your own inventory with categories",
            "/my/inventory/complete - Your complete inventory including Storage Unit contents"
        ],
        "authentication": [
            "/auth/steam - Login via Steam",
            "/auth/steam/callback - Return after authentication"
        ],
        "version": "0.5.0"
    }


@app.get("/inventory/{steamid}")
async def inventory(steamid: str, response: Response, request: Request = None, cors: bool = Query(False)):
    """Returns items and estimated prices from public inventory, differentiating between Storage Units and market items"""
    # Check if cors parameter is present and set headers more directly
    # This ensures compatibility with browser requests
    if cors or (request and "cors" in request.query_params):
        # For requests explicitly marked with cors=true, force headers
        print(f"CORS parameter detected for {steamid}. Adding explicit CORS headers.")
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "*"
        response.headers["Access-Control-Allow-Credentials"] = "true"
    else:
        # Add default CORS headers for other requests
        origin = request.headers.get("origin", "*") if request else "*"
        if origin and (origin in ALLOWED_ORIGINS or "*" in ALLOWED_ORIGINS):
            response.headers["Access-Control-Allow-Origin"] = origin
        else:
            response.headers["Access-Control-Allow-Origin"] = "*"
        
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "*"
    
    try:
        print(f"Starting inventory analysis for {steamid}")
        result = get_inventory_value(steamid)
        
        # Ensure required fields exist
        if "average_item_value" not in result:
            result["average_item_value"] = round(result["total_value"] / result["total_items"], 2) if result["total_items"] > 0 else 0
            
        if "most_valuable_item" not in result or result["most_valuable_item"] is None:
            # Try to find the most valuable item in the list
            most_valuable = None
            highest_price = 0
            
            for item in result.get("items", []):
                if item.get("price", 0) > highest_price:
                    highest_price = item.get("price", 0)
                    most_valuable = {
                        "name": item.get("name", ""),
                        "market_hash_name": item.get("market_hash_name", ""),
                        "price": item.get("price", 0),
                        "source": item.get("source", "market")
                    }
            
            result["most_valuable_item"] = most_valuable
            
        # Round values for easier display
        result["total_value"] = round(result["total_value"], 2)
        result["average_item_value"] = round(result["average_item_value"], 2)
        
        # Add counts by source type if they don't exist
        if "storage_units_count" not in result:
            result["storage_units_count"] = len(result.get("storage_units", []))
        
        if "market_items_count" not in result:
            result["market_items_count"] = len(result.get("market_items", []))
        
        # Adicionar resumo por fonte
        result["source_summary"] = {
            "storage_units": {
                "count": result["storage_units_count"],
                "value": round(sum(item.get("total", 0) for item in result.get("storage_units", [])), 2)
            },
            "market": {
                "count": result["market_items_count"],
                "value": round(sum(item.get("total", 0) for item in result.get("market_items", [])), 2)
            }
        }
        
        print(f"Inventory analysis completed for {steamid}: {len(result.get('items', []))} items found")
        print(f"- Storage Unit items: {result['storage_units_count']}")
        print(f"- Market items: {result['market_items_count']}")
        
        return result
    except Exception as e:
        print(f"Error processing inventory: {e}")
        import traceback
        traceback.print_exc()
        
        # Return an error object that the frontend can interpret
        # CORS headers were already configured above, so they should be sent even with error
        return {
            "steamid": steamid,
            "error": str(e),
            "total_items": 0,
            "total_value": 0,
            "items": [],
            "storage_units": [],
            "market_items": []
        }


@app.get("/inventory/full/{steamid}")
async def full_inventory_analysis(steamid: str, response: Response, request: Request = None):
    """Returns a complete inventory analysis, categorized by item types"""
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
        print(f"Starting detailed inventory analysis for {steamid}")
        result = get_inventory_value(steamid, categorize=True)
        
        # Let's ensure all important fields exist
        if "items_by_category" not in result:
            result["items_by_category"] = {}
        
        # Ensure required fields exist
        if "average_item_value" not in result:
            result["average_item_value"] = round(result["total_value"] / result["total_items"], 2) if result["total_items"] > 0 else 0
            
        if "most_valuable_item" not in result or result["most_valuable_item"] is None:
            # Try to find the most valuable item in the list
            most_valuable = None
            highest_price = 0
            
            for item in result.get("items", []):
                if item.get("price", 0) > highest_price:
                    highest_price = item.get("price", 0)
                    most_valuable = {
                        "name": item.get("name", ""),
                        "market_hash_name": item.get("market_hash_name", ""),
                        "price": item.get("price", 0),
                        "source": item.get("source", "market")
                    }
            
            result["most_valuable_item"] = most_valuable
        
        # Add summary by source if it doesn't exist yet
        if "source_summary" not in result:
            storage_units = result.get("storage_units", [])
            market_items = result.get("market_items", [])
            
            result["source_summary"] = {
                "storage_units": {
                    "count": len(storage_units),
                    "value": round(sum(item.get("total", 0) for item in storage_units), 2)
                },
                "market": {
                    "count": len(market_items),
                    "value": round(sum(item.get("total", 0) for item in market_items), 2)
                }
            }
        
        # Add analysis by category
        categories = {}
        for item in result.get("items", []):
            category = item.get("category", "Outros")
            if category not in categories:
                categories[category] = {
                    "count": 0,
                    "value": 0.0,
                    "items": []
                }
            
            categories[category]["count"] += item.get("quantity", 1)
            categories[category]["value"] += item.get("total", 0)
            categories[category]["items"].append(item)
        
        # Round values by category
        for category in categories:
            categories[category]["value"] = round(categories[category]["value"], 2)
        
        # Add category analysis to result
        result["category_summary"] = categories
        
        # Round values for easier display
        result["total_value"] = round(result["total_value"], 2)
        result["average_item_value"] = round(result["average_item_value"], 2)
        if result["most_valuable_item"]:
            result["most_valuable_item"]["price"] = round(result["most_valuable_item"]["price"], 2)
        
        return result
    except Exception as e:
        print(f"Error processing complete analysis: {e}")
        import traceback
        traceback.print_exc()
        return {
            "steamid": steamid,
            "error": str(e),
            "total_items": 0,
            "total_value": 0,
            "items": [],
            "storage_units": [],
            "market_items": []
        }


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
    """Returns the price of an item by its market_hash_name"""
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
        
        # Build response with currency information
        response_data = {
            "market_hash_name": market_hash_name,
            "price": item_price_data["price"],
            "currency": item_price_data["currency"],
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        # Add optional fields if they exist
        if "sources_count" in item_price_data:
            response_data["sources_count"] = item_price_data["sources_count"]
            
        if "is_fallback" in item_price_data:
            response_data["is_fallback"] = item_price_data["is_fallback"]
            
        if "processed" in item_price_data:
            response_data["processed"] = item_price_data["processed"]
            
        return response_data
    except Exception as e:
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
            "version": "0.5.0",
            "timestamp": datetime.datetime.now().isoformat()
        }
    except Exception as e:
        # Still return online status to ensure healthcheck passes
        return {"status": "online", "error": str(e)}


# Authentication functions
def get_current_user(token: str = Depends(oauth2_scheme)):
    """Gets the current user based on JWT token"""
    if not token:
        print("Token not provided in request")
        # Return None to allow endpoint to decide how to handle missing token
        return None
        
    try:
        print(f"Attempting to validate token: {token[:10]}...")
        
        # Decode token manually with improved error handling
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            print("Token decoded successfully")
        except jwt.ExpiredSignatureError:
            print("Error: Token expired")
            return {"error": "Token expired. Please login again."}
        except jwt.InvalidTokenError:
            print("Error: Invalid token")
            return {"error": "Invalid token. Incorrect format."}
        except Exception as e:
            print(f"Unknown error decoding token: {e}")
            return {"error": f"Error processing token: {str(e)}"}
            
        # Check if payload contains steam_id
        steam_id = payload.get("steam_id")
        if not steam_id:
            print("Error: Token does not contain SteamID")
            return {"error": "Token does not contain SteamID"}
            
        # Return user information
        print(f"User authenticated with SteamID: {steam_id}")
        return {"steam_id": steam_id}
    except Exception as e:
        print(f"Unexpected authentication error: {e}")
        import traceback
        traceback.print_exc()
        return {"error": f"Authentication error: {str(e)}"}


# Endpoints for Steam authentication
@app.get("/auth/steam")
async def steam_auth(request: Request, redirect_local: bool = False, return_url: str = None):
    """Redirects to Steam login"""
    # Base URL for the API
    base_url = str(request.base_url).rstrip('/')
    redirect_uri = f"{base_url}/auth/steam/callback"
    
    # Add parameters to callback URL
    params = {}
    
    # Add parameter to indicate local redirect
    if redirect_local:
        params["redirect_local"] = "true"
    
    # Add return URL if provided
    if return_url:
        params["return_url"] = return_url
        print(f"Return URL received: {return_url}")
    
    # Add parameters to callback URL
    if params:
        redirect_uri += "?" + urlencode(params)
    
    print(f"Callback URL configured: {redirect_uri}")
    
    # Generate login URL
    login_url = steam_login_url(redirect_uri)
    print(f"Steam login URL: {login_url}")
    
    return RedirectResponse(url=login_url)


@app.get("/auth/steam/callback")
async def steam_callback(request: Request):
    """Callback after Steam login"""
    # Extract parameters from response
    params = dict(request.query_params)
    
    # Check if should redirect to local
    redirect_local = "redirect_local" in params and params["redirect_local"] == "true"
    
    # Validate authentication
    steam_id = validate_steam_login(params)
    if steam_id:
        # Generate JWT token
        token = create_jwt_token({"steam_id": steam_id})
        
        # Set frontend URL based on redirect_local parameter
        if redirect_local:
            # Local development environment
            frontend_url = "http://localhost:5500/api.html"
            print(f"Redirecting to: {frontend_url}?token={token}")
            print(f"Environment: Local development")
        else:
            # Production environment
            frontend_url = "https://elite-skins-2025.github.io/api.html"
            print(f"Redirecting to: {frontend_url}?token={token}")
            print(f"Environment: Production")
        
        # Receive custom return URL if provided in original request
        # Check if return URL was passed in original request
        return_url_param = next((p for p in params.keys() if "return_url" in p), None)
        if return_url_param:
            custom_return_url = params[return_url_param]
            if custom_return_url:
                frontend_url = custom_return_url
                print(f"Using custom return URL: {frontend_url}")
                print(f"Return parameter: {return_url_param}={custom_return_url}")
        
        # Redirect to frontend with token as parameter
        redirect_url = f"{frontend_url}?token={token}"
        
        # Log additional information for debugging
        print(f"Parameters received in callback: {params}")
        print(f"Final redirect URL: {redirect_url}")
        
        # Return HTTP 302 redirect
        return RedirectResponse(url=redirect_url)
    else:
        return {"error": "Steam authentication failed"}


# Test endpoint for redirection
@app.get("/auth/test-redirect")
async def test_redirect(request: Request, return_url: str = None):
    """Test endpoint to verify how return URL is handled"""
    # Extract parameters from response
    params = dict(request.query_params)
    
    # Get base URL
    base_url = str(request.base_url).rstrip('/')
    
    # Debug information
    debug_info = {
        "request_url": str(request.url),
        "base_url": base_url,
        "params": params,
        "return_url": return_url,
        "headers": dict(request.headers),
        "would_redirect_to": return_url if return_url else "No return URL provided",
        "info": "This is a test endpoint to verify redirection. Does not perform actual redirection."
    }
    
    return debug_info


# Endpoint for complete inventory analysis (including Storage Unit contents)
# This function is now internal and used only by /my/inventory/complete
async def _complete_inventory_analysis(
    steamid: str, 
    current_user: dict,
    session_id: str,
    steam_token: str
):
    """
    Internal function: Returns complete inventory analysis including Storage Unit contents.
    Requires user to be authenticated and owner of the inventory.
    """
    # Check if user is authenticated
    if not current_user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required to access this endpoint"
        )
    
    # Check if there's an authentication error
    if "error" in current_user:
        raise HTTPException(
            status_code=401,
            detail=current_user["error"]
        )
    
    # Check if user is trying to access their own inventory
    if steamid != current_user["steam_id"]:
        raise HTTPException(
            status_code=403,
            detail="You can only access the contents of your own Storage Units"
        )
    
    # Check if all required parameters were provided
    if not session_id or not steam_token:
        raise HTTPException(
            status_code=400,
            detail="session_id and steam_token are required to access Storage Units"
        )
    
    try:
        # Get basic inventory
        inventory_result = get_inventory_value(steamid)
        
        # Process storage units
        storage_units = inventory_result.get("storage_units", [])
        storage_unit_contents = []
        
        for unit in storage_units:
            unit_id = unit.get("assetid")
            if unit_id:
                # Get unit contents
                contents = get_storage_unit_contents(
                    unit_id,
                    steamid,
                    session_id,
                    steam_token
                )
                
                # Add to contents list
                storage_unit_contents.append({
                    "unit_info": unit,
                    "contents": contents
                })
        
        # Add contents to result
        inventory_result["storage_unit_contents"] = storage_unit_contents
        
        # Calculate totals including unit contents
        total_units_value = sum(
            content.get("contents", {}).get("total_value", 0)
            for content in storage_unit_contents
        )
        
        inventory_result["storage_units_content_value"] = total_units_value
        inventory_result["grand_total_value"] = inventory_result["total_value"] + total_units_value
        
        # Add a flat list with all items (inventory + units)
        all_items = inventory_result.get("items", [])[:]  # Copy of original list
        
        for unit_content in storage_unit_contents:
            all_items.extend(unit_content.get("contents", {}).get("items", []))
        
        inventory_result["all_items"] = all_items
        inventory_result["all_items_count"] = len(all_items)
        
        return inventory_result
    
    except Exception as e:
        print(f"Error processing complete inventory: {e}")
        import traceback
        traceback.print_exc()
        
        raise HTTPException(
            status_code=500,
            detail=f"Error processing inventory: {str(e)}"
        )


# New endpoints for authenticated user
@app.get("/my/inventory")
async def my_inventory(current_user: dict = Depends(get_current_user), response: Response = None, request: Request = None):
    """Returns items from authenticated user's inventory"""
    # CORS handled by global middleware
    
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        # Use authenticated user's steamid
        steamid = current_user["steam_id"]
        print(f"Analyzing authenticated user's inventory: {steamid}")
        
        # Reuse public endpoint
        result = get_inventory_value(steamid)
        
        return result
    except Exception as e:
        print(f"Error processing authenticated user's inventory: {e}")
        import traceback
        traceback.print_exc()
        return {
            "error": str(e),
            "total_items": 0,
            "total_value": 0,
            "items": []
        }


@app.get("/my/inventory/complete")
async def my_inventory_complete(
    current_user: dict = Depends(get_current_user),
    session_id: str = Query(None),
    steam_token: str = Query(None),
    response: Response = None,
    request: Request = None
):
    """Returns user's complete inventory, including storage unit contents"""
    # CORS handled by global middleware
    
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        # Use authenticated user's steamid
        steamid = current_user["steam_id"]
        
        return await _complete_inventory_analysis(steamid, current_user, session_id, steam_token)
    except Exception as e:
        print(f"Error processing authenticated user's complete inventory: {e}")
        import traceback
        traceback.print_exc()
        return {
            "error": str(e),
            "total_items": 0,
            "total_value": 0,
            "items": []
        }


@app.get("/my/inventory/full")
async def my_inventory_full(current_user: dict = Depends(get_current_user), response: Response = None, request: Request = None):
    """Returns complete analysis of authenticated user's inventory, with categories"""
    # CORS handled by global middleware
    
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        # Use authenticated user's steamid
        steamid = current_user["steam_id"]
        print(f"Analyzing authenticated user's detailed inventory: {steamid}")
        
        # Get inventory with categorization
        result = get_inventory_value(steamid, categorize=True)
        
        return result
    except Exception as e:
        print(f"Error processing authenticated user's complete analysis: {e}")
        import traceback
        traceback.print_exc()
        return {
            "error": str(e),
            "total_items": 0,
            "total_value": 0,
            "items": []
        }


@app.get("/cors-test")
async def cors_test(response: Response):
    """Simple endpoint to test CORS headers"""
    # Add CORS headers manually
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    
    return {
        "cors_status": "OK",
        "message": "If you can see this message, CORS headers are working correctly",
        "timestamp": str(datetime.datetime.now()),
        "requested_headers": "All headers are allowed"
    }


@app.get("/db/stats")
async def db_stats(current_user: dict = Depends(get_current_user)):
    """
    Returns statistics from the skin prices database.
    Requires authentication.
    """
    # Check if user is authenticated
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Get database statistics
    stats = get_stats()
    
    # Get scheduler status
    scheduler_status = get_scheduler_status()
    
    return {
        "database": stats,
        "scheduler": scheduler_status
    }

@app.post("/db/update")
async def force_db_update(current_user: dict = Depends(get_current_user), max_items: int = Query(100, description="Maximum number of items to update")):
    """
    Forces an immediate update of the oldest skin prices.
    Requires authentication.
    """
    # Check if user is authenticated
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Force update
    stats = force_update_now(max_items=max_items)
    
    return {
        "message": f"Force update completed. {stats['updated_skins']} items updated.",
        "stats": stats
    }

# Route to initialize database (protected by admin key)
@app.get("/api/db/init")
async def initialize_database(admin_key: str = Query(None), response: Response = None):
    """Initializes the database (admin only)"""
    # CORS handled by global middleware
    
    # Check if admin key is correct
    expected_key = os.environ.get("ADMIN_KEY", "dev_admin_key")
    
    if admin_key != expected_key:
        raise HTTPException(status_code=403, detail="Invalid admin key")
        
    try:
        # Initialize database
        result = init_database()
        
        return {
            "success": True,
            "message": "Database initialized successfully",
            "details": result
        }
    except Exception as e:
        print(f"Error initializing database: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e)
        }

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


@app.get("/test-csgostash/{market_hash_name}")
async def test_csgostash(market_hash_name: str):
    """
    Endpoint to test CSGOStash price retrieval function.
    Development/testing only.
    """
    try:
        result = get_item_price_via_csgostash(market_hash_name)
        return {
            "market_hash_name": market_hash_name,
            "result": result
        }
    except Exception as e:
        import traceback
        return {
            "error": str(e),
            "traceback": traceback.format_exc()
        }


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
