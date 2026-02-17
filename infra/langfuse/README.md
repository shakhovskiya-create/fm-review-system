# Langfuse v3 Self-Hosted

Observability для FM Review Agents. Трекинг стоимости, токенов, латентности per-agent.

## Требования

- Docker + Docker Compose
- 4 vCPU, 16 GB RAM, 100 GB storage
- Порт 3000 (UI)

## Запуск

```bash
cd infra/langfuse

# 1. Создать конфигурацию
cp .env.langfuse.example .env.langfuse

# 2. Сгенерировать секреты
sed -i "s/^ENCRYPTION_KEY=$/ENCRYPTION_KEY=$(openssl rand -hex 32)/" .env.langfuse
sed -i "s/^NEXTAUTH_SECRET=$/NEXTAUTH_SECRET=$(openssl rand -hex 32)/" .env.langfuse
sed -i "s/^SALT=$/SALT=$(openssl rand -hex 16)/" .env.langfuse
sed -i "s/^POSTGRES_PASSWORD=$/POSTGRES_PASSWORD=$(openssl rand -hex 16)/" .env.langfuse
sed -i "s/^REDIS_AUTH=$/REDIS_AUTH=$(openssl rand -hex 16)/" .env.langfuse
sed -i "s/^MINIO_ROOT_PASSWORD=$/MINIO_ROOT_PASSWORD=$(openssl rand -hex 16)/" .env.langfuse

# 3. Запустить
docker compose --env-file .env.langfuse up -d

# 4. Открыть UI
open http://localhost:3000
```

## Получение API ключей

1. Открыть http://localhost:3000
2. Войти (admin@local / пароль из .env.langfuse)
3. Settings > API Keys > Create
4. Скопировать `pk-lf-...` и `sk-lf-...` в `.env` проекта:

```bash
# В корне fm-review-system/.env добавить:
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=http://localhost:3000
```

## Альтернатива: Langfuse Cloud

Если нет сервера с 16 GB RAM - используйте Langfuse Cloud (бесплатный Hobby tier, 50k units/месяц):

1. Зарегистрироваться на https://cloud.langfuse.com
2. Создать проект "fm-review-agents"
3. Settings > API Keys > скопировать ключи в `.env`:

```bash
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=https://cloud.langfuse.com
```
