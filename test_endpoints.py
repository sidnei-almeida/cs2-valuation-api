"""
Script para testar os novos endpoints com dados mockados
"""
import requests
import json
from datetime import datetime

# URL base da API (ajustar se necessário)
BASE_URL = "http://localhost:8000"

def test_get_item_price():
    """Testa o endpoint GET /api/inventory/item-price"""
    print("\n" + "="*60)
    print("TESTE 1: GET /api/inventory/item-price")
    print("="*60)
    
    # Dados de teste
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
        
        try:
            response = requests.get(
                f"{BASE_URL}/api/inventory/item-price",
                params=test_case,
                timeout=30
            )
            
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"Resposta:")
                print(json.dumps(data, indent=2, ensure_ascii=False))
            else:
                print(f"Erro: {response.text}")
                
        except requests.exceptions.ConnectionError:
            print("ERRO: Não foi possível conectar ao servidor. Certifique-se de que o uvicorn está rodando.")
        except Exception as e:
            print(f"ERRO: {e}")


def test_analyze_items():
    """Testa o endpoint POST /api/inventory/analyze-items"""
    print("\n" + "="*60)
    print("TESTE 2: POST /api/inventory/analyze-items")
    print("="*60)
    
    # Dados mockados de inventário
    mock_items = {
        "items": [
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
        ],
        "currency": "BRL"
    }
    
    print(f"\nEnviando {len(mock_items['items'])} itens para análise...")
    print(f"Dados enviados:")
    print(json.dumps(mock_items, indent=2, ensure_ascii=False))
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/inventory/analyze-items",
            json=mock_items,
            headers={"Content-Type": "application/json"},
            timeout=60  # Timeout maior para processar múltiplos itens
        )
        
        print(f"\nStatus Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\nResposta:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            
            # Resumo
            print(f"\n--- RESUMO ---")
            print(f"Total de itens: {data.get('total_items', 0)}")
            print(f"Valor total USD: ${data.get('total_value_usd', 0):.2f}")
            print(f"Valor total BRL: R$ {data.get('total_value_brl', 0):.2f}")
        else:
            print(f"Erro: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("ERRO: Não foi possível conectar ao servidor. Certifique-se de que o uvicorn está rodando.")
    except Exception as e:
        print(f"ERRO: {e}")


def test_root_endpoint():
    """Testa o endpoint raiz"""
    print("\n" + "="*60)
    print("TESTE 0: GET / (Root)")
    print("="*60)
    
    try:
        response = requests.get(f"{BASE_URL}/", timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Resposta:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print(f"Erro: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("ERRO: Não foi possível conectar ao servidor. Certifique-se de que o uvicorn está rodando.")
    except Exception as e:
        print(f"ERRO: {e}")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("TESTES DOS ENDPOINTS DA API CS2 VALUATION")
    print("="*60)
    print(f"\nURL Base: {BASE_URL}")
    print("Certifique-se de que o servidor está rodando com: uvicorn main:app --reload")
    print("\nPressione Enter para começar os testes...")
    input()
    
    # Testar endpoint raiz primeiro
    test_root_endpoint()
    
    # Testar endpoints principais
    test_get_item_price()
    test_analyze_items()
    
    print("\n" + "="*60)
    print("TESTES CONCLUÍDOS")
    print("="*60)

