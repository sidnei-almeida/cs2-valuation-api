"""
Script para testar os dados mockados e a lógica dos endpoints
sem precisar do servidor rodando
"""
import json
from datetime import datetime
from services.inventory_pricer import get_specific_price, analyze_inventory_items
import asyncio

# Taxa de câmbio para teste
EXCHANGE_RATE_USD_TO_BRL = 5.00
STEAM_TAX = 0.15


async def test_get_specific_price():
    """Testa a função get_specific_price com dados mockados"""
    print("\n" + "="*60)
    print("TESTE: get_specific_price()")
    print("="*60)
    
    test_cases = [
        {
            "market_hash_name": "AK-47 | Redline",
            "exterior": "Field-Tested",
            "stattrack": False
        },
        {
            "market_hash_name": "AK-47 | Redline",
            "exterior": "Battle-Scarred",
            "stattrack": True
        },
        {
            "market_hash_name": "AWP | Dragon Lore",
            "exterior": "Factory New",
            "stattrack": False
        },
        {
            "market_hash_name": "M4A4 | Howl",
            "exterior": "Minimal Wear",
            "stattrack": True
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n--- Teste {i} ---")
        print(f"Parâmetros: {test_case}")
        
        try:
            price_usd = await get_specific_price(
                test_case["market_hash_name"],
                test_case["exterior"],
                test_case["stattrack"]
            )
            
            if price_usd:
                price_brl = price_usd * EXCHANGE_RATE_USD_TO_BRL * (1 + STEAM_TAX)
                print(f"✅ Preço encontrado:")
                print(f"   USD: ${price_usd:.2f}")
                print(f"   BRL: R$ {price_brl:.2f}")
            else:
                print(f"❌ Preço não encontrado")
                
        except Exception as e:
            print(f"❌ Erro: {e}")
            import traceback
            traceback.print_exc()


async def test_analyze_items():
    """Testa a função analyze_inventory_items com dados mockados"""
    print("\n" + "="*60)
    print("TESTE: analyze_inventory_items()")
    print("="*60)
    
    # Dados mockados de inventário
    mock_items = [
        {
            "name": "AK-47 | Redline (Field-Tested)",
            "market_hash_name": "AK-47 | Redline",
            "exterior": "Field-Tested",
            "stattrack": False,
            "quantity": 1,
            "icon_url": "https://steamcommunity-a.akamaihd.net/economy/image/-9a81dlWLwJ2UUGcVs_nsVtzdOEdtWwKGZZLQHTxDZ7I56KU0Zwwo4NUX4oFJZEHLbXH5ApeO4YmlhxYQknCRvCo04DEVlxkKgpot7HxfDhjxszJemkV09-5gZKKkuXLPr7Vn35cppwl3r3E9t2s3gHgqkE4Z2-mJ4fDc1M3Y1rV-lC_x-7s1sO5tJ7Nv3Rjz3Mh5CvDlQ",
            "assetid": "1234567890",
            "rarity": "Classified",
            "category": "Rifle"
        },
        {
            "name": "AWP | Dragon Lore (Factory New)",
            "market_hash_name": "AWP | Dragon Lore",
            "exterior": "Factory New",
            "stattrack": True,
            "quantity": 1,
            "icon_url": "https://steamcommunity-a.akamaihd.net/economy/image/-9a81dlWLwJ2UUGcVs_nsVtzdOEdtWwKGZZLQHTxDZ7I56KU0Zwwo4NUX4oFJZEHLbXH5ApeO4YmlhxYQknCRvCo04DEVlxkKgpot7HxfDhjxszJemkV09-5gZKKkuXLPr7Vn35cppwl3r3E9t2s3gHgqkE4Z2-mJ4fDc1M3Y1rV-lC_x-7s1sO5tJ7Nv3Rjz3Mh5CvDlQ",
            "assetid": "0987654321",
            "rarity": "Covert",
            "category": "Sniper Rifle"
        },
        {
            "name": "M4A4 | Howl (Minimal Wear)",
            "market_hash_name": "M4A4 | Howl",
            "exterior": "Minimal Wear",
            "stattrack": False,
            "quantity": 2,
            "icon_url": "https://steamcommunity-a.akamaihd.net/economy/image/-9a81dlWLwJ2UUGcVs_nsVtzdOEdtWwKGZZLQHTxDZ7I56KU0Zwwo4NUX4oFJZEHLbXH5ApeO4YmlhxYQknCRvCo04DEVlxkKgpot7HxfDhjxszJemkV09-5gZKKkuXLPr7Vn35cppwl3r3E9t2s3gHgqkE4Z2-mJ4fDc1M3Y1rV-lC_x-7s1sO5tJ7Nv3Rjz3Mh5CvDlQ",
            "assetid": "1122334455",
            "rarity": "Covert",
            "category": "Rifle"
        }
    ]
    
    print(f"\nAnalisando {len(mock_items)} itens...")
    
    try:
        result = await analyze_inventory_items(mock_items, "BRL")
        
        print(f"\n✅ Análise concluída!")
        print(f"\n--- RESUMO ---")
        print(f"Total de itens: {result.get('total_items', 0)}")
        print(f"Valor total USD: ${result.get('total_value_usd', 0):.2f}")
        print(f"Valor total BRL: R$ {result.get('total_value_brl', 0):.2f}")
        print(f"Moeda: {result.get('currency', 'N/A')}")
        print(f"Processado em: {result.get('processed_at', 'N/A')}")
        
        print(f"\n--- DETALHES DOS ITENS ---")
        for i, item in enumerate(result.get('items', []), 1):
            print(f"\nItem {i}: {item.get('name', 'N/A')}")
            print(f"  - Market Hash Name: {item.get('market_hash_name', 'N/A')}")
            print(f"  - Exterior: {item.get('exterior', 'N/A')}")
            print(f"  - StatTrak: {item.get('stattrack', False)}")
            print(f"  - Quantidade: {item.get('quantity', 0)}")
            print(f"  - Preço USD: ${item.get('price_usd', 0):.2f}")
            print(f"  - Preço BRL: R$ {item.get('price_brl', 0):.2f}")
            print(f"  - Total USD: ${item.get('total_usd', 0):.2f}")
            print(f"  - Total BRL: R$ {item.get('total_brl', 0):.2f}")
            if 'error' in item:
                print(f"  - ⚠️ Erro: {item.get('error')}")
        
        print(f"\n--- JSON COMPLETO ---")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Função principal para executar todos os testes"""
    print("\n" + "="*60)
    print("TESTES COM DADOS MOCKADOS - API CS2 VALUATION")
    print("="*60)
    print("\nEstes testes usam dados mockados para validar a lógica")
    print("dos endpoints sem precisar do servidor rodando.\n")
    
    await test_get_specific_price()
    await test_analyze_items()
    
    print("\n" + "="*60)
    print("TESTES CONCLUÍDOS")
    print("="*60)
    print("\nPara testar os endpoints HTTP, você precisa:")
    print("1. Instalar as dependências: pip install -r requirements.txt")
    print("2. Rodar o servidor: uvicorn main:app --reload")
    print("3. Usar o script test_endpoints.py ou curl para testar")


if __name__ == "__main__":
    asyncio.run(main())

