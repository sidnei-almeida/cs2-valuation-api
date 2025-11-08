import requests
import json
import time
import re
import struct
import base64
from typing import Dict, List, Any, Optional, Tuple
from services.steam_market import get_item_price, get_steam_api_data
from utils.config import STEAM_API_KEY, STEAM_MARKET_CURRENCY, STEAM_APPID, STEAM_REQUEST_DELAY
import os
from dotenv import load_dotenv

# Load environment variables (if .env file exists)
load_dotenv()

# Base URL for Steam inventory API
STEAM_INVENTORY_URL = "https://steamcommunity.com/inventory/{steamid}/730/2"

# URL to get float values
FLOAT_API_URL = "https://api.csgofloat.com/?url="


def get_inventory_value(steamid: str, categorize: bool = False) -> Dict[str, Any]:
    """
    Gets the CS2 inventory value of a user.
    
    Args:
        steamid: User's Steam ID
        categorize: If True, categorizes items by type
        
    Returns:
        Dictionary with inventory information and total value
    """
    print(f"Starting inventory retrieval for SteamID: {steamid}")
    
    # Clean Steam ID of unwanted characters or URL encoding
    # Remove braces {} and any URL encoding (%7B = { and %7D = })
    steamid = steamid.replace("{", "").replace("}", "").replace("%7B", "").replace("%7D", "")
    print(f"Normalized Steam ID: {steamid}")
    
    # First try to get inventory using public endpoint
    print("Attempting to get inventory via public endpoint...")
    real_inventory = get_real_inventory(steamid)
    if real_inventory:
        print(f"Complete inventory obtained via public endpoint: {len(real_inventory.get('items', []))} items found")
        
        # Add categorization if requested
        if categorize:
            real_inventory = categorize_inventory(real_inventory)
            
        return real_inventory
    
    # If it fails, try with official API (if configured)
    if STEAM_API_KEY:
        print(f"Public endpoint failed, trying official API...")
        api_inventory = get_api_inventory(steamid)
        if api_inventory:
            print(f"Complete inventory obtained via official API: {len(api_inventory.get('items', []))} items found")
            
            # Add categorization if requested
            if categorize:
                api_inventory = categorize_inventory(api_inventory)
                
            return api_inventory
        print("Failed to get inventory via official API.")
    else:
        print("API key not configured and public endpoint failed.")
    
    # Return empty inventory instead of mocked data
    print(f"Unable to get inventory for {steamid} or inventory is empty")
    
    # Create a valid empty inventory
    empty_inventory = {
        "steamid": steamid,
        "total_items": 0,
        "total_value": 0.0,
        "currency": "BRL",
        "items": [],
        "most_valuable_item": None,
        "storage_units": [],
        "market_items": [],
        "storage_units_count": 0,
        "market_items_count": 0,
        "average_item_value": 0.0,
        "note": "Inventário vazio ou não acessível"
    }
    
    # Adicionar categorização se solicitado
    if categorize:
        empty_inventory["items_by_category"] = {}
        
    return empty_inventory


def get_api_inventory(steamid: str) -> Optional[Dict[str, Any]]:
    """
    Gets a Steam user's inventory using the official API.
    
    Args:
        steamid: User's Steam ID
        
    Returns:
        Dictionary with inventory information or None if it fails
    """
    print(f"Attempting to get inventory via official API for {steamid}...")
    
    # Use official API to get inventory
    # The official IEconItems_730 API already returns all items at once
    # without pagination needed in most cases
    inventory_data = get_steam_api_data(
        "IEconItems_730",  # Interface para CS2
        "GetPlayerItems",  # Método
        "v1",              # Versão
        {"steamid": steamid}
    )
    
    if inventory_data:
        print(f"Inventory successfully obtained via official API for {steamid}")
        # Process official API data
        return process_api_inventory_data(inventory_data, steamid)
    else:
        print(f"Failed to get inventory via official API for {steamid}")
        
    return None


