import requests
from selectolax.parser import HTMLParser
import urllib.parse
from typing import Optional, List, Dict, Union
from datetime import datetime
import time
import re
import asyncio
from services.steam_market import get_item_detailed_data_via_csgostash, sleep_between_requests

# Taxa de câmbio USD para BRL (pode ser atualizada dinamicamente)
EXCHANGE_RATE_USD_TO_BRL = 5.00  # Atualizar dinamicamente se necessário
STEAM_TAX = 0.15  # 15% de taxa da Steam


def _get_mock_data(market_hash_name: str) -> Dict:
    """
    Retorna dados mockados para teste quando o scraping falha.
    """
    # Preços mockados baseados em itens populares
    mock_prices = {
        "AK-47 | Redline": {
            "normal": {
                "factory_new": 45.50,
                "minimal_wear": 38.20,
                "field_tested": 32.10,
                "well_worn": 28.50,
                "battle_scarred": 25.00
            },
            "stattrak": {
                "factory_new": 91.00,
                "minimal_wear": 76.40,
                "field_tested": 64.20,
                "well_worn": 57.00,
                "battle_scarred": 50.00
            }
        },
        "AWP | Dragon Lore": {
            "normal": {
                "factory_new": 12500.00,
                "minimal_wear": 9800.00,
                "field_tested": 7500.00,
                "well_worn": 6200.00,
                "battle_scarred": 5000.00
            },
            "stattrak": {
                "factory_new": 25000.00,
                "minimal_wear": 19600.00,
                "field_tested": 15000.00,
                "well_worn": 12400.00,
                "battle_scarred": 10000.00
            }
        },
        "M4A4 | Howl": {
            "normal": {
                "factory_new": 3200.00,
                "minimal_wear": 2800.00,
                "field_tested": 2400.00,
                "well_worn": 2100.00,
                "battle_scarred": 1800.00
            },
            "stattrak": {
                "factory_new": 6400.00,
                "minimal_wear": 5600.00,
                "field_tested": 4800.00,
                "well_worn": 4200.00,
                "battle_scarred": 3600.00
            }
        }
    }
    
    # Buscar preços mockados ou usar valores padrão
    item_prices = mock_prices.get(market_hash_name, {
        "normal": {
            "factory_new": 100.00,
            "minimal_wear": 85.00,
            "field_tested": 70.00,
            "well_worn": 60.00,
            "battle_scarred": 50.00
        },
        "stattrak": {
            "factory_new": 200.00,
            "minimal_wear": 170.00,
            "field_tested": 140.00,
            "well_worn": 120.00,
            "battle_scarred": 100.00
        }
    })
    
    return {
        "market_hash_name": market_hash_name,
        "prices": item_prices,
        "currency": "USD",
        "source": "mock_data",
        "timestamp": datetime.now().isoformat()
    }


