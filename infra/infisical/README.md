# Infisical — Secret Management

Менеджер секретов для fm-review-system. Заменяет plaintext `.env`.

## Production: Hosted Infisical

Основной инстанс: **https://infisical.shakhoff.com**

- Org: Shakhovskiy
- Project: `fm-review-system` (ID: `3288744a-5f74-440b-a037-3e77c752cd2f`)
- Environment: `dev`
- Auth: Machine Identity `fm-review-pipeline` (Universal Auth, TTL 10 лет)

### Machine Identity credentials

Файл `.env.machine-identity` (уже настроен, в `.gitignore`):
```
INFISICAL_API_URL=https://infisical.shakhoff.com/api
INFISICAL_CLIENT_ID=<client_id>
INFISICAL_CLIENT_SECRET=<client_secret>
INFISICAL_PROJECT_ID=3288744a-5f74-440b-a037-3e77c752cd2f
```

### Проверка

```bash
# Загрузить секреты
source scripts/load-secrets.sh

# Или проверить напрямую
./scripts/check-secrets.sh --verbose
```

## Fallback: Self-Hosted (docker-compose)

При необходимости можно поднять локальный инстанс:

```bash
cp .env.infisical.example .env.infisical
# Заполнить ENCRYPTION_KEY, AUTH_SECRET, POSTGRES_PASSWORD
docker compose --env-file .env.infisical up -d
# UI: http://localhost:8080
```

## Секреты в проекте (10 шт.)

| Ключ | Назначение |
|------|-----------|
| ANTHROPIC_API_KEY | Claude API (обязательный) |
| CONFLUENCE_TOKEN | Confluence PAT |
| CONFLUENCE_URL | URL Confluence |
| GITHUB_TOKEN | GitHub PAT |
| MIRO_ACCESS_TOKEN | Miro API |
| MIRO_BOARD_ID | Miro board |
| LANGFUSE_SECRET_KEY | Langfuse secret |
| LANGFUSE_PUBLIC_KEY | Langfuse public |
| LANGFUSE_BASE_URL | Langfuse URL |
| LANGFUSE_HOST | Langfuse host |

## Интеграция с fm-review-system

Все компоненты поддерживают Infisical (fallback chain):

| Компонент | Файл | Приоритет |
|-----------|------|-----------|
| Shell | `scripts/load-secrets.sh` | Infisical (Universal Auth) → keyring → .env |
| Python | `scripts/run_agent.py` | Infisical (Universal Auth) → .env |
| MCP | `scripts/mcp-confluence.sh` | Infisical (Universal Auth) → user auth → .env |
| Verify | `scripts/check-secrets.sh` | Проверка всех источников |
