# Configuração do arquivo .env

Para configurar o banco de dados localmente, você precisa criar um arquivo `.env` na raiz do projeto.

## Passos:

1. Copie o arquivo `env.example` para `.env`:
   ```bash
   cp env.example .env
   ```

2. Ou crie manualmente o arquivo `.env` com o seguinte conteúdo:

```bash
# Database Configuration
# Neon.tech PostgreSQL Database
DATABASE_URL="postgres://sidnei-almeida:A1b2C3d4E5f6@ep-exemplo-host.us-east-2.aws.neon.tech/neondb"

# Steam API Configuration (optional)
# STEAM_API_KEY=your_steam_api_key_here

# JWT Secret Key (optional, will be auto-generated if not provided)
# JWT_SECRET_KEY=your_secret_key_here

# Python Version
PYTHON_VERSION=3.11.0
```

## Nota importante:

Se você encontrar erros de conexão SSL com o Neon.tech, adicione os parâmetros SSL à connection string:

```bash
DATABASE_URL="postgres://sidnei-almeida:A1b2C3d4E5f6@ep-exemplo-host.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
```

O código tentará automaticamente diferentes modos SSL se os parâmetros não estiverem especificados, mas é recomendado incluí-los explicitamente para Neon.tech.