async def get_specific_price(
    market_hash_name: str,
    exterior: str,
    stattrack: bool = False,
    include_image: bool = False
) -> Union[Optional[float], Dict]:
    """
    Busca preço específico de uma skin no Steam Market considerando wear e StatTrak.
    Usa o serviço existente de scraping do CSGOSkins.gg que já extrai preços por wear.
    
    Args:
        market_hash_name: Nome base da skin (ex: "AK-47 | Redline")
        exterior: Condição do item (ex: "Battle-Scarred", "Field-Tested", etc.)
        stattrack: Se é StatTrak (True) ou Normal (False)
        include_image: Se True, retorna dict com price e icon_url. Se False, retorna apenas float.
    
    Returns:
        float: Preço em USD, ou None se não encontrar (quando include_image=False)
        dict: {"price": float, "icon_url": str} quando include_image=True
    """
    try:
        # Mapeamento de nomes de exterior para chaves internas
        exterior_map = {
            "Factory New": "factory_new",
            "Minimal Wear": "minimal_wear",
            "Field-Tested": "field_tested",
            "Well-Worn": "well_worn",
            "Battle-Scarred": "battle_scarred"
        }
        
        # Normalizar o nome do exterior
        exterior_key = None
        for ext_name, ext_key in exterior_map.items():
            if ext_name.lower() in exterior.lower() or exterior.lower() in ext_name.lower():
                exterior_key = ext_key
                break
        
        if not exterior_key:
            print(f"Exterior '{exterior}' não reconhecido")
            return None
        
        # Usar o scraping real do CSGOSkins.gg
        print(f"Buscando preço específico para {market_hash_name} ({exterior}, StatTrak={stattrack})")
        
        # Executar scraping síncrono em thread separada para não bloquear o event loop
        detailed_data = await asyncio.to_thread(
            get_item_detailed_data_via_csgostash, 
            market_hash_name
        )
        
        if not detailed_data or not detailed_data.get("prices"):
            print(f"Não foi possível obter dados para {market_hash_name}")
            return None
        
        # Extrair preço específico baseado em wear e StatTrak
        prices = detailed_data.get("prices", {})
        
        if stattrack:
            price_dict = prices.get("stattrak", {})
        else:
            price_dict = prices.get("normal", {})
        
        # Buscar preço para o exterior específico
        # Se a chave existe no dict mas o valor é None, significa "Not possible"
        # Se a chave não existe, significa que não foi encontrado
        price = None
        is_not_possible = False
        
        # Verificar se a chave existe no dict (mesmo que seja None)
        if exterior_key in price_dict:
            price = price_dict[exterior_key]
            # Se a chave existe mas o valor é None, foi marcado como "Not possible" no scraping
            if price is None:
                is_not_possible = True
                print(f"Skin marcada como 'Not possible' para {market_hash_name} ({exterior}, StatTrak={stattrack})")
        else:
            # Chave não existe - verificar se temos outros preços disponíveis para confirmar que é erro
            # Se temos outros preços mas não este, pode ser "Not possible" também
            has_any_price = any(p is not None and isinstance(p, (int, float)) and p > 0 
                              for p in price_dict.values())
            if has_any_price:
                # Temos outros preços, então este provavelmente é "Not possible"
                is_not_possible = True
                print(f"Skin provavelmente 'Not possible' para {market_hash_name} ({exterior}, StatTrak={stattrack}) - outros wears disponíveis")
            else:
                print(f"Preço não encontrado para {market_hash_name} ({exterior}, StatTrak={stattrack})")
        
        if price is None:
            # Se include_image=True, retornar dict indicando "not_possible" ou erro
            if include_image:
                if is_not_possible:
                    return {
                        "price": None,
                        "icon_url": detailed_data.get("image_url"),
                        "not_possible": True,
                        "message": f"Esta skin não existe em {exterior} {'StatTrak' if stattrack else 'Normal'}"
                    }
                else:
                    # Erro real - não encontrado
                    return None
            
            return None
        
        print(f"Preço encontrado: ${price:.2f} USD para {market_hash_name} ({exterior}, StatTrak={stattrack})")
        
        # Se include_image=True, retornar dict com price e icon_url
        if include_image:
            return {
                "price": float(price),
                "icon_url": detailed_data.get("image_url"),
                "not_possible": False
            }
        
        return float(price)
        
    except Exception as e:
        print(f"Erro ao buscar preço específico: {e}")
        import traceback
        traceback.print_exc()
        return None


async def analyze_inventory_items(items: List[dict]) -> Dict:
    """
    Analisa lista de itens e retorna preços específicos em USD.
    A conversão para outras moedas deve ser feita no frontend.
    
    Args:
        items: Lista de dicionários com informações dos itens
    
    Returns:
        dict: Resultado da análise com preços em USD
    """
    results = []
    total_usd = 0.0
    
    for item in items:
        # Buscar preço com imagem
        price_data = await get_specific_price(
            item.get('market_hash_name', ''),
            item.get('exterior', ''),
            item.get('stattrack', False),
            include_image=True
        )
        
        # Extrair preço e icon_url
        if isinstance(price_data, dict):
            price_usd = price_data.get('price')
            icon_url = price_data.get('icon_url')
        else:
            price_usd = price_data
            icon_url = None
        
        if price_usd:
            # Calcular total considerando quantidade
            item_total_usd = price_usd * item.get('quantity', 1)
            total_usd += item_total_usd
            
            result_item = {
                **item,
                'price_usd': price_usd,
                'total_usd': item_total_usd,
                'source': 'Steam Market',
                'last_updated': datetime.now().isoformat()
            }
            
            # Adicionar icon_url se disponível
            if icon_url:
                result_item['icon_url'] = icon_url
            elif item.get('icon_url'):
                result_item['icon_url'] = item.get('icon_url')
            
            results.append(result_item)
        else:
            # Item sem preço encontrado
            results.append({
                **item,
                'price_usd': 0.0,
                'total_usd': 0.0,
                'error': 'Price not found'
            })
    
    return {
        'total_items': len(results),
        'total_value_usd': total_usd,
        'items': results,
        'currency': 'USD',
        'processed_at': datetime.now().isoformat()
    }