def get_real_inventory(steamid: str, appid: int = None) -> Optional[Dict[str, Any]]:
    """
    Gets a Steam user's real inventory.
    
    Args:
        steamid: User's Steam ID
        appid: Steam application ID. If None, uses configured value
        
    Returns:
        Dictionary with inventory information or None if it fails
    """
    if appid is None:
        appid = STEAM_APPID
        
    # Get complete inventory via public endpoint with pagination support
    all_assets = []
    all_descriptions = []
    
    # Base URL for inventory API
    base_url = STEAM_INVENTORY_URL.format(steamid=steamid)
    
    # Start with first page
    url = base_url
    count = 0
    max_tries = 30  # Increased limit for more pages (was 10)
    
    try:
        # Add user-agent to avoid blocks
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Loop to get all inventory pages
        while url and count < max_tries:
            print(f"Fetching page {count+1} of inventory for {steamid}...")
            
            response = requests.get(url, headers=headers, timeout=15)  # Added timeout
            
            if response.status_code == 200:
                inventory_data = response.json()
                
                # Check if there's valid data
                if "assets" not in inventory_data or "descriptions" not in inventory_data:
                    print(f"Invalid inventory format on page {count+1}")
                    break
                
                # Add assets and descriptions from this page
                all_assets.extend(inventory_data.get("assets", []))
                all_descriptions.extend(inventory_data.get("descriptions", []))
                
                # Check if there are more pages
                if "more_items" in inventory_data and inventory_data["more_items"] == 1:
                    # Get last assetid for next page
                    last_assetid = inventory_data.get("last_assetid")
                    if last_assetid:
                        # Build URL for next page
                        url = f"{base_url}?start_assetid={last_assetid}"
                        
                        # Wait before next request to avoid rate limit
                        time.sleep(STEAM_REQUEST_DELAY * 1.5)
                    else:
                        print("Unable to get last item ID for pagination")
                        break
                else:
                    # No more pages
                    break
                    
                count += 1
                print(f"Processed page {count} with {len(inventory_data.get('assets', []))} items")
            elif response.status_code == 403:
                print(f"Private or inaccessible inventory for user {steamid}")
                return None
            else:
                print(f"Error accessing inventory: Status {response.status_code}")
                return None
                
            # Respect request limit
            time.sleep(STEAM_REQUEST_DELAY)
            
        # Combinar todas as páginas em um único objeto de inventário
        combined_inventory = {
            "assets": all_assets,
            "descriptions": all_descriptions,
            "total_inventory_count": len(all_assets)
        }
        
        # Processar os dados do inventário combinado
        if all_assets:
            processed_inventory = process_inventory_data(combined_inventory, steamid)
            print(f"Total items processed: {len(all_assets)} in {count} pages")
            return processed_inventory
        else:
            print(f"No items found in inventory for {steamid}")
            
    except Exception as e:
        print(f"Error getting inventory for {steamid}: {e}")
        import traceback
        traceback.print_exc()
    
    return None


