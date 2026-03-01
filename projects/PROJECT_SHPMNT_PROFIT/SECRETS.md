# Secrets Management: profitability-service

> **Status:** PREPARED | **Infisical project:** `profitability-service` (TBD)

## Required Secrets (15+ keys)

| # | Secret Key | Category | Source | Required |
|---|-----------|----------|--------|----------|
| 1 | `PROFITABILITY_DB_URL` | Database | PostgreSQL | YES |
| 2 | `WORKFLOW_DB_URL` | Database | PostgreSQL | YES |
| 3 | `ANALYTICS_DB_URL` | Database | PostgreSQL | YES |
| 4 | `INTEGRATION_DB_URL` | Database | PostgreSQL | YES |
| 5 | `NOTIFICATION_DB_URL` | Database | PostgreSQL | YES |
| 6 | `REDIS_URL` | Cache | Redis | YES |
| 7 | `KAFKA_BROKERS` | Queue | Kafka | YES |
| 8 | `AD_BIND_PASSWORD` | Auth | Active Directory | YES (staging/prod) |
| 9 | `ANTHROPIC_API_KEY` | AI | Anthropic | YES |
| 10 | `ELMA_API_KEY` | Integration | ELMA BPM | YES (staging/prod) |
| 11 | `ODIN_C_API_KEY` | Integration | 1С:УТ | YES (staging/prod) |
| 12 | `TELEGRAM_BOT_TOKEN` | Notification | Telegram | YES |
| 13 | `TELEGRAM_CHAT_ID` | Notification | Telegram | YES |
| 14 | `SMTP_PASSWORD` | Notification | Email | YES (staging/prod) |
| 15 | `JWT_PRIVATE_KEY_PATH` | Auth | RSA-256 keypair | YES |
| 16 | `JWT_PUBLIC_KEY_PATH` | Auth | RSA-256 keypair | YES |
| 17 | `LANGFUSE_SECRET_KEY` | Observability | Langfuse | OPTIONAL |
| 18 | `LANGFUSE_PUBLIC_KEY` | Observability | Langfuse | OPTIONAL |
| 19 | `WMS_API_KEY` | Integration | WMS | YES (staging/prod) |

**Total: 19 keys** (15 required + 4 optional/env-specific)

## Infisical Setup

### Step 1: Create Project
```bash
# Via Infisical Web UI: https://infisical.shakhoff.com
# Project: profitability-service
# Environments: dev, staging, prod
```

### Step 2: Create Machine Identity
```bash
# Machine Identity: profitability-service-pipeline
# Auth method: Universal Auth
# TTL: 10 years (matching fm-review-system)
# Save credentials to: profitability-service/infra/infisical/.env.machine-identity
```

### Step 3: Populate Secrets (per environment)

**Dev** — local Docker values:
```bash
cd profitability-service
infisical secrets set PROFITABILITY_DB_URL="postgres://dev:dev@localhost:5432/profitability" --env=dev
infisical secrets set REDIS_URL="redis://localhost:6379/0" --env=dev
infisical secrets set KAFKA_BROKERS="localhost:9092" --env=dev
infisical secrets set INTEGRATION_MODE="mock" --env=dev
# ... etc
```

**Staging** — tunnel to corporate:
- DB: tunnel endpoint
- AD: LDAP bind credentials from IT
- ELMA/1С: staging API keys

**Prod** — corporate network:
- All real credentials
- JWT keypair: generate RS256 pair, store private key securely

### Step 4: Generate JWT Keypair
```bash
# Generate RS256 keypair for JWT signing
openssl genrsa -out jwt-rs256.key 4096
openssl rsa -in jwt-rs256.key -pubout -out jwt-rs256.key.pub
# Store private key as Infisical secret (base64 encoded)
# Store public key in repo (not secret)
```

### Step 5: Verify
```bash
./scripts/check-secrets.sh --verbose --project profitability-service
```

## Environment-Specific Notes

| Environment | Mode | External Services |
|-------------|------|-------------------|
| **Dev** | `INTEGRATION_MODE=mock` | All mocked, local Docker |
| **Staging** | `INTEGRATION_MODE=real` | Tunnel to corporate, real AD/ELMA |
| **Prod** | `INTEGRATION_MODE=real` | Corporate network, all real |

## Security Checklist

- [ ] No secrets in `.env` committed to git (`.gitignore` includes `.env`)
- [ ] Machine Identity credentials in `.env.machine-identity` (in `.gitignore`)
- [ ] JWT private key never in git
- [ ] API keys rotated monthly (Infisical rotation policy)
- [ ] `check-secrets.sh --verbose` passes in CI
- [ ] Infisical audit log enabled
