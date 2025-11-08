import requests
import json
import time
import random
import datetime
import re
from typing import Dict, List, Any, Optional
from cachetools import TTLCache
import os
from dotenv import load_dotenv
from selectolax.parser import HTMLParser
from utils.config import (
    STEAM_API_KEY, STEAM_MARKET_CURRENCY, STEAM_APPID, 
    STEAM_REQUEST_DELAY, STEAM_MAX_RETRIES, STEAM_MAX_DELAY,
    STEAM_DAILY_LIMIT
)
from utils.scraper import process_scraped_price
from utils.database import get_skin_price, save_skin_price, update_last_scrape_time

# Carrega as variáveis de ambiente (se existir um arquivo .env)
load_dotenv()

# URLs da Steam
STEAM_API_URL = "https://api.steampowered.com"
STEAM_MARKET_BASE_URL = "https://steamcommunity.com/market/listings"

# Cache para armazenar preços temporariamente (4 horas de TTL para dados de scraping)
price_cache = TTLCache(maxsize=1000, ttl=14400)  # 4 horas

# Último timestamp em que uma requisição foi feita
last_request_time = 0

# Mapeamento de códigos de moeda para símbolos
CURRENCY_SYMBOLS = {
    1: "$",      # USD
    3: "€",      # EUR
    5: "¥",      # JPY
    7: "R$",     # BRL
    9: "₽",      # RUB
}

# Mapeamento de códigos de qualidade para representação textual
QUALITY_NAMES = {
    "FN": "Factory New",
    "MW": "Minimal Wear",
    "FT": "Field-Tested",
    "WW": "Well-Worn",
    "BS": "Battle-Scarred"
}


def sleep_between_requests(min_delay=STEAM_REQUEST_DELAY):
    """
    Aguarda um tempo suficiente entre requisições para evitar bloqueios.
    Usa um delay mais curto para scraping do que para a API oficial.
    
    Args:
        min_delay: Tempo mínimo a aguardar em segundos
    """
    global last_request_time
    
    current_time = time.time()
    elapsed = current_time - last_request_time
    
    # If time since last request is less than minimum delay
    if elapsed < min_delay:
        # Increase delay to avoid 429 error (Too Many Requests)
        sleep_time = min(min_delay - elapsed + random.uniform(1.0, 3.0), 5.0)
        
        if sleep_time > 0:
            time.sleep(sleep_time)
    else:
        # Adicionar um pequeno delay mesmo se já passou tempo suficiente
        time.sleep(random.uniform(0.5, 2.0))
    
    # Atualizar o último timestamp
    last_request_time = time.time()


def convert_currency(price: float, from_currency: str, to_currency: str = 'BRL') -> float:
    """
    DESATIVADA: Esta função foi desativada para evitar dupla conversão.
    Todos os preços agora são retornados na moeda original (USD) e a conversão é feita apenas no frontend.
    
    Args:
        price: Preço a ser convertido
        from_currency: Moeda de origem ('USD', 'EUR', etc.)
        to_currency: Moeda de destino (padrão: 'BRL')
        
    Returns:
        Preço sem conversão (original)
    """
    # Sempre retornar o preço original sem conversão
    print(f"AVISO: Tentativa de conversão de moeda no backend ({from_currency} para {to_currency}) foi desativada.")
    print(f"A conversão de moeda agora é feita apenas no frontend.")
    return price


def extract_price_from_text(price_text: str, currency_code: int = STEAM_MARKET_CURRENCY) -> Optional[Dict]:
    """
    Extrai o valor numérico de um texto de preço sem aplicar limites ou ajustes.
    
    Args:
        price_text: Texto contendo o preço (ex: "R$ 10,25", "$5.99")
        currency_code: Código da moeda para formatação correta
        
    Returns:
        Dicionário contendo o preço e a moeda original, ou None se não for possível extrair
    """
    if not price_text:
        return None
    
    # Limpar o texto de preço
    price_text = price_text.strip()
    
    try:
        # Detectar a moeda do texto
        original_currency = 'USD'  # Padrão alterado para USD
        
        # Verificação de moeda baseada no símbolo
        if 'R$' in price_text:
            original_currency = 'BRL'
        elif '€' in price_text:
            original_currency = 'EUR'
        elif '£' in price_text:
            original_currency = 'GBP'    
            
        # Armazenar o símbolo para log
        currency_symbol = {'BRL': 'R$', 'USD': '$', 'EUR': '€', 'GBP': '£'}.get(original_currency, '')
        
        # Remover todos os caracteres não-numéricos, exceto ponto e vírgula
        cleaned_text = re.sub(r'[^\d.,]', '', price_text)
        
        # CORREÇÃO: Verificar se há várias ocorrências de separadores (o que pode indicar erro)
        if cleaned_text.count('.') > 1 or cleaned_text.count(',') > 1:
            # Se houver múltiplos separadores, tente pegar apenas o primeiro número
            match = re.search(r'(\d+[.,]?\d*)', cleaned_text)
            if match:
                cleaned_text = match.group(1)
            else:
                return None
        
        # Formatação baseada na moeda detectada
        if original_currency in ['BRL', 'EUR']:
            # Usar vírgula como separador decimal (ex: R$, €)
            cleaned_text = cleaned_text.replace('.', '').replace(',', '.')
        else:
            # Usar ponto como separador decimal (ex: $)
            cleaned_text = cleaned_text.replace(',', '')
        
        # Converter para float
        price = float(cleaned_text)
        
        # Retornar preço e moeda sem validações ou ajustes
        return {
            "price": price,
            "currency": original_currency
        }
    except (ValueError, AttributeError):
        print(f"Error extracting price from text: '{price_text}'")
        return None