def process_inventory_data(inventory_data: Dict[str, Any], steamid: str) -> Dict[str, Any]:
    """
    Processa os dados brutos do inventário da Steam.
    Distingue entre itens de Unidades de Armazenamento e itens de mercado.
    
    Args:
        inventory_data: Dados brutos do inventário
        steamid: ID da Steam do usuário
        
    Returns:
        Dicionário processado com itens do inventário categorizados
    """
    result = {
        "steamid": steamid,
        "total_items": 0,
        "total_value": 0.0,
        "average_item_value": 0.0,
        "currency": "BRL",
        "items": [],
        "most_valuable_item": None,
        "storage_units": [],  # Lista de Unidades de Armazenamento
        "market_items": []    # Lista de itens do mercado
    }
    
    try:
        # Check if we have necessary information
        if "assets" not in inventory_data or "descriptions" not in inventory_data:
            print("Invalid inventory format or empty inventory")
            return result
            
        # Map 'descriptions' by classid for fast access
        descriptions = {}
        for desc in inventory_data["descriptions"]:
            key = f"{desc.get('classid')}_{desc.get('instanceid')}"
            descriptions[key] = desc
            
        # Processar cada item do inventário
        processed_items = []
        storage_units = []
        market_items = []
        
        total_value = 0.0
        most_valuable_item = None
        highest_value = 0.0
        items_with_value = 0  # Para calcular a média corretamente
        
        # Contadores para estatísticas
        processed_count = 0
        valuable_count = 0
        sticker_count = 0
        
        for asset in inventory_data["assets"]:
            asset_id = asset.get("assetid")
            classid = asset.get("classid")
            instanceid = asset.get("instanceid")
            amount = int(asset.get("amount", 1))
            
            # Find item description
            desc_key = f"{classid}_{instanceid}"
            if desc_key in descriptions:
                processed_count += 1
                desc = descriptions[desc_key]
                
                # Extract relevant information
                market_hash_name = desc.get("market_hash_name", "")
                name = desc.get("name", "")
                type_info = desc.get("type", "")
                tradable = desc.get("tradable", 0) == 1
                
                # Verificar se é uma Unidade de Armazenamento
                is_storage_unit = "Storage Unit" in name or "Unidade de Armazenamento" in name
                
                # Verificar se é um adesivo
                is_sticker = "Sticker" in name or "Adesivo" in name
                if is_sticker:
                    sticker_count += 1
                    
                # Item especial (StatTrak, Souvenir)
                is_special = "StatTrak™" in name or "Souvenir" in name
                
                # Extract inspection URL and get float value
                inspect_url = extract_inspect_url(desc)
                float_value = None
                
                # Só obter float para armas e facas (não para caixas, adesivos, etc.)
                # Isso evita consultas desnecessárias à API
                if inspect_url and not is_sticker and not is_storage_unit:
                    # Verificar se é uma arma ou faca (que têm float)
                    has_float = any(cat in type_info.lower() for cat in [
                        "pistol", "rifle", "smg", "shotgun", "machinegun", 
                        "sniper rifle", "knife", "★"
                    ])
                    
                    if has_float:
                        float_value = get_item_float(inspect_url)
                        if float_value is not None:
                            print(f"Float obtido para {market_hash_name}: {float_value:.10f}")
                
                # Obter preço do item
                price = 0.0
                if tradable:
                    try:
                        price_data = get_item_price(market_hash_name)
                        if isinstance(price_data, dict):
                            price = price_data.get("price", 0.0)
                        else:
                            price = float(price_data) if price_data else 0.0
                            
                        if price > 0:
                            valuable_count += 1
                            
                            # Ajustar preço com base no float (para itens que têm)
                            if float_value is not None:
                                price = adjust_price_by_float(price, float_value, market_hash_name)
                    except Exception as e:
                        print(f"Error getting price for {market_hash_name}: {e}")
                
                item_total = price * amount
                
                # Extract category and type
                category, item_type = parse_item_type(type_info, desc)
                
                # Verificar se o item tem tags que indicam qualidade/raridade 
                tags = desc.get("tags", [])
                rarity = next((tag.get("name", "") for tag in tags if tag.get("category") == "Rarity"), "Normal")
                exterior = next((tag.get("name", "") for tag in tags if tag.get("category") == "Exterior"), "Not Painted")
                
                # Criar objeto item
                item = {
                    "assetid": asset_id,
                    "name": name,
                    "market_hash_name": market_hash_name,
                    "quantity": amount,
                    "price": price,
                    "total": item_total,
                    "tradable": tradable,
                    "category": category,
                    "type": item_type,
                    "rarity": rarity,
                    "exterior": exterior,
                    "stattrak": "StatTrak™" in name,
                    "souvenir": "Souvenir" in name,
                    "is_sticker": is_sticker,
                    "image": get_item_image(desc),
                    "source": "storage_unit" if is_storage_unit else "market",
                    "inspect_url": inspect_url,  # Nova propriedade: URL de inspeção
                    "float_value": float_value   # Nova propriedade: Valor float
                }
                
                # Adicionar à categoria apropriada
                if is_storage_unit:
                    storage_units.append(item)
                else:
                    market_items.append(item)
                
                # Adicionar à lista geral de itens
                processed_items.append(item)
                
                # Atualizar item mais valioso
                if price > highest_value:
                    highest_value = price
                    most_valuable_item = {
                        "name": name,
                        "market_hash_name": market_hash_name,
                        "price": price,
                        "rarity": rarity,
                        "category": category,
                        "source": "storage_unit" if is_storage_unit else "market",
                        "float_value": float_value  # Adicionar float ao item mais valioso
                    }
                    print(f"Novo item mais valioso encontrado: {name} - R$ {price:.2f}" + 
                          (f" (Float: {float_value:.10f})" if float_value is not None else ""))
                
                # Atualizar valor total
                total_value += item_total
                
                # Contar apenas itens com valor na média
                if price > 0:
                    items_with_value += amount
                
        # Atualizar resultados
        result["items"] = processed_items
        result["storage_units"] = storage_units
        result["market_items"] = market_items
        result["total_items"] = sum(item.get("quantity", 1) for item in processed_items)
        result["total_value"] = total_value
            
        # Calcular valor médio (apenas para itens com valor)
        result["average_item_value"] = total_value / items_with_value if items_with_value > 0 else 0
        
        # Atualizar item mais valioso
        result["most_valuable_item"] = most_valuable_item
        
        # Adicionar contagens por categoria
        result["storage_units_count"] = len(storage_units)
        result["market_items_count"] = len(market_items)
        
        # Adicionar estatísticas detalhadas
        result["stats"] = {
            "processed_count": processed_count,
            "valuable_items_count": valuable_count,
            "sticker_count": sticker_count,
            "total_pages_processed": inventory_data.get("total_pages", 1),
            "items_with_float": sum(1 for item in processed_items if item.get("float_value") is not None)
        }
        
        print(f"Processed {processed_count} items, totaling {result['total_items']} units, worth R$ {total_value:.2f}")
        print(f"Valuable items: {valuable_count}, Stickers: {sticker_count}")
        print(f"Items with float obtained: {result['stats']['items_with_float']}")
        
    except Exception as e:
        print(f"Error processing inventory: {e}")
        import traceback
        traceback.print_exc()
        
    return result


