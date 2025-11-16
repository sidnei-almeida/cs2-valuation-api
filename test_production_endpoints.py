"""
Script para testar os endpoints na API de produção no Render
"""
import requests
import json
from datetime import datetime

# URL base da API de produção
BASE_URL = "https://cs2-valuation-api.onrender.com"

def print_section(title):
    """Imprime um separador visual"""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)

def test_root_endpoint():
    """Testa o endpoint raiz"""
    print_section("TESTE: GET / (Root Endpoint)")
    
    try:
        response = requests.get(f"{BASE_URL}/", timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("\n✅ Resposta recebida:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print(f"❌ Erro: {response.text}")
            
    except requests.exceptions.Timeout:
        print("❌ Timeout: O servidor demorou muito para responder")
    except requests.exceptions.ConnectionError:
        print("❌ Erro de conexão: Não foi possível conectar ao servidor")
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")

def test_get_item_price():
    """Testa o endpoint GET /api/inventory/item-price"""
    print_section("TESTE: GET /api/inventory/item-price")
    
    test_cases = [
        {
            "name": "AK-47 Redline Field-Tested (Normal)",
            "params": {
                "market_hash_name": "AK-47 | Redline",
                "exterior": "Field-Tested",
                "stattrack": False,
                "currency": "USD"
            }
        },
        {
            "name": "AK-47 Redline Battle-Scarred (StatTrak)",
            "params": {
                "market_hash_name": "AK-47 | Redline",
                "exterior": "Battle-Scarred",
                "stattrack": True,
                "currency": "BRL"
            }
        },
        {
            "name": "AWP Dragon Lore Factory New (Normal)",
            "params": {
                "market_hash_name": "AWP | Dragon Lore",
                "exterior": "Factory New",
                "stattrack": False,
                "currency": "USD"
            }
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n--- Teste {i}: {test_case['name']} ---")
        print(f"Parâmetros: {test_case['params']}")
        
        try:
            response = requests.get(
                f"{BASE_URL}/api/inventory/item-price",
                params=test_case['params'],
                timeout=30
            )
            
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print("✅ Resposta recebida:")
                print(json.dumps(data, indent=2, ensure_ascii=False))
                
                # Mostrar resumo
                if 'price_usd' in data:
                    print(f"\n📊 Resumo:")
                    print(f"   Preço USD: ${data.get('price_usd', 0):.2f}")
                    if data.get('price_brl'):
                        print(f"   Preço BRL: R$ {data.get('price_brl', 0):.2f}")
                    print(f"   Fonte: {data.get('source', 'N/A')}")
                    
            elif response.status_code == 404:
                error_data = response.json()
                print(f"⚠️  Item não encontrado:")
                print(f"   {error_data.get('detail', 'N/A')}")
            else:
                print(f"❌ Erro: {response.status_code}")
                try:
                    error_data = response.json()
                    print(json.dumps(error_data, indent=2, ensure_ascii=False))
                except:
                    print(f"   {response.text}")
                    
        except requests.exceptions.Timeout:
            print("❌ Timeout: O servidor demorou muito para responder")
        except requests.exceptions.ConnectionError:
            print("❌ Erro de conexão: Não foi possível conectar ao servidor")
        except Exception as e:
            print(f"❌ Erro inesperado: {e}")
            import traceback
            traceback.print_exc()

def test_analyze_items():
    """Testa o endpoint POST /api/inventory/analyze-items"""
    print_section("TESTE: POST /api/inventory/analyze-items")
    
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
    
    print(f"Enviando {len(mock_items['items'])} itens para análise...")
    print(f"\nDados enviados:")
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
            print("\n✅ Resposta recebida:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            
            # Mostrar resumo
            print(f"\n📊 RESUMO DA ANÁLISE:")
            print(f"   Total de itens: {data.get('total_items', 0)}")
            print(f"   Valor total USD: ${data.get('total_value_usd', 0):.2f}")
            print(f"   Valor total BRL: R$ {data.get('total_value_brl', 0):.2f}")
            print(f"   Moeda: {data.get('currency', 'N/A')}")
            print(f"   Processado em: {data.get('processed_at', 'N/A')}")
            
            # Mostrar detalhes dos itens
            print(f"\n📦 DETALHES DOS ITENS:")
            for i, item in enumerate(data.get('items', []), 1):
                print(f"\n   Item {i}: {item.get('name', 'N/A')}")
                print(f"      - Market Hash Name: {item.get('market_hash_name', 'N/A')}")
                print(f"      - Exterior: {item.get('exterior', 'N/A')}")
                print(f"      - StatTrak: {item.get('stattrack', False)}")
                print(f"      - Quantidade: {item.get('quantity', 0)}")
                if 'error' in item:
                    print(f"      - ⚠️  Erro: {item.get('error')}")
                else:
                    print(f"      - Preço USD: ${item.get('price_usd', 0):.2f}")
                    print(f"      - Preço BRL: R$ {item.get('price_brl', 0):.2f}")
                    print(f"      - Total USD: ${item.get('total_usd', 0):.2f}")
                    print(f"      - Total BRL: R$ {item.get('total_brl', 0):.2f}")
                    
        elif response.status_code == 422:
            error_data = response.json()
            print(f"❌ Erro de validação:")
            print(json.dumps(error_data, indent=2, ensure_ascii=False))
        else:
            print(f"❌ Erro: {response.status_code}")
            try:
                error_data = response.json()
                print(json.dumps(error_data, indent=2, ensure_ascii=False))
            except:
                print(f"   {response.text}")
                
    except requests.exceptions.Timeout:
        print("❌ Timeout: O servidor demorou muito para responder")
    except requests.exceptions.ConnectionError:
        print("❌ Erro de conexão: Não foi possível conectar ao servidor")
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")
        import traceback
        traceback.print_exc()

def test_api_status():
    """Testa o endpoint GET /api/status"""
    print_section("TESTE: GET /api/status")
    
    try:
        response = requests.get(f"{BASE_URL}/api/status", timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("\n✅ Resposta recebida:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print(f"❌ Erro: {response.text}")
            
    except Exception as e:
        print(f"❌ Erro: {e}")

def main():
    """Função principal"""
    print("\n" + "="*70)
    print("  TESTES DOS ENDPOINTS NA API DE PRODUÇÃO (RENDER)")
    print("="*70)
    print(f"\nURL Base: {BASE_URL}")
    print(f"Data/Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\nIniciando testes...")
    
    # Testar endpoints
    test_root_endpoint()
    test_api_status()
    test_get_item_price()
    test_analyze_items()
    
    print("\n" + "="*70)
    print("  TESTES CONCLUÍDOS")
    print("="*70)

if __name__ == "__main__":
    main()

