"""
Demonstração dos dados mockados e estrutura de resposta dos endpoints
"""
import json
from datetime import datetime

# Dados mockados de preços
MOCK_PRICES = {
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

EXCHANGE_RATE_USD_TO_BRL = 5.00
STEAM_TAX = 0.15

# Mapeamento de exterior
EXTERIOR_MAP = {
    "Factory New": "factory_new",
    "Minimal Wear": "minimal_wear",
    "Field-Tested": "field_tested",
    "Well-Worn": "well_worn",
    "Battle-Scarred": "battle_scarred"
}


def get_mock_price(market_hash_name, exterior, stattrack=False):
    """Simula a busca de preço específico"""
    exterior_key = None
    for ext_name, ext_key in EXTERIOR_MAP.items():
        if ext_name.lower() in exterior.lower() or exterior.lower() in ext_name.lower():
            exterior_key = ext_key
            break
    
    if not exterior_key:
        return None
    
    item_prices = MOCK_PRICES.get(market_hash_name, {})
    price_type = "stattrak" if stattrack else "normal"
    price_dict = item_prices.get(price_type, {})
    
    return price_dict.get(exterior_key)


def simulate_get_item_price_endpoint(market_hash_name, exterior, stattrack=False, currency="USD"):
    """Simula a resposta do endpoint GET /api/inventory/item-price"""
    price_usd = get_mock_price(market_hash_name, exterior, stattrack)
    
    if price_usd is None:
        return {
            "error": f"Preço não encontrado para {market_hash_name} ({exterior})"
        }
    
    price_brl = None
    if currency == "BRL":
        price_brl = price_usd * EXCHANGE_RATE_USD_TO_BRL * (1 + STEAM_TAX)
    
    return {
        "market_hash_name": market_hash_name,
        "exterior": exterior,
        "stattrack": stattrack,
        "price_usd": price_usd,
        "price_brl": price_brl,
        "currency": currency,
        "source": "Steam Market (Mock Data)",
        "last_updated": datetime.now().isoformat()
    }


def simulate_analyze_items_endpoint(items, currency="BRL"):
    """Simula a resposta do endpoint POST /api/inventory/analyze-items"""
    results = []
    total_usd = 0.0
    
    for item in items:
        price_usd = get_mock_price(
            item.get('market_hash_name', ''),
            item.get('exterior', ''),
            item.get('stattrack', False)
        )
        
        if price_usd:
            item_total_usd = price_usd * item.get('quantity', 1)
            total_usd += item_total_usd
            
            price_brl = None
            total_brl = None
            if currency == "BRL":
                price_brl = price_usd * EXCHANGE_RATE_USD_TO_BRL * (1 + STEAM_TAX)
                total_brl = price_brl * item.get('quantity', 1)
            
            results.append({
                **item,
                'price_usd': price_usd,
                'price_brl': price_brl,
                'total_usd': item_total_usd,
                'total_brl': total_brl,
                'source': 'Steam Market (Mock Data)',
                'last_updated': datetime.now().isoformat()
            })
        else:
            results.append({
                **item,
                'price_usd': 0.0,
                'price_brl': 0.0,
                'total_usd': 0.0,
                'total_brl': 0.0,
                'error': 'Price not found'
            })
    
    total_brl = total_usd * EXCHANGE_RATE_USD_TO_BRL * (1 + STEAM_TAX) if currency == "BRL" else None
    
    return {
        'total_items': len(results),
        'total_value_usd': total_usd,
        'total_value_brl': total_brl,
        'items': results,
        'currency': currency,
        'processed_at': datetime.now().isoformat()
    }


def main():
    print("\n" + "="*60)
    print("DEMONSTRAÇÃO DOS ENDPOINTS COM DADOS MOCKADOS")
    print("="*60)
    
    # Teste 1: GET /api/inventory/item-price
    print("\n" + "="*60)
    print("TESTE 1: GET /api/inventory/item-price")
    print("="*60)
    
    test_cases = [
        {
            "market_hash_name": "AK-47 | Redline",
            "exterior": "Field-Tested",
            "stattrack": False,
            "currency": "USD"
        },
        {
            "market_hash_name": "AK-47 | Redline",
            "exterior": "Battle-Scarred",
            "stattrack": True,
            "currency": "BRL"
        },
        {
            "market_hash_name": "AWP | Dragon Lore",
            "exterior": "Factory New",
            "stattrack": False,
            "currency": "USD"
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n--- Teste {i} ---")
        print(f"Parâmetros: {test_case}")
        result = simulate_get_item_price_endpoint(**test_case)
        print(f"Resposta:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    # Teste 2: POST /api/inventory/analyze-items
    print("\n" + "="*60)
    print("TESTE 2: POST /api/inventory/analyze-items")
    print("="*60)
    
    mock_items = [
        {
            "name": "AK-47 | Redline (Field-Tested)",
            "market_hash_name": "AK-47 | Redline",
            "exterior": "Field-Tested",
            "stattrack": False,
            "quantity": 1,
            "rarity": "Classified",
            "category": "Rifle"
        },
        {
            "name": "AWP | Dragon Lore (Factory New)",
            "market_hash_name": "AWP | Dragon Lore",
            "exterior": "Factory New",
            "stattrack": True,
            "quantity": 1,
            "rarity": "Covert",
            "category": "Sniper Rifle"
        },
        {
            "name": "M4A4 | Howl (Minimal Wear)",
            "market_hash_name": "M4A4 | Howl",
            "exterior": "Minimal Wear",
            "stattrack": False,
            "quantity": 2,
            "rarity": "Covert",
            "category": "Rifle"
        }
    ]
    
    print(f"\nEnviando {len(mock_items)} itens para análise...")
    result = simulate_analyze_items_endpoint(mock_items, "BRL")
    
    print(f"\n--- RESUMO ---")
    print(f"Total de itens: {result.get('total_items', 0)}")
    print(f"Valor total USD: ${result.get('total_value_usd', 0):.2f}")
    print(f"Valor total BRL: R$ {result.get('total_value_brl', 0):.2f}")
    
    print(f"\n--- DETALHES ---")
    for i, item in enumerate(result.get('items', []), 1):
        print(f"\nItem {i}: {item.get('name', 'N/A')}")
        print(f"  Preço USD: ${item.get('price_usd', 0):.2f}")
        print(f"  Preço BRL: R$ {item.get('price_brl', 0):.2f}")
        print(f"  Total USD: ${item.get('total_usd', 0):.2f}")
        print(f"  Total BRL: R$ {item.get('total_brl', 0):.2f}")
    
    print(f"\n--- JSON COMPLETO ---")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    print("\n" + "="*60)
    print("DEMONSTRAÇÃO CONCLUÍDA")
    print("="*60)
    print("\nPara testar os endpoints HTTP reais:")
    print("1. Instale as dependências: pip install -r requirements.txt")
    print("2. Execute: uvicorn main:app --reload")
    print("3. Teste com curl ou o script test_endpoints.py")


if __name__ == "__main__":
    main()