def process_api_inventory_data(api_data: Dict[str, Any], steamid: str) -> Dict[str, Any]:
    """
    Processa os dados obtidos pela API oficial da Steam.
    
    Args:
        api_data: Dados brutos da API oficial
        steamid: ID da Steam do usuário
        
    Returns:
        Dicionário processado com itens do inventário
    """
    result = {
        "steamid": steamid,
        "total_items": 0,
        "total_value": 0.0,
        "average_item_value": 0.0,
        "currency": "BRL",
        "items": [],
        "most_valuable_item": None
    }
    
    try:
        # Check if we have necessary information
        if "result" not in api_data or "status" not in api_data["result"] or api_data["result"]["status"] != 1:
            print("Error getting inventory or inventory is empty")
            return result
            
        if "items" not in api_data["result"]:
            print("No items found in inventory")
            return result
            
        # Processar cada item do inventário
        items_data = api_data["result"]["items"]
        processed_items = []
        total_value = 0.0
        most_valuable_item = None
        highest_value = 0.0
        items_with_value = 0  # Para calcular a média corretamente
        
        # Debug: Contar itens processados
        processed_count = 0
        
        for item in items_data:
            processed_count += 1
            # Extrair informações relevantes do item
            item_name = item.get("name", "")
            market_hash_name = item.get("market_hash_name", item_name)
            
            # Debug para itens de alto valor
            if "Knife" in item_name or "★" in item_name or "Gloves" in item_name:
                print(f"Item potencialmente valioso encontrado: {item_name} ({market_hash_name})")
            
            # Obter categoria, raridade, exterior
            item_tags = item.get("tags", [])
            category = next((tag.get("localized_tag_name") for tag in item_tags if tag.get("category") == "Type"), "Other")
            rarity = next((tag.get("localized_tag_name") for tag in item_tags if tag.get("category") == "Rarity"), "Normal")
            exterior = next((tag.get("localized_tag_name") for tag in item_tags if tag.get("category") == "Exterior"), "Not Painted")
            
            # Verificar se é negociável
            tradable = item.get("tradable", 0) == 1
            
            # Verificar se o item é especial (Stattrak, Souvenir, etc)
            is_stattrak = "StatTrak™" in item_name
            is_souvenir = "Souvenir" in item_name
            
            # Obter preço do mercado
            price = get_item_price(market_hash_name) if tradable else 0.0
            
            # Atualizar item mais valioso
            if price > highest_value:
                highest_value = price
                most_valuable_item = {
                    "name": item_name,
                    "market_hash_name": market_hash_name,
                    "price": price
                }
                print(f"Novo item mais valioso encontrado: {item_name} - R$ {price:.2f}")
            
            # Contar para média apenas se tiver valor
            if price > 0:
                total_value += price
                items_with_value += 1
            
            # Criar objeto do item processado
            processed_item = {
                "name": item_name,
                "market_hash_name": market_hash_name,
                "category": category,
                "rarity": rarity,
                "exterior": exterior,
                "tradable": tradable,
                "stattrak": is_stattrak,
                "souvenir": is_souvenir,
                "price": price,
                "total": price,  # Quantidade é sempre 1 para itens da API oficial
                "quantity": 1,
                "image": f"https://community.cloudflare.steamstatic.com/economy/image/{item.get('icon_url', '')}"
            }
            
            processed_items.append(processed_item)
        
        print(f"Total items processed via official API: {processed_count} of {len(items_data)}")
        print(f"Total items with value: {items_with_value}")
        print(f"Total inventory value: R$ {total_value:.2f}")
        
        # Calculate average value per item (only for items with value)
        average_value = total_value / items_with_value if items_with_value > 0 else 0
        print(f"Average value per item: R$ {average_value:.2f}")
        
        # Atualizar resultados
        result["items"] = processed_items
        result["total_items"] = len(processed_items)
        result["total_value"] = total_value
        result["average_item_value"] = average_value
        result["most_valuable_item"] = most_valuable_item
        
    except Exception as e:
        print(f"Error processing inventory via API: {e}")
        import traceback
        traceback.print_exc()
        
    return result


