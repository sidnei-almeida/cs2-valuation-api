import requests
import re
from selectolax.parser import HTMLParser

def test_csgoskins(item_name="AK-47 | Asiimov (Field-Tested)"):
    """
    Tests price retrieval via CSGOSkins.gg using iPhone User-Agent that worked in tests.
    """
    # Format item name
    cleaned_name = item_name.replace("StatTrak™ ", "")
    base_parts = cleaned_name.split(" (")
    base_name = base_parts[0].strip()
    formatted_name = base_name.lower().replace(" | ", "-").replace(" ", "-")
    formatted_name = re.sub(r'[^\w\-]', '', formatted_name)
    
    # URL for the item
    url = f"https://csgoskins.gg/items/{formatted_name}"
    print(f"URL: {url}")
    
    # Headers with iPhone User-Agent that worked in previous tests
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
        'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Cache-Control': 'no-cache',
        'Referer': 'https://www.google.com/'
    }
    
    try:
        # Make the request
        response = requests.get(url, headers=headers, timeout=30)
        print(f"Status: {response.status_code}")
        print(f"Response size: {len(response.text)} bytes")
        
        if response.status_code == 200:
            # HTML parser
            parser = HTMLParser(response.text)
            title = parser.css_first('title')
            if title:
                print(f"Page title: {title.text()}")
            
            # Extract all prices from HTML
            all_text = parser.body.text() if parser.body else ""
            price_matches = re.findall(r'(Factory New|Minimal Wear|Field-Tested|Well-Worn|Battle-Scarred)(?:.*?)(\$|R\$|€|£|¥)\s*([0-9.,]+)', all_text)
            
            if price_matches:
                print(f"Found {len(price_matches)} price matches:")
                for found_condition, symbol, price_text in price_matches:
                    print(f"  - {found_condition}: {symbol}{price_text}")
                    
                # Check if there are prices for the specific item condition
                if len(base_parts) > 1:
                    condition = base_parts[1].replace(")", "").strip()
                    matching_prices = [match for match in price_matches if match[0].lower() == condition.lower()]
                    if matching_prices:
                        print(f"\nPrices for specific condition ({condition}):")
                        for found_condition, symbol, price_text in matching_prices:
                            print(f"  - {symbol}{price_text}")
            else:
                print("No price pattern found with the specific format.")
                
                # Try a simpler regex for any price pattern
                general_prices = re.findall(r'(\$|R\$|€|£|¥)\s*([0-9.,]+)', all_text)
                if general_prices:
                    print(f"Found {len(general_prices)} generic prices:")
                    for symbol, price_text in general_prices[:10]:  # Show up to 10
                        print(f"  - {symbol}{price_text}")
                else:
                    print("No prices found in text.")
                    
            # Save response for later analysis
            with open('csgoskins_response.html', 'w', encoding='utf-8') as f:
                f.write(response.text)
            print("Response saved to 'csgoskins_response.html'")
            
        else:
            print(f"Error: Status code {response.status_code}")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("==== Testing CSGOSkins.gg for AK-47 Asiimov ====")
    test_csgoskins("AK-47 | Asiimov (Field-Tested)")
    
    print("\n==== Testing CSGOSkins.gg for AWP Asiimov ====")
    test_csgoskins("AWP | Asiimov (Field-Tested)")
    
    print("\n==== Testing CSGOSkins.gg for StatTrak item ====")
    test_csgoskins("StatTrak™ AK-47 | Redline (Field-Tested)")