def get_item_price_via_scraping(market_hash_name: str, appid: int = STEAM_APPID, currency: int = STEAM_MARKET_CURRENCY) -> Optional[Dict]:
    """
    Obtém o preço de um item através de scraping da página do mercado da Steam.
    Usa a busca geral do mercado Steam sem especificar o AppID.
    
    Args:
        market_hash_name: Nome do item formatado para o mercado
        appid: ID da aplicação na Steam (não utilizado nesta versão)
        currency: Código da moeda (1 = USD)
        
    Returns:
        Dicionário com preço e moeda do item, ou None se falhar
    """
    # URL codificada para o item - VERSÃO SEM APPID
    encoded_name = requests.utils.quote(market_hash_name)
    # Usar a URL sem AppID
    url = f"https://steamcommunity.com/market/listings/{encoded_name}"
    
    # Adicionar parâmetro de moeda
    url += f"?currency={currency}"
    
    print(f"DEBUGGING: Obtendo preço para '{market_hash_name}'")
    print(f"DEBUGGING: URL de consulta sem AppID: {url}")

    # Wait time between requests
    sleep_between_requests()
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',  # Definir inglês para padronizar formato
        'Cache-Control': 'no-cache',
        'Referer': 'https://steamcommunity.com/market'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)  # Aumento do timeout para 30s
        
        if response.status_code == 200:
            # Log do HTML para debugging (primeiros 500 caracteres)
            html_preview = response.text[:500].replace("\n", " ")
            print(f"DEBUGGING: Preview do HTML: {html_preview}...")
            
            # Processar HTML com selectolax
            parser = HTMLParser(response.text)
            
            # Armazenar todos os preços encontrados para análise
            all_prices = []
            
            # 1. Buscar no elemento específico que mostra o preço mais baixo
            price_element = parser.css_first("span.market_listing_price_with_fee")
            if price_element:
                price_text = price_element.text().strip()
                print(f"DEBUGGING: Texto do elemento de preço principal: '{price_text}'")
                # Verificar se contém o formato de preço correto (símbolo de moeda)
                if any(symbol in price_text for symbol in ['R$', '$', '€', '¥', '£', 'kr', 'zł', '₽']):
                    price_data = extract_price_from_text(price_text, currency)
                    if price_data and price_data["price"] > 0:
                        all_prices.append((price_data, f"Preço principal: {price_text}"))
                        print(f"DEBUGGING: Preço principal encontrado: {price_data['price']} {price_data['currency']} ({price_text})")
            
            # 2. Buscar no histograma de vendas recentes
            histogram_element = parser.css_first("div.market_listing_price_listings_block")
            if histogram_element:
                price_spans = histogram_element.css("span.market_listing_price")
                for span in price_spans:
                    price_text = span.text().strip()
                    print(f"DEBUGGING: Texto do histograma: '{price_text}'")
                    # Verificar se é um preço real (contém símbolo de moeda)
                    if any(symbol in price_text for symbol in ['R$', '$', '€', '¥', '£', 'kr', 'zł', '₽']):
                        price_data = extract_price_from_text(price_text, currency)
                        if price_data and price_data["price"] > 0:
                            all_prices.append((price_data, f"Histograma: {price_text}"))
                            print(f"DEBUGGING: Preço do histograma: {price_data['price']} {price_data['currency']} ({price_text})")
            
            # 3. Buscar nos dados JavaScript da página
            script_tags = parser.css("script")
            price_patterns_found = False
            
            for script in script_tags:
                script_text = script.text()
                
                # Procurar padrões diferentes de preço no JavaScript
                price_patterns = [
                    r'"lowest_price":"([^"]+)"',
                    r'"median_price":"([^"]+)"',
                    r'"sale_price_text":"([^"]+)"'
                ]
                
                for pattern in price_patterns:
                    price_match = re.search(pattern, script_text)
                    if price_match:
                        price_patterns_found = True
                        price_text = price_match.group(1)
                        print(f"DEBUGGING: Texto de preço encontrado em JavaScript: '{price_text}'")
                        # Verificar se é um preço real (contém símbolo de moeda)
                        if any(symbol in price_text for symbol in ['R$', '$', '€', '¥', '£', 'kr', 'zł', '₽']):
                            price_data = extract_price_from_text(price_text, currency)
                            if price_data and price_data["price"] > 0:
                                all_prices.append((price_data, f"JavaScript: {price_text}"))
                                print(f"DEBUGGING: Preço em JavaScript: {price_data['price']} {price_data['currency']} ({price_text})")
            
            if not price_patterns_found:
                print("DEBUGGING: Nenhum padrão de preço encontrado nos scripts JavaScript")
            
            # ANÁLISE ESTATÍSTICA: Se encontrou múltiplos preços, tomar uma decisão mais informada
            if len(all_prices) > 0:
                print(f"DEBUGGING: Total de preços encontrados: {len(all_prices)}")
                
                # Filtrar preços claramente inválidos (valores extremamente baixos ou altos)
                valid_prices = [(p, src) for p, src in all_prices if p["price"] >= 0.1]  # Mínimo de 0.1 para evitar erros
                print(f"DEBUGGING: Preços válidos após filtragem: {len(valid_prices)}")
                
                if valid_prices:
                    # Ordenar por preço
                    valid_prices.sort(key=lambda x: x[0]["price"])
                    
                    # Mostrar todos os preços encontrados para debug
                    print(f"DEBUGGING: Todos os preços válidos encontrados para {market_hash_name}:")
                    for price_data, source in valid_prices:
                        print(f"DEBUGGING:   - {price_data['price']:.2f} {price_data['currency']} ({source})")
                    
                    # Pegar a moeda predominante
                    currency_counts = {}
                    for price_data, _ in valid_prices:
                        curr = price_data["currency"]
                        currency_counts[curr] = currency_counts.get(curr, 0) + 1
                    
                    predominant_currency = max(currency_counts.items(), key=lambda x: x[1])[0]
                    print(f"DEBUGGING: Moeda predominante: {predominant_currency}")
                    
                    # Se temos múltiplos preços, calcular média e mediana
                    if len(valid_prices) > 1:
                        prices_only = [p["price"] for p, _ in valid_prices]
                        mean_price = sum(prices_only) / len(prices_only)
                        median_index = len(prices_only) // 2
                        median_price = prices_only[median_index]
                        lowest_price = prices_only[0]
                        
                        print(f"DEBUGGING: Análise detalhada:")
                        print(f"DEBUGGING:   - Número total de preços: {len(prices_only)}")
                        print(f"DEBUGGING:   - Lista ordenada de preços: {[f'{p:.2f}' for p in prices_only]}")
                        print(f"DEBUGGING:   - Índice da mediana: {median_index}")
                        print(f"DEBUGGING:   - Mínimo={lowest_price:.2f}, Mediana={median_price:.2f}, Média={mean_price:.2f}")
                        
                        # Para ser conservador, usar o menor preço desde que não seja absurdamente baixo
                        lowest_legitimate_price = lowest_price
                        
                        # Detectar outliers (preços muito altos ou muito baixos)
                        for i, price in enumerate(prices_only):
                            # Se o preço for mais de 2x a mediana, provavelmente é outlier
                            if price > median_price * 2:
                                print(f"DEBUGGING:   - Preço {price:.2f} detectado como outlier ALTO (> 2x mediana)")
                            # Se o preço for menos da metade da mediana, provavelmente é outlier
                            elif price < median_price * 0.5 and len(valid_prices) > 2:
                                print(f"DEBUGGING:   - Preço {price:.2f} detectado como outlier BAIXO (< 0.5x mediana)")
                                if i == 0:  # Se for o menor preço
                                    lowest_legitimate_price = median_price
                                    print(f"DEBUGGING:   - Usando mediana {median_price:.2f} em vez do outlier baixo")
                        
                        # O preço final agora usa a moeda original detectada
                        final_price = lowest_legitimate_price
                        final_currency = predominant_currency
                        
                        print(f"DEBUGGING:   - Preço final: {final_price:.2f} {final_currency}")
                        return {
                            "price": final_price,
                            "currency": final_currency,
                            "sources_count": len(valid_prices)
                        }
                    else:
                        # Se só temos um preço, usar esse
                        price_data, source = valid_prices[0]
                        print(f"DEBUGGING: Apenas um preço encontrado: {price_data['price']:.2f} {price_data['currency']} ({source})")
                        return {
                            "price": price_data["price"],
                            "currency": price_data["currency"],
                            "sources_count": 1
                        }
            
            # Se não encontrou nenhum preço válido
            print(f"DEBUGGING: Não foi possível encontrar preços válidos para {market_hash_name}")
            
        else:
            print(f"DEBUGGING: Erro ao acessar página do mercado: Status {response.status_code}")
    
    except Exception as e:
        print(f"DEBUGGING: Erro durante scraping para {market_hash_name}: {e}")
        import traceback
        traceback.print_exc()
    
    # Tentar uma segunda vez com outro user-agent
    try:
        print("DEBUGGING: Tentando segunda abordagem...")
        # User-agent alternativo
        alt_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
            'Accept-Language': 'en-US,en;q=0.8',
            'Cache-Control': 'max-age=0'
        }
        
        print(f"DEBUGGING: Tentando novamente com user-agent alternativo para: {market_hash_name}")
        sleep_between_requests(2.0)  # Esperar mais tempo na segunda tentativa
        
        response = requests.get(url, headers=alt_headers, timeout=30)
        
        if response.status_code == 200:
            parser = HTMLParser(response.text)
            
            # Buscar por preços em elementos principais
            all_prices = []
            
            # Verificar diferentes formatos de exibição de preço
            price_containers = parser.css("span.normal_price, span.market_listing_price_with_fee")
            
            for container in price_containers:
                price_text = container.text().strip()
                print(f"DEBUGGING: Segunda tentativa - texto de preço: '{price_text}'")
                # Verificar se é de fato um preço (contém símbolo de moeda)
                if any(symbol in price_text for symbol in ['R$', '$', '€', '¥', '£', 'kr', 'zł', '₽']):
                    price_data = extract_price_from_text(price_text, currency)
                    if price_data and price_data["price"] > 0:
                        all_prices.append((price_data, price_text))
            
            # Se encontrou candidatos, analisar
            if all_prices:
                # Ordenar por preço (menor primeiro)
                all_prices.sort(key=lambda x: x[0]["price"])
                
                # Determinar a moeda predominante
                currency_counts = {}
                for price_data, _ in all_prices:
                    curr = price_data["currency"]
                    currency_counts[curr] = currency_counts.get(curr, 0) + 1
                    
                predominant_currency = max(currency_counts.items(), key=lambda x: x[1])[0]
                
                # Filtrar candidatos que parecem ser quantidades
                valid_prices = [(price_data, text) for price_data, text in all_prices 
                               if not (price_data["price"] > 100 and price_data["price"].is_integer() and price_data["price"] % 50 == 0)]
                
                print(f"DEBUGGING: Segunda tentativa - preços válidos: {[(p['price'], p['currency']) for p, _ in valid_prices]}")
                
                if valid_prices:
                    # Se temos múltiplos preços, calcular média e mediana
                    if len(valid_prices) > 1:
                        prices_only = [p["price"] for p, _ in valid_prices]
                        median_price = prices_only[len(prices_only) // 2]
                        lowest_price = prices_only[0]
                        
                        # Verificar se o menor preço parece suspeito (muito abaixo da mediana), usar a mediana
                        if lowest_price < median_price * 0.5 and len(valid_prices) > 2:
                            print(f"DEBUGGING: Segunda tentativa - preço mais baixo ({lowest_price:.2f}) é outlier. Usando mediana ({median_price:.2f})")
                            return {
                                "price": median_price,
                                "currency": predominant_currency,
                                "sources_count": len(valid_prices)
                            }
                    
                    # Retornar o preço mais baixo (ou único)
                    price_data, price_text = valid_prices[0]
                    print(f"DEBUGGING: Segunda tentativa - preço mais baixo: {price_data['price']:.2f} {price_data['currency']} ({price_text})")
                    return {
                        "price": price_data["price"],
                        "currency": price_data["currency"],
                        "sources_count": len(valid_prices)
                    }
        
    except Exception as e:
        print(f"DEBUGGING: Segunda tentativa falhou: {e}")
    
    # Se não foi possível obter o preço, gerar um erro em vez de usar um valor fallback
    print("DEBUGGING: Nenhum preço encontrado, gerando erro")
    raise Exception(f"Não foi possível obter o preço para {market_hash_name}")


def get_item_detailed_data_via_csgostash(market_hash_name: str, currency: int = STEAM_MARKET_CURRENCY) -> Optional[Dict]:
    """
    Obtém dados completos de um item através de scraping do CSGOSkins.gg.
    Extrai todos os preços por wear condition, versões StatTrak, imagem e outras informações.
    
    Args:
        market_hash_name: Nome do item formatado para o mercado (pode incluir wear condition)
        currency: Código da moeda
        
    Returns:
        Dicionário completo com todos os dados do item ou None se falhar
    """
    # Extrair o nome base do item (remover StatTrak e wear condition)
    cleaned_name = market_hash_name.replace("StatTrak™ ", "").replace("StatTrak ", "")
    base_parts = cleaned_name.split(" (")
    base_name = base_parts[0].strip()
    
    # Transformar o nome base para o formato do CSGOSkins.gg
    formatted_name = base_name.lower()
    formatted_name = formatted_name.replace(" | ", "-")
    formatted_name = formatted_name.replace(" ", "-")
    formatted_name = re.sub(r'[^\w\-]', '', formatted_name)
    
    # Construir URL do CSGOSkins.gg
    url = f"https://csgoskins.gg/items/{formatted_name}"
    
    print(f"DEBUGGING: Obtendo dados completos para '{market_hash_name}' via CSGOSkins.gg")
    print(f"DEBUGGING: URL de consulta: {url}")
    
    # Wait time between requests
    sleep_between_requests()
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Cache-Control': 'no-cache',
        'Referer': 'https://www.google.com/'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            print(f"DEBUGGING: Erro ao acessar CSGOSkins.gg: Status {response.status_code}")
            return None
        
        parser = HTMLParser(response.text)
        html_text = response.text  # Armazenar HTML para uso posterior
        
        # Estrutura de dados a retornar
        result = {
            "market_hash_name": base_name,
            "image_url": None,
            "rarity": None,
            "category": None,
            "weapon": None,
            "prices": {
                "normal": {
                    "factory_new": None,
                    "minimal_wear": None,
                    "field_tested": None,
                    "well_worn": None,
                    "battle_scarred": None
                },
                "stattrak": {
                    "factory_new": None,
                    "minimal_wear": None,
                    "field_tested": None,
                    "well_worn": None,
                    "battle_scarred": None
                }
            },
            "currency": "USD",
            "source": "csgoskins.gg",
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        # Extrair imagem da arma
        # Tentar vários seletores possíveis para a imagem principal
        image_selectors = [
            'img[alt*="' + base_name.split('|')[0].strip() + '"]',  # Nome da arma
            'img[alt*="' + base_name.split('|')[-1].strip() + '"]',  # Nome da skin
            'img[src*="/items/"]',
            'div[class*="item"] img',
            'div[class*="image"] img',
            'main img[src*=".png"]',
            'main img[src*=".jpg"]',
            'main img[src*=".webp"]',
            'img.item-image',
            'img[class*="weapon"]',
            'img[class*="skin"]'
        ]
        
        # Também procurar por padrões no HTML
        img_pattern = r'<img[^>]+src=["\']([^"\']*(?:ak-47|redline|weapon|skin|item)[^"\']*\.(?:png|jpg|webp|jpeg))["\']'
        img_matches = re.findall(img_pattern, html_text, re.IGNORECASE)
        
        if img_matches:
            for img_src in img_matches:
                if img_src:
                    # Garantir URL absoluta
                    if img_src.startswith('//'):
                        img_src = 'https:' + img_src
                    elif img_src.startswith('/'):
                        img_src = 'https://csgoskins.gg' + img_src
                    elif not img_src.startswith('http'):
                        img_src = 'https://csgoskins.gg' + img_src
                    result["image_url"] = img_src
                    print(f"DEBUGGING: Imagem encontrada via regex: {img_src}")
                    break
        
        # Se não encontrou via regex, tentar seletores CSS
        if not result["image_url"]:
            for selector in image_selectors:
                try:
                    img_element = parser.css_first(selector)
                    if img_element:
                        img_src = img_element.attributes.get('src') or img_element.attributes.get('data-src') or img_element.attributes.get('data-lazy-src')
                        if img_src and ('png' in img_src.lower() or 'jpg' in img_src.lower() or 'webp' in img_src.lower()):
                            # Garantir URL absoluta
                            if img_src.startswith('//'):
                                img_src = 'https:' + img_src
                            elif img_src.startswith('/'):
                                img_src = 'https://csgoskins.gg' + img_src
                            elif not img_src.startswith('http'):
                                img_src = 'https://csgoskins.gg' + img_src
                            result["image_url"] = img_src
                            print(f"DEBUGGING: Imagem encontrada via CSS selector '{selector}': {img_src}")
                            break
                except Exception as e:
                    continue
        
        # Extrair informações básicas (raridade, categoria, arma)
        # Procurar por badges/pills com informações
        all_text = parser.body.text() if parser.body else ""
        
        # Extrair raridade (Classified, Covert, etc.)
        rarity_patterns = ['Classified', 'Covert', 'Restricted', 'Mil-Spec', 'Consumer', 'Exceedingly Rare']
        for rarity in rarity_patterns:
            if rarity.lower() in all_text.lower():
                result["rarity"] = rarity
                break
        
        # Extrair categoria e tipo de arma do texto
        if 'rifle' in all_text.lower():
            result["category"] = "Rifle"
        elif 'pistol' in all_text.lower():
            result["category"] = "Pistol"
        elif 'knife' in all_text.lower():
            result["category"] = "Knife"
        elif 'gloves' in all_text.lower() or 'glove' in all_text.lower():
            result["category"] = "Gloves"
        
        # Extrair nome da arma (ex: AK-47)
        weapon_match = re.search(r'(AK-47|AWP|M4A4|M4A1-S|Desert Eagle|Glock|USP-S|P250|Five-SeveN|Tec-9|CZ75|R8|Dual Berettas|P2000)', all_text, re.IGNORECASE)
        if weapon_match:
            result["weapon"] = weapon_match.group(1)
        
        # Extrair preços por wear condition
        # Usar uma abordagem mais estruturada baseada na organização da página
        all_text_lower = html_text.lower()
        
        # Mapeamento de wear conditions para padrões de busca
        wear_patterns = {
            "factory_new": [r'factory\s+new', r'\bfn\b'],
            "minimal_wear": [r'minimal\s+wear', r'\bmw\b'],
            "field_tested": [r'field[- ]tested', r'\bft\b'],
            "well_worn": [r'well[- ]worn', r'\bww\b'],
            "battle_scarred": [r'battle[- ]scarred', r'\bbs\b']
        }
        
        # Padrão para extrair preços
        price_pattern = r'(\$|R\$|€|£|¥)\s*([0-9]{1,3}(?:[.,][0-9]{2,3})*(?:[.,][0-9]{2})?)'
        
        # Dividir HTML em seções para análise mais precisa
        # Procurar por seções que contenham informações de preços organizadas
        
        # Estratégia 1: Procurar por padrões estruturados (wear condition seguido de preço)
        for wear_key, wear_patterns_list in wear_patterns.items():
            for wear_pattern in wear_patterns_list:
                # Procurar todas as ocorrências do padrão de wear
                for match in re.finditer(wear_pattern, html_text, re.IGNORECASE):
                    # Pegar contexto maior ao redor (até 300 caracteres)
                    start_pos = max(0, match.start() - 150)
                    end_pos = min(len(html_text), match.end() + 300)
                    context = html_text[start_pos:end_pos]
                    context_lower = context.lower()
                    
                    # Verificar se é StatTrak (procurar antes do wear pattern)
                    is_stattrak = False
                    # Verificar se há "stattrak" antes do wear pattern no contexto
                    pre_context = html_text[max(0, match.start() - 100):match.start()].lower()
                    if 'stattrak' in pre_context or 'stattrak' in context_lower[:200]:
                        is_stattrak = True
                    
                    # Verificar se não é "Not possible"
                    if 'not possible' in context_lower:
                        print(f"DEBUGGING: {wear_key} marcado como 'Not possible'")
                        continue
                    
                    # Procurar preço no contexto (procurar após o wear pattern)
                    post_context = context[match.end() - start_pos:]
                    price_matches = re.findall(price_pattern, post_context)
                    
                    if price_matches:
                        # Pegar o primeiro preço válido encontrado após o wear pattern
                        for symbol, price_text in price_matches:
                            try:
                                # Converter preço
                                if symbol == 'R$':
                                    # Formato brasileiro: R$ 1.234,56
                                    price_value = float(price_text.replace('.', '').replace(',', '.'))
                                else:
                                    # Formato internacional: $1234.56
                                    price_value = float(price_text.replace(',', ''))
                                
                                # Validar preço (deve ser razoável)
                                if 0.01 <= price_value <= 100000:
                                    if is_stattrak:
                                        if result["prices"]["stattrak"][wear_key] is None:
                                            result["prices"]["stattrak"][wear_key] = price_value
                                            currency_map = {'$': 'USD', 'R$': 'BRL', '€': 'EUR', '£': 'GBP', '¥': 'CNY'}
                                            result["currency"] = currency_map.get(symbol, 'USD')
                                            print(f"DEBUGGING: Preço StatTrak {wear_key}: {symbol}{price_value}")
                                    else:
                                        if result["prices"]["normal"][wear_key] is None:
                                            result["prices"]["normal"][wear_key] = price_value
                                            currency_map = {'$': 'USD', 'R$': 'BRL', '€': 'EUR', '£': 'GBP', '¥': 'CNY'}
                                            result["currency"] = currency_map.get(symbol, 'USD')
                                            print(f"DEBUGGING: Preço Normal {wear_key}: {symbol}{price_value}")
                                    break
                            except ValueError as e:
                                print(f"DEBUGGING: Erro ao converter preço '{price_text}': {e}")
                                continue
                
                # Se já encontrou preço para este wear (normal ou stattrak), passar para o próximo
                if result["prices"]["normal"][wear_key] is not None or result["prices"]["stattrak"][wear_key] is not None:
                    break
        
        # Calcular range de preços
        all_price_values = []
        for wear_prices in [result["prices"]["normal"], result["prices"]["stattrak"]]:
            for price in wear_prices.values():
                if price is not None:
                    all_price_values.append(price)
        
        if all_price_values:
            result["price_range"] = {
                "min": min(all_price_values),
                "max": max(all_price_values)
            }
            # Usar preço médio como price padrão (ou Field-Tested se disponível)
            if result["prices"]["normal"]["field_tested"]:
                result["price"] = result["prices"]["normal"]["field_tested"]
            else:
                result["price"] = sum(all_price_values) / len(all_price_values)
        else:
            result["price_range"] = {"min": 0, "max": 0}
            result["price"] = 0
        
        print(f"DEBUGGING: Dados completos extraídos para {base_name}")
        return result
        
    except Exception as e:
        print(f"DEBUGGING: Erro durante scraping completo do CSGOSkins.gg para {market_hash_name}: {e}")
        import traceback
        traceback.print_exc()
        return None


def get_item_price_via_csgostash(market_hash_name: str, currency: int = STEAM_MARKET_CURRENCY) -> Optional[Dict]:
    """
    Obtém o preço de um item através de scraping do CSGOSkins.gg.
    Mais estável e menos propenso a bloqueios que o scraping direto da Steam.
    
    Args:
        market_hash_name: Nome do item formatado para o mercado
        currency: Código da moeda (não utilizado diretamente, site usa localização do navegador)
        
    Returns:
        Dicionário com preço e moeda do item, ou None se falhar
    """
    # Verificar se estamos lidando com StatTrak
    is_stattrak = "StatTrak" in market_hash_name
    
    # Extrair o nome base do item e sua condição
    # Remover o prefixo "StatTrak™ " se existir
    cleaned_name = market_hash_name.replace("StatTrak™ ", "")
    
    # Separar o nome base da condição (Field-Tested, Well-Worn, etc.)
    base_parts = cleaned_name.split(" (")
    base_name = base_parts[0].strip()
    condition = ""
    if len(base_parts) > 1:
        condition = base_parts[1].replace(")", "").strip()
    
    # Transformar o nome base para o formato do CSGOSkins.gg
    # Exemplo: "AK-47 | Asiimov" -> "ak-47-asiimov"
    formatted_name = base_name.lower()
    formatted_name = formatted_name.replace(" | ", "-")
    formatted_name = formatted_name.replace(" ", "-")
    formatted_name = re.sub(r'[^\w\-]', '', formatted_name)
    
    # Construir URL do CSGOSkins.gg
    url = f"https://csgoskins.gg/items/{formatted_name}"
    
    print(f"DEBUGGING: Obtendo preço para '{market_hash_name}' via CSGOSkins.gg")
    print(f"DEBUGGING: URL de consulta: {url}")
    print(f"DEBUGGING: Condição: {condition}, StatTrak: {is_stattrak}")

    # Wait time between requests
    sleep_between_requests()
    
    # Use iPhone User-Agent that worked in tests
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
        'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',  # Set Portuguese to get prices in BRL
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Cache-Control': 'no-cache',
        'Referer': 'https://www.google.com/'
    }
    
    # Mapeamento de nomes de condições para termos de busca
    condition_keywords = {
        "Factory New": ["factory new", "fn", "new"],
        "Minimal Wear": ["minimal wear", "mw", "minimal"],
        "Field-Tested": ["field-tested", "ft", "field"],
        "Well-Worn": ["well-worn", "ww", "well"],
        "Battle-Scarred": ["battle-scarred", "bs", "scarred", "battle"]
    }
    
    try:
        # Tentar obter a página
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            # Processar HTML com selectolax
            parser = HTMLParser(response.text)
            
            # Verificar se obtivemos o título correto para garantir que a página foi carregada adequadamente
            title = parser.css_first('title')
            if title and market_hash_name.split(" (")[0].lower() in title.text().lower():
                print(f"DEBUGGING: Título da página encontrado: {title.text()}")
            else:
                print("DEBUGGING: Título da página não encontrado ou não corresponde ao item")
                if title:
                    print(f"DEBUGGING: Título encontrado: {title.text()}")
            
            # Extrair texto HTML completo para análise
            all_text = parser.body.text() if parser.body else ""
            
            # Obter todos os preços genéricos
            general_price_pattern = r'(\$|R\$|€|£|¥)\s*([0-9.,]+)'
            general_prices = re.findall(general_price_pattern, all_text)
            
            print(f"DEBUGGING: Encontrados {len(general_prices)} preços genéricos")
            
            # Se temos uma condição específica, tentar encontrar preços relacionados à ela
            condition_matches = []
            stattrak_matches = []
            
            if condition:
                # Buscar termos relacionados à condição específica
                search_terms = condition_keywords.get(condition, [condition.lower()])
                
                # Para cada preço, analisar o texto ao redor para verificar se está relacionado à condição
                for i, (symbol, price_text) in enumerate(general_prices):
                    # Pegar contexto de até 200 caracteres antes e depois do preço
                    price_pos = all_text.find(f"{symbol}{price_text}")
                    if price_pos > 0:
                        start_pos = max(0, price_pos - 200)
                        end_pos = min(len(all_text), price_pos + 200)
                        context = all_text[start_pos:end_pos].lower()
                        
                        # Verificar se algum termo da condição está no contexto
                        condition_match = any(term in context for term in search_terms)
                        
                        # Para StatTrak, verificar se há menção no contexto
                        stattrak_match = "stattrak" in context if is_stattrak else True
                        
                        if condition_match:
                            condition_matches.append((i, symbol, price_text, stattrak_match))
                            if stattrak_match:
                                stattrak_matches.append((i, symbol, price_text))
                
                print(f"DEBUGGING: Encontrados {len(condition_matches)} preços relacionados à condição '{condition}'")
                if is_stattrak:
                    print(f"DEBUGGING: Destes, {len(stattrak_matches)} também mencionam StatTrak")
            
            # Processar os preços encontrados
            price_data = None
            
            # Caso 1: Se temos preços específicos para condição e StatTrak
            if is_stattrak and stattrak_matches:
                # Usar o primeiro preço que corresponde à condição e StatTrak
                _, symbol, price_text = stattrak_matches[0]
                print(f"DEBUGGING: Usando preço específico para StatTrak + {condition}: {symbol}{price_text}")
                price_data = _process_price(symbol, price_text)
                
            # Caso 2: Se temos preços específicos para a condição (sem StatTrak ou não é StatTrak)
            elif condition_matches:
                # Usar o primeiro preço que corresponde à condição
                _, symbol, price_text, _ = condition_matches[0]
                print(f"DEBUGGING: Usando preço específico para condição {condition}: {symbol}{price_text}")
                price_data = _process_price(symbol, price_text)
                
            # Caso 3: Se não encontramos preços específicos, usar estimativa baseada em padrões
            elif general_prices:
                # Para itens StatTrak, tentar identificar preços mais altos (StatTrak geralmente custa mais)
                if is_stattrak:
                    # Converter todos os preços para valores numéricos
                    numeric_prices = []
                    for symbol, price_text in general_prices:
                        try:
                            if symbol == 'R$':
                                price_value = float(price_text.replace('.', '').replace(',', '.'))
                            else:
                                price_value = float(price_text.replace(',', ''))
                            numeric_prices.append((symbol, price_value))
                        except ValueError:
                            continue
                    
                    # Ordenar preços (maior para menor)
                    numeric_prices.sort(key=lambda x: x[1], reverse=True)
                    
                    # StatTrak geralmente custa mais, usar um dos preços mais altos
                    if numeric_prices:
                        # Usar o terceiro maior preço para ser conservador
                        index = min(2, len(numeric_prices)-1)
                        symbol, price_value = numeric_prices[index]
                        print(f"DEBUGGING: Usando preço estimado para StatTrak (3º maior): {symbol}{price_value:.2f}")
                        price_data = {
                            "price": price_value,
                            "currency": _get_currency_from_symbol(symbol),
                            "source": "csgoskins.gg",
                            "estimated": True
                        }
                else:
                    # Converter todos os preços para valores numéricos e filtrar valores claramente inválidos
                    numeric_prices = []
                    for symbol, price_text in general_prices:
                        try:
                            if symbol == 'R$':
                                price_value = float(price_text.replace('.', '').replace(',', '.'))
                            else:
                                price_value = float(price_text.replace(',', ''))
                            
                            # Filtrar valores muito altos ou muito baixos
                            if 0.1 <= price_value <= 5000:
                                numeric_prices.append((symbol, price_value))
                        except ValueError:
                            continue
                    
                    # Ordenar preços (menor para maior)
                    numeric_prices.sort(key=lambda x: x[1])
                    
                    if numeric_prices:
                        # Encontrar a posição média com base na condição
                        condition_ranks = {
                            "Factory New": 0.8,  # Usar preço próximo ao mais alto
                            "Minimal Wear": 0.6,  # Um pouco acima da média
                            "Field-Tested": 0.4,  # Na média
                            "Well-Worn": 0.2,  # Abaixo da média
                            "Battle-Scarred": 0.1  # Próximo ao mais baixo
                        }
                        
                        # Obter o rank, com padrão para Field-Tested se a condição não for conhecida
                        rank = condition_ranks.get(condition, 0.4)
                        
                        # Calcular a posição com base no rank
                        index = min(int(len(numeric_prices) * rank), len(numeric_prices) - 1)
                        symbol, price_value = numeric_prices[index]
                        
                        print(f"DEBUGGING: Usando preço estimado para {condition or 'condição desconhecida'}: {symbol}{price_value:.2f} (rank {rank}, índice {index})")
                        price_data = {
                            "price": price_value,
                            "currency": _get_currency_from_symbol(symbol),
                            "source": "csgoskins.gg",
                            "estimated": True
                        }
                    
            # Se encontramos um preço, retornar
            if price_data:
                return price_data
            
            print(f"DEBUGGING: Nenhum preço adequado encontrado para {market_hash_name} no CSGOSkins.gg")
        else:
            print(f"DEBUGGING: Erro ao acessar CSGOSkins.gg: Status {response.status_code}")
    
    except Exception as e:
        print(f"DEBUGGING: Erro durante scraping do CSGOSkins.gg para {market_hash_name}: {e}")
        import traceback
        traceback.print_exc()
    
    # Se tudo falhar, tentar Fallback para o método anterior
    print(f"DEBUGGING: Tentando fallback para método de scraping direto da Steam")
    try:
        return get_item_price_via_scraping(market_hash_name, STEAM_APPID, currency)
    except Exception as e:
        print(f"DEBUGGING: Fallback também falhou: {e}")
    
    return None

# Helper function to process price based on symbol and text
def _process_price(symbol: str, price_text: str) -> Dict:
    """Converts price text to a dictionary with price and currency."""
    try:
        if symbol == 'R$':
            # Brazilian format: R$ 10,50
            price_value = float(price_text.replace('.', '').replace(',', '.'))
        else:
            # International format: $10.50
            price_value = float(price_text.replace(',', ''))
        
        return {
            "price": price_value,
            "currency": _get_currency_from_symbol(symbol),
            "source": "csgoskins.gg"
        }
    except ValueError:
        print(f"DEBUGGING: Não foi possível converter o valor '{price_text}' para float")
        return None

# Função auxiliar para obter o código da moeda a partir do símbolo
def _get_currency_from_symbol(symbol: str) -> str:
    """Retorna o código da moeda a partir do símbolo."""
    currency_map = {
        '$': 'USD',
        'R$': 'BRL',
        '€': 'EUR',
        '£': 'GBP',
        '¥': 'CNY'
    }
    return currency_map.get(symbol, 'USD')


def get_item_price(market_hash_name: str, currency: int = None, appid: int = None) -> Dict:
    """
    Obtém o preço atual de um item no mercado.
    Primeiro verifica no banco de dados, e se não encontrar ou estiver desatualizado,
    usa o método de scraping completo do CSGOSkins.gg e salva o resultado no banco.
    
    Args:
        market_hash_name: Nome formatado do item para o mercado (pode incluir wear condition)
        currency: Código da moeda (padrão definido em configuração)
        appid: ID da aplicação na Steam
        
    Returns:
        Dicionário com o preço, a moeda e outras informações do item (incluindo dados completos)
        
    Raises:
        Exception: Se não for possível obter o preço atual do CSGOSkins.gg
    """
    if currency is None:
        currency = STEAM_MARKET_CURRENCY
        
    if appid is None:
        appid = STEAM_APPID
    
    # Verificar se o item já está no cache em memória
    cache_key = f"{market_hash_name}_{currency}_{appid}"
    if cache_key in price_cache:
        print(f"Usando preço em cache (memória) para {market_hash_name}")
        return price_cache[cache_key]
    
    # Verificar se o item está no banco de dados
    db_result = get_skin_price(market_hash_name, currency, appid)
    if db_result is not None:
        print(f"Usando dados do banco de dados para {market_hash_name}")
        # Construir resposta com dados do banco
        price_data = {
            "price": db_result["price"],
            "currency": "USD" if currency == 1 else "BRL" if currency == 7 else "EUR" if currency == 3 else "UNKNOWN",
            "source": "database"
        }
        
        # Adicionar dados detalhados se disponíveis
        if db_result.get("detailed_data"):
            if isinstance(db_result["detailed_data"], str):
                # Se for string JSON, fazer parse
                try:
                    price_data["detailed_data"] = json.loads(db_result["detailed_data"])
                except:
                    price_data["detailed_data"] = db_result["detailed_data"]
            else:
                price_data["detailed_data"] = db_result["detailed_data"]
        
        if db_result.get("image_url"):
            price_data["image_url"] = db_result["image_url"]
        
        price_cache[cache_key] = price_data
        return price_data
    
    # Buscar dados completos via scraping do CSGOSkins.gg
    try:
        print(f"Buscando dados completos via CSGOSkins.gg para {market_hash_name}")
        detailed_data = get_item_detailed_data_via_csgostash(market_hash_name, currency)
        
        # Verificar se o scraping retornou dados válidos
        if not detailed_data:
            # Fallback para método antigo se o novo falhar
            print(f"Scraping completo falhou, tentando método antigo...")
            price_data = get_item_price_via_csgostash(market_hash_name, currency)
            if not price_data or price_data.get("price", 0) <= 0:
                raise Exception(f"Não foi possível obter o preço atual de {market_hash_name} no CSGOSkins.gg")
            
            processed_price = process_scraped_price(market_hash_name, price_data["price"])
            if processed_price <= 0:
                raise Exception(f"O processamento resultou em um preço inválido para {market_hash_name}")
            
            price_data["price"] = processed_price
            price_data["processed"] = True
            price_cache[cache_key] = price_data
            save_skin_price(market_hash_name, processed_price, currency, appid)
            return price_data
        
        # Extrair preço específico se market_hash_name contém wear condition
        extracted_price = detailed_data.get("price", 0)
        is_stattrak = "StatTrak" in market_hash_name or "stattrak" in market_hash_name.lower()
        
        # Tentar extrair wear condition do nome
        wear_condition = None
        wear_key_map = {
            "Factory New": "factory_new",
            "Minimal Wear": "minimal_wear",
            "Field-Tested": "field_tested",
            "Well-Worn": "well_worn",
            "Battle-Scarred": "battle_scarred"
        }
        
        for wear_name, wear_key in wear_key_map.items():
            if wear_name.lower() in market_hash_name.lower():
                wear_condition = wear_key
                break
        
        # Se encontrou wear condition específica, usar esse preço
        if wear_condition and detailed_data.get("prices"):
            if is_stattrak and detailed_data["prices"]["stattrak"].get(wear_condition):
                extracted_price = detailed_data["prices"]["stattrak"][wear_condition]
            elif detailed_data["prices"]["normal"].get(wear_condition):
                extracted_price = detailed_data["prices"]["normal"][wear_condition]
        
        # Processar o preço obtido
        processed_price = process_scraped_price(market_hash_name, extracted_price)
        
        if processed_price <= 0:
            raise Exception(f"O processamento resultou em um preço inválido para {market_hash_name}")
        
        # Registrar que o scraping foi feito
        update_last_scrape_time(market_hash_name, currency, appid)
        
        # Preparar dados para retorno
        price_data = {
            "price": processed_price,
            "currency": detailed_data.get("currency", "USD"),
            "source": "csgoskins.gg",
            "processed": True,
            "market_hash_name": detailed_data.get("market_hash_name", market_hash_name),
            "image_url": detailed_data.get("image_url"),
            "rarity": detailed_data.get("rarity"),
            "category": detailed_data.get("category"),
            "weapon": detailed_data.get("weapon"),
            "prices": detailed_data.get("prices"),
            "price_range": detailed_data.get("price_range"),
            "timestamp": detailed_data.get("timestamp")
        }
        
        # Armazenar no cache e banco de dados
        price_cache[cache_key] = price_data
        
        # Salvar no banco com dados detalhados
        save_skin_price(
            market_hash_name, 
            processed_price, 
            currency, 
            appid,
            detailed_data=detailed_data,
            image_url=detailed_data.get("image_url")
        )
        
        return price_data
    except Exception as e:
        print(f"Erro ao fazer scraping para {market_hash_name}: {e}")
        import traceback
        traceback.print_exc()
        # Propagar o erro para o frontend em vez de usar fallback
        raise Exception(f"Erro ao obter preço para {market_hash_name}: {str(e)}")


def classify_item_and_get_price_limit(market_hash_name: str) -> tuple:
    """
    Classifica um item com base em seu nome e retorna uma categoria e um limite de preço razoável.
    
    Args:
        market_hash_name: Nome do item no formato do mercado
        
    Returns:
        Tupla (categoria, limite_de_preço)
    """
    market_hash_name_lower = market_hash_name.lower()
    
    # Mapeamento de tipos de itens para limites de preço razoáveis (em R$)
    categories = [
        # Categoria: Knives (Facas) - Itens mais caros
        {
            "category": "knife",
            "keywords": ["★ ", "knife", "karambit", "bayonet", "butterfly", "flip knife", "gut knife", "huntsman", "falchion", "bowie", "daggers"],
            "limit": 5000.0
        },
        # Categoria: Luvas
        {
            "category": "gloves",
            "keywords": ["★ gloves", "★ hand", "sport gloves", "driver gloves", "specialist gloves", "bloodhound gloves"],
            "limit": 4000.0
        },
        # Categoria: Skins raras/caras
        {
            "category": "rare_skins",
            "keywords": ["dragon lore", "howl", "gungnir", "fire serpent", "fade", "asiimov", "doppler", "tiger tooth", "slaughter", "crimson web", "marble fade"],
            "limit": 3000.0
        },
        # Categoria: StatTrak
        {
            "category": "stattrak",
            "keywords": ["stattrak™"],
            "limit": 1000.0
        },
        # Categoria: AWP (Sniper rifle popular)
        {
            "category": "awp",
            "keywords": ["awp"],
            "limit": 500.0
        },
        # Categoria: Rifles populares
        {
            "category": "popular_rifles",
            "keywords": ["ak-47", "m4a4", "m4a1-s"],
            "limit": 350.0
        },
        # Categoria: Outras armas
        {
            "category": "other_weapons",
            "keywords": ["deagle", "desert eagle", "usp-s", "glock", "p250", "p90", "mp5", "mp7", "mp9", "mac-10", "mag-7", "nova", "sawed-off", "xm1014", "galil", "famas", "sg 553", "aug", "ssg 08", "g3sg1", "scar-20", "m249", "negev"],
            "limit": 150.0
        },
        # Categoria: Cases (Caixas)
        {
            "category": "cases",
            "keywords": ["case", "caixa"],
            "limit": 30.0
        },
        # Categoria: Stickers (Adesivos)
        {
            "category": "stickers",
            "keywords": ["sticker", "adesivo"],
            "limit": 50.0
        },
        # Categoria: Agents (Agentes)
        {
            "category": "agents",
            "keywords": ["agent", "agente", "soldier", "operator", "muhlik", "cmdr", "doctor", "lieutenant", "saidan", "chef", "cypher", "enforcer", "crasswater", "farlow", "voltzmann", "street soldier"],
            "limit": 30.0
        },
        # Categoria: Outros itens
        {
            "category": "other_items",
            "keywords": ["pin", "patch", "graffiti", "spray", "music kit", "pass"],
            "limit": 20.0
        }
    ]
    
    # Verificar cada categoria
    for category in categories:
        for keyword in category["keywords"]:
            if keyword in market_hash_name_lower:
                return category["category"], category["limit"]
    
    # Padrão: categoria desconhecida com limite conservador
    return "unknown", 50.0


def get_steam_api_data(interface: str, method: str, version: str, params: dict) -> Optional[Dict]:
    """
    Realiza uma chamada para a API oficial da Steam.
    
    Args:
        interface: A interface da API (ex: 'IEconService')
        method: O método a ser chamado (ex: 'GetTradeOffers')
        version: A versão da API (ex: 'v1')
        params: Parâmetros adicionais para a chamada
        
    Returns:
        Dados da API ou None se falhar
    """
    url = f"{STEAM_API_URL}/{interface}/{method}/{version}/"
    
    # Adiciona a chave API aos parâmetros
    api_params = params.copy()
    api_params['key'] = STEAM_API_KEY
    
    try:
        # Wait appropriate time between requests
        sleep_between_requests()
        
        response = requests.get(url, params=api_params, timeout=15)
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error in official Steam API: Status {response.status_code}, URL: {url}")
            if response.status_code == 403:
                print("Authentication error: Verify that the API key is correct and has necessary permissions.")
    
    except Exception as e:
        print(f"Error calling official Steam API: {e}")
        
    return None


def get_item_listings_page(market_hash_name: str, appid: int = None) -> Optional[str]:
    """
    Obtém a página HTML de listagens do mercado para um item específico.
    Essa função pode ser usada para scraping de informações adicionais.
    
    Args:
        market_hash_name: Nome do item formatado para o mercado
        appid: ID da aplicação na Steam (730 = CS2). Se None, usa configuração
        
    Returns:
        HTML da página ou None se falhar
    """
    if appid is None:
        appid = STEAM_APPID
        
    # URL da página de listagens do mercado
    encoded_name = requests.utils.quote(market_hash_name)
    url = f"{STEAM_MARKET_BASE_URL}/{appid}/{encoded_name}"
    
    try:
        # Wait appropriate time between requests
        sleep_between_requests()
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            return response.text
        else:
            print(f"Error accessing market page: Status {response.status_code}")
            
    except Exception as e:
        print(f"Error getting listings page for {market_hash_name}: {e}")
    
    return None


def get_api_status() -> Dict[str, Any]:
    """
    Verifica o status do sistema de scraping e da API oficial da Steam.
    
    Returns:
        Dicionário com informações sobre o status
    """
    result = {
        "scraping_system": "active",
        "scraping_test": False,
        "steam_web_api_reachable": False,
        "api_key_configured": bool(STEAM_API_KEY),
        "currency": STEAM_MARKET_CURRENCY,
        "appid": STEAM_APPID,
        "cache_info": {
            "size": len(price_cache),
            "maxsize": price_cache.maxsize,
            "ttl_seconds": price_cache.ttl
        },
        "pricing_method": "csgostash_scraping"  # Atualizado para refletir o uso do CSGOStash
    }
    
    # Testar sistema de scraping com um item comum
    try:
        test_item = "Operation Broken Fang Case"
        
        # Tenta remover do cache para testar o scraping realmente
        cache_key = f"{test_item}_{STEAM_MARKET_CURRENCY}_{STEAM_APPID}"
        if cache_key in price_cache:
            del price_cache[cache_key]
            
        # Testa o scraping
        start_time = time.time()
        price = get_item_price_via_csgostash(test_item, STEAM_MARKET_CURRENCY)
        end_time = time.time()
        
        result["scraping_test"] = price is not None
        
        if price is not None:
            result["scraping_test_response"] = {
                "item": test_item,
                "price": price,
                "time_taken_ms": round((end_time - start_time) * 1000),
                "source": "csgostash"
            }
        
    except Exception as e:
        print(f"Error testing CSGOStash scraping system: {e}")
        result["scraping_error"] = str(e)
    
    # Testar conexão com API oficial da Steam (somente para fins de diagnóstico)
    # Note: This API is NOT used to get prices, only for other data
    if STEAM_API_KEY:
        try:
            # Teste simples com a interface ISteamUser
            api_data = get_steam_api_data(
                "ISteamUser", 
                "GetPlayerSummaries", 
                "v2", 
                {"steamids": "76561198071275191"}  # Exemplo de SteamID
            )
            
            result["steam_web_api_reachable"] = api_data is not None
            
            if api_data:
                result["web_api_test_response"] = {
                    "response_status": "OK",
                    "players_found": len(api_data.get("response", {}).get("players", [])),
                    "note": "API oficial usada apenas para dados de inventário, não para preços"
                }
                
        except Exception as e:
            print(f"Error testing official Steam API: {e}")
            result["web_api_error"] = str(e)
    
    return result