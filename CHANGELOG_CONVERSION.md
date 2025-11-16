# Changelog - Remoção de Conversão de Moeda do Backend

## Data: 2025-11-16

## Mudança Principal
A conversão de moeda (USD → BRL) foi removida do backend. Agora a API sempre retorna preços em USD e a conversão deve ser feita no frontend.

## Motivação
- Maior flexibilidade para o frontend controlar a taxa de câmbio
- Taxa de câmbio pode ser atualizada dinamicamente no frontend
- Melhor performance (sem processamento de conversão no backend)
- Suporte a múltiplas moedas sem mudanças na API

## Mudanças Realizadas

### 1. Endpoint GET /api/inventory/item-price
**Antes:**
- Parâmetro `currency` aceito (USD, BRL, EUR)
- Retornava `price_brl` quando currency=BRL

**Depois:**
- Parâmetro `currency` removido
- Sempre retorna `price_usd` em USD
- `price_brl` sempre `null`
- `currency` sempre "USD"

### 2. Endpoint POST /api/inventory/analyze-items
**Antes:**
- Campo `currency` no request (padrão: "BRL")
- Retornava `total_value_brl` e `price_brl` para cada item

**Depois:**
- Campo `currency` removido do request
- Retorna apenas `total_value_usd` e `price_usd`
- `currency` na resposta sempre "USD"

### 3. Modelos (models/inventory.py)
**Mudanças:**
- `ItemPriceRequest`: Removido campo `currency`
- `InventoryAnalysisRequest`: Removido campo `currency`
- `InventoryAnalysisResponse`: Removido campo `total_value_brl`

### 4. Serviços (services/inventory_pricer.py)
**Mudanças:**
- `analyze_inventory_items()`: Removido parâmetro `currency`
- Removida toda lógica de conversão USD → BRL
- Removidas constantes `EXCHANGE_RATE_USD_TO_BRL` e `STEAM_TAX` (ainda no código mas não usadas)

## Fórmula de Conversão (Frontend)

A conversão deve ser feita no frontend usando:

```javascript
const exchangeRate = 5.00; // Obter de API de câmbio atual
const steamTax = 0.15; // 15% de taxa da Steam
const priceBRL = priceUSD * exchangeRate * (1 + steamTax);
```

## Exemplo de Uso

### Antes (Backend fazia conversão):
```javascript
const response = await fetch(
  `${API_BASE_URL}/api/inventory/item-price?` +
  `market_hash_name=AK-47%20%7C%20Redline&` +
  `exterior=Field-Tested&` +
  `currency=BRL`
);
const data = await response.json();
console.log(`Preço: R$ ${data.price_brl}`); // R$ 184.58
```

### Depois (Frontend faz conversão):
```javascript
const response = await fetch(
  `${API_BASE_URL}/api/inventory/item-price?` +
  `market_hash_name=AK-47%20%7C%20Redline&` +
  `exterior=Field-Tested`
);
const data = await response.json();

// Converter no frontend
const exchangeRate = 5.00; // Obter de API de câmbio
const steamTax = 0.15;
const priceBRL = data.price_usd * exchangeRate * (1 + steamTax);
console.log(`Preço: R$ ${priceBRL.toFixed(2)}`); // R$ 184.58
```

## Arquivos Modificados

1. `main.py` - Removido parâmetro currency e lógica de conversão
2. `models/inventory.py` - Removidos campos currency dos requests
3. `services/inventory_pricer.py` - Removida lógica de conversão
4. `FRONTEND_INTEGRATION_GUIDE.txt` - Atualizado com novos exemplos

## Compatibilidade

⚠️ **BREAKING CHANGE**: Esta mudança quebra a compatibilidade com código frontend que esperava conversão automática.

**Ação necessária no frontend:**
- Remover parâmetro `currency` das requisições
- Implementar conversão USD → BRL no frontend
- Atualizar código que usa `price_brl` e `total_value_brl` da resposta

## Benefícios

✅ Taxa de câmbio sempre atualizada (frontend pode buscar de API de câmbio)
✅ Melhor performance (sem processamento no backend)
✅ Maior flexibilidade (suporte a múltiplas moedas)
✅ Separação de responsabilidades (backend busca preços, frontend formata)