def parse_item_type(type_info: str, desc: Dict[str, Any]) -> tuple:
    """
    Extracts the category and type of the item based on its information.
    
    Args:
        type_info: Item type text
        desc: Complete item description
        
    Returns:
        Tuple (category, type)
    """
    category = "Outros"
    item_type = type_info
    
    # A categoria geralmente está na primeira parte do type_info
    parts = type_info.split()
    if parts:
        base_type = parts[0].lower()
        
        # Mapeamento de tipos para categorias
        if base_type in ["pistol", "pistola"]:
            category = "Pistolas"
        elif base_type in ["rifle", "smg"]:
            category = "Rifles"
        elif base_type in ["knife", "★"]:
            category = "Facas"
        elif base_type in ["gloves", "luvas", "hand", "wraps"]:
            category = "Luvas"
        elif base_type in ["sticker", "adesivo"]:
            category = "Adesivos"
        elif base_type in ["case", "caixa"]:
            category = "Caixas"
        elif "key" in base_type or "chave" in base_type:
            category = "Chaves"
        elif "agent" in base_type or "agente" in base_type:
            category = "Agentes"
        elif "container" in base_type or "package" in base_type:
            category = "Pacotes"
        elif "pin" in base_type or "patch" in base_type:
            category = "Souvenirs"
            
    # Check tags to extract additional information
    tags = desc.get("tags", [])
    for tag in tags:
        if tag.get("category") == "Type":
            item_type = tag.get("name", item_type)
            
            # Mapear categorias específicas
            type_lower = item_type.lower()
            if any(knife in type_lower for knife in ["knife", "facas", "★"]):
                category = "Facas"
            elif any(glove in type_lower for glove in ["gloves", "luvas", "hand", "wraps"]):
                category = "Luvas"
            
    return category, item_type


def get_item_image(desc: Dict) -> str:
    """
    Gets the item image URL.
    
    Args:
        desc: Item description
        
    Returns:
        Image URL
    """
    # Large images have priority
    icon_url_large = desc.get("icon_url_large", "")
    if icon_url_large:
        return f"https://community.cloudflare.steamstatic.com/economy/image/{icon_url_large}"
    
    # If no large image, use normal one
    icon_url = desc.get("icon_url", "")
    if icon_url:
        return f"https://community.cloudflare.steamstatic.com/economy/image/{icon_url}"
    
    # Fallback: default image
    return "https://community.cloudflare.steamstatic.com/economy/image/IzMF03bi9WpSBq-S-ekoE33L-iLqGFHVaU25ZzQNQcXdB2ozio1RrlIWFK3UfvMYB8UsvjiMXojflsZalyxSh31CIyHz2GZ-KuFpPsrTzBG0ouqID2fIYCPBLi6NBg06GPAZN2nB-zeo5ObGFz3BQewrFAsHf_UF9mMba5rYPRQ81oQMrDTvkxUlUQIbPsleJED-4ngAb7oTkmM"


def get_item_float(inspect_url: str) -> Optional[float]:
    """
    Gets the float value (wear) of an item from its inspection URL.
    Tries to use CSGOFloat API.
    
    Args:
        inspect_url: Item inspection URL
        
    Returns:
        Item float value or None if unable to get
    """
    if not inspect_url:
        return None
        
    try:
        # Adicionar delay para evitar bloqueios pela API
        time.sleep(1)
        
        # Tentar obter via API CSGOFloat
        response = requests.get(f"{FLOAT_API_URL}{inspect_url}", timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            if 'iteminfo' in data and 'floatvalue' in data['iteminfo']:
                float_value = data['iteminfo']['floatvalue']
                return float_value
                
        print(f"Failed to get float via API: Status {response.status_code}")
    except Exception as e:
        print(f"Error getting float value: {e}")
        
    return None


def extract_inspect_url(desc: Dict) -> Optional[str]:
    """
    Extrai a URL de inspeção de um item a partir da descrição.
    
    Args:
        desc: Descrição do item do inventário
        
    Returns:
        URL de inspeção ou None se não estiver disponível
    """
    # Para itens normais, a URL de inspeção está em actions[0].link
    actions = desc.get('actions', [])
    if actions and 'link' in actions[0]:
        link = actions[0]['link']
        # Substituir o placeholder %owner_steamid% pelo ID do proprietário
        # Isso não é necessário para a API CSGOFloat
        return link
        
    # Para itens dentro de unidades de armazenamento, a URL pode estar em outro formato
    # Isso é apenas um stub - a lógica real dependeria da estrutura exata do item
    
    return None


def categorize_inventory(inventory: Dict[str, Any]) -> Dict[str, Any]:
    """
    Categoriza os itens do inventário por tipo.
    
    Args:
        inventory: Dados do inventário
        
    Returns:
        Inventário com itens categorizados
    """
    items_by_category = {}
    
    for item in inventory.get("items", []):
        category = item.get("category", "Outros")
        
        if category not in items_by_category:
            items_by_category[category] = {
                "items": [],
                "count": 0,
                "value": 0.0
            }
            
        items_by_category[category]["items"].append(item)
        items_by_category[category]["count"] += item.get("quantity", 1)
        items_by_category[category]["value"] += item.get("total", 0)
        
    # Arredondar valores
    for category in items_by_category:
        items_by_category[category]["value"] = round(items_by_category[category]["value"], 2)
        
    # Adicionar ao resultado
    inventory["items_by_category"] = items_by_category
    
    return inventory


def adjust_price_by_float(base_price: float, float_value: float, market_hash_name: str) -> float:
    """
    Adjusts an item's price based on float value.
    Items with low float (newer) are generally worth more.
    
    Args:
        base_price: Base item price
        float_value: Item float value (0 to 1)
        market_hash_name: Item name for special cases
        
    Returns:
        Adjusted price
    """
    # Wear ranges: https://csgofloat.com/
    # Factory New: 0.00 - 0.07
    # Minimal Wear: 0.07 - 0.15
    # Field-Tested: 0.15 - 0.38
    # Well-Worn: 0.38 - 0.45
    # Battle-Scarred: 0.45 - 1.00
    
    # Verificar se é um item popular onde o float faz grande diferença
    high_value_patterns = [
        "fade", "doppler", "marble fade", "crimson web", "case hardened",
        "dragon lore", "medusa", "howl", "fire serpent", "asiimov",
        "tiger tooth", "slaughter", "autotronic", "lore", "gamma doppler",
        "★", "knife", "gloves"
    ]
    
    # Verificar se é um item de alto valor
    is_high_value = any(pattern in market_hash_name.lower() for pattern in high_value_patterns)
    
    # Ajustes mais intensos para itens de valor alto
    if is_high_value:
        # Para Factory New, quanto mais baixo o float, mais valioso
        if float_value < 0.07:  # Factory New
            # Escala logarítmica: valores mais baixos têm efeito exponencial
            # float 0.069 = x1.1, float 0.03 = x1.5, float 0.01 = x2, float 0.001 = x3
            if float_value < 0.001:  # Ultra raro
                return base_price * 4.0  # Quadruplicar o valor
            elif float_value < 0.01:
                return base_price * (3.0 - float_value * 100)  # Entre x2 e x3
            elif float_value < 0.03:
                return base_price * (2.0 - float_value * 33)  # Entre x1.5 e x2
            else:
                return base_price * (1.1 + (0.07 - float_value) * 5.7)  # Entre x1.1 e x1.5
        
        # Para outros níveis de desgaste, os valores extremos podem ser mais valiosos
        elif float_value < 0.15:  # Minimal Wear
            # Float perto de Factory New (< 0.08) é mais valioso
            return base_price * (1 + max(0, (0.15 - float_value) * 2))
        elif float_value < 0.38:  # Field-Tested
            # Field-Tested com float baixo (perto de MW) é mais valioso
            # Field-Tested com float alto (perto de WW) é menos valioso
            mid_value = 0.265  # O meio do range FT
            distance = abs(float_value - mid_value) / (0.38 - 0.15) * 2  # Distância normalizada
            return base_price * (1 + (0.15 - float_value) * 0.5)  # Mais valor se mais perto de MW
        elif float_value < 0.45:  # Well-Worn
            # Geralmente WW tem menos variação de preço
            return base_price  # Valor padrão
        else:  # Battle-Scarred
            # BS com float muito alto (>0.95) pode ser mais valioso
            if float_value > 0.95:
                return base_price * (1 + (float_value - 0.95) * 10)  # Até 50% mais
            return base_price
    else:
        # Para itens comuns, o ajuste é mais sutil
        # Factory New com float baixo (< 0.01) é um pouco mais valioso
        if float_value < 0.01:
            return base_price * 1.2  # 20% mais valioso
        # Factory New com float normal
        elif float_value < 0.07:
            return base_price * (1 + (0.07 - float_value) * 1.5)  # Até 10% mais
        # Para outros, manter o preço base
        return base_price


def get_storage_unit_contents(unit_id: str, steamid: str, session_id: str, steam_token: str) -> Dict[str, Any]:
    """
    Obtém o conteúdo de uma unidade de armazenamento.
    Requer autenticação do usuário (session_id e steam_token).
    
    Args:
        unit_id: ID do asset da unidade de armazenamento
        steamid: ID da Steam do dono da unidade
        session_id: ID da sessão Steam do usuário autenticado
        steam_token: Token de autenticação Steam do usuário
        
        Returns:
        Dictionary with information about unit contents
    """
    try:
        print(f"Getting unit {unit_id} contents for user {steamid}")
        
        # URL for Steam Storage Units API
        storage_url = f"https://steamcommunity.com/inventory/{steamid}/730/2/storage/{unit_id}"
        
        # Headers required for authentication
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Cookie': f'sessionid={session_id}; steamLoginSecure={steam_token}'
        }
        
        # Fazer requisição para obter o conteúdo
        print(f"Fazendo requisição para {storage_url}")
        response = requests.get(
            storage_url,
            headers=headers,
            timeout=30  # Timeout aumentado para dar tempo suficiente
        )
        
        # Verificar se a requisição foi bem-sucedida
        if response.status_code == 200:
            unit_data = response.json()
            print(f"Conteúdo obtido com sucesso: {len(unit_data.get('assets', []))} itens encontrados")
            
            # Estrutura similar ao inventário normal
            result = {
                "unit_id": unit_id,
                "steamid": steamid,
                "total_items": 0,
                "total_value": 0.0,
                "items": []
            }
            
            # Processar os itens dentro da unidade
            if "assets" in unit_data and "descriptions" in unit_data:
                # Mapear descriptions para acesso rápido
                descriptions = {}
                for desc in unit_data["descriptions"]:
                    key = f"{desc.get('classid')}_{desc.get('instanceid')}"
                    descriptions[key] = desc
                
                # Processar cada item
                processed_items = []
                total_value = 0.0
                most_valuable_item = None
                highest_value = 0.0
                
                for asset in unit_data["assets"]:
                    asset_id = asset.get("assetid")
                    classid = asset.get("classid")
                    instanceid = asset.get("instanceid")
                    amount = int(asset.get("amount", 1))
                    
                    # Find item description
                    desc_key = f"{classid}_{instanceid}"
                    if desc_key in descriptions:
                        desc = descriptions[desc_key]
                        
                        # Extract relevant information
                        market_hash_name = desc.get("market_hash_name", "")
                        name = desc.get("name", "")
                        type_info = desc.get("type", "")
                        tradable = desc.get("tradable", 0) == 1
                        
                        # Verificar se é um adesivo
                        is_sticker = "Sticker" in name or "Adesivo" in name
                        
                        # Item especial (StatTrak, Souvenir)
                        is_special = "StatTrak™" in name or "Souvenir" in name
                        
                        # Extract inspection URL and get float value
                        inspect_url = extract_inspect_url(desc)
                        float_value = None
                        
                        # Só obter float para armas e facas
                        if inspect_url and not is_sticker:
                            # Verificar se é uma arma ou faca
                            has_float = any(cat in type_info.lower() for cat in [
                                "pistol", "rifle", "smg", "shotgun", "machinegun", 
                                "sniper rifle", "knife", "★"
                            ])
                            
                            if has_float:
                                float_value = get_item_float(inspect_url)
                                if float_value is not None:
                                    print(f"Float obtido para {market_hash_name}: {float_value:.10f}")
                        
                        # Obter preço do item
                        price = 0.0
                        if tradable:
                            try:
                                price_data = get_item_price(market_hash_name)
                                if isinstance(price_data, dict):
                                    price = price_data.get("price", 0.0)
                                else:
                                    price = float(price_data) if price_data else 0.0
                                    
                                # Ajustar preço com base no float (para itens que têm)
                                if float_value is not None:
                                    price = adjust_price_by_float(price, float_value, market_hash_name)
                            except Exception as e:
                                print(f"Error getting price for {market_hash_name}: {e}")
                        
                        item_total = price * amount
                        
                        # Extract category and type
                        category, item_type = parse_item_type(type_info, desc)
                        
                        # Verificar se o item tem tags que indicam qualidade/raridade 
                        tags = desc.get("tags", [])
                        rarity = next((tag.get("name", "") for tag in tags if tag.get("category") == "Rarity"), "Normal")
                        exterior = next((tag.get("name", "") for tag in tags if tag.get("category") == "Exterior"), "Not Painted")
                        
                        # Criar objeto item
                        item = {
                            "assetid": asset_id,
                            "name": name,
                            "market_hash_name": market_hash_name,
                            "quantity": amount,
                            "price": price,
                            "total": item_total,
                            "tradable": tradable,
                            "category": category,
                            "type": item_type,
                            "rarity": rarity,
                            "exterior": exterior,
                            "stattrak": "StatTrak™" in name,
                            "souvenir": "Souvenir" in name,
                            "is_sticker": is_sticker,
                            "image": get_item_image(desc),
                            "source": "storage_unit_content",  # Indicar que vem de dentro de uma unidade
                            "inspect_url": inspect_url,
                            "float_value": float_value
                        }
                        
                        # Adicionar à lista de itens
                        processed_items.append(item)
                        
                        # Atualizar item mais valioso
                        if price > highest_value:
                            highest_value = price
                            most_valuable_item = {
                                "name": name,
                                "market_hash_name": market_hash_name,
                                "price": price,
                                "rarity": rarity,
                                "category": category,
                                "float_value": float_value
                            }
                            print(f"Novo item mais valioso na unidade: {name} - R$ {price:.2f}" + 
                                  (f" (Float: {float_value:.10f})" if float_value is not None else ""))
                        
                        # Atualizar valor total
                        total_value += item_total
                
                # Atualizar resultados
                result["items"] = processed_items
                result["total_items"] = sum(item.get("quantity", 1) for item in processed_items)
                result["total_value"] = total_value
                result["most_valuable_item"] = most_valuable_item
                result["status"] = "success"
                
                print(f"Processados {len(processed_items)} itens da unidade {unit_id}, valor total: R$ {total_value:.2f}")
                
                return result
            else:
                print(f"Dados da unidade de armazenamento incompletos: assets={unit_data.get('assets') is not None}, descriptions={unit_data.get('descriptions') is not None}")
                return {
                    "unit_id": unit_id,
                    "steamid": steamid,
                    "total_items": 0,
                    "total_value": 0.0,
                    "items": [],
                    "status": "no_data",
                    "error": "Incomplete data returned by API"
                }
        else:
            print(f"Error accessing storage unit: code {response.status_code}")
            print(f"Response: {response.text[:200]}...")
            return {
                "unit_id": unit_id,
                "steamid": steamid,
                "total_items": 0,
                "total_value": 0.0,
                "items": [],
                "status": "error",
                "error": f"Error accessing unit: code {response.status_code}"
            }
            
    except Exception as e:
        print(f"Error getting unit {unit_id} contents: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return {
            "unit_id": unit_id,
            "steamid": steamid,
            "error": str(e),
            "status": "exception",
            "total_items": 0,
            "total_value": 0.0,
            "items": []
        }