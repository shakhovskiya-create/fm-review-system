# Infrastructure & Architecture

## 1C Server Landscape

### Production
| Server | IP | Role | Systems |
|--------|-----|------|---------|
| 1C-EKF-APP-01 | 172.20.0.51 | Main 1C app server | УТ, БП, ЗУП, ДО, ERP Ставрово, УХ |
| 1capp-mi / 1C-APP-MI | 172.20.0.11 | Alexandrov 1C app server | ERP Александров, ДО Александров |
| 1c-mi-db | 172.20.0.10 | Alexandrov DB server | PostgreSQL for Alexandrov |
| PLM-1C | - | PLM server | Appius-PLM |
| 1c-nalog | - | Tax monitoring | 1С:БП Витрина (налоговый мониторинг) |

### Production (additional)
| Server | IP | Role |
|--------|-----|------|
| 1C-app-ekf-02 | — | 1C app server (Windows Task Scheduler: Restart1C, обновления) |

### Development / Test
| Server | IP | Role |
|--------|-----|------|
| 1C-DEVAPP01 | - | Dev server 1 (actual copies of БП, УТ) |
| 1C-DEVAPP02 | - | Dev server 2 (actual copies of ERP Ставрово, ERP Александров, УХ dev) |
| 1c-devsql01 | — | Dev SQL server (ut_actual_copy, ekf_actual_copy; MaintenancePlan) |
| devappmi | 192.168.6.36 | Alexandrov dev app server |
| dev1cmi | 192.168.6.35 | Alexandrov dev DB |

### 1C Database List
| # | Name | Connection | Org |
|---|------|------------|-----|
| 1 | 1С УТ | Srvr="1C-EKF-APP-01";Ref="EKF" | Электрорешения |
| 2 | 1С БП | Srvr="1C-EKF-APP-01";Ref="acc_ee" | Электрорешения |
| 3 | 1С БП Витрина | Srvr="1c-nalog";Ref="acc_ee_mon_pub" | Электрорешения |
| 4 | 1С БП (KZ) | Srvr="1C-EKF-APP-01";Ref="acc_kz" | - |
| 5 | 1С БП (UZ) | Srvr="1C-EKF-APP-01";Ref="acc_uzb" | - |
| 6 | 1С ЗУП | Srvr="1C-EKF-APP-01";Ref="hrm_3_ekf" | Электрорешения |
| 7 | 1С ERP ЦЭР | Srvr="1C-EKF-APP-01";Ref="ERP_DigitalER" | ЦЭР |
| 8 | 1С ERP MENA | https://ekf.erp.firstbit.ae/ekf/ | - |
| 9 | 1С ERP Александров | Srvr="1c-ekf-app-01";Ref="mes" | Филиал |
| 10 | 1С ERP Ставрово | Srvr="1c-ekf-app-01";Ref="ERP_Stavrovo" | Филиал |
| 11 | 1С ЗУП Александров | Srvr="1C-EKF-APP-01";Ref="zup3_fer" | Филиал |
| 12 | 1С ДО | Srvr="1c-ekf-app-01";Ref="1c_doc" | - |
| 14 | 1С УХ (TEST) | Srvr="1C-DEVAPP02";Ref="UH_dev" | - |
| 15 | 1С УХ (PROD) | Srvr="1C-EKF-APP-01";Ref="UH_EKF" | - |
| 16 | Appius PLM | Srvr="PLM-1C";Ref="PLM-NEW" | - |

## Web Infrastructure
| Service | Prod IP | Dev |
|---------|---------|-----|
| ekfgroup.com | 51.250.3.21 | 78.155.208.20:22957/22958 |
| market.ekfgroup.com | 84.252.140.0 | 78.155.208.20:22957/22958 |
| IMS | 188.127.236.199 | 78.155.208.20:22957/22958 |
| QC Portal | 188.127.236.199 | 78.155.208.20:22957/22958 |
| EKF.ID | 188.127.236.199 | - |
| univer.ekfgroup | 188.127.236.199 | - |

## Data Platform (DWH)
- **Hasura:** GraphQL API layer (DEV + PROD instances)
- **dbt:** Data transformation
- **Airflow:** Orchestration (http://51.250.3.20:8080), DAGs in gitlab.ekf.su
- **S3 (Yandex Cloud):** Object storage
- **MSSQL (MDS):** BI / legacy analytics — temporary data source before Kafka migration
- **PostgreSQL:** Primary database cluster (known incident history with degradation)
- **DQ monitoring:** dq_stats.table_source_comparing in PostgreSQL (source row count vs loaded)

### DWH Monitoring
- **Airflow task alerts:** on_failure_callback → Telegram chat "EKF Alerts"
- **Airflow health check:** Yandex Cloud function (d4efgdr0vngggeibkqe7), checks /health endpoint
- **DQ alerts:** Telegram chat "EKF Alerts Dev" (separate from Airflow alerts)
- **Telegram chats:** EKF Alerts, EKF Alerts Dev

## Other Infrastructure
| Service | IP/Location |
|---------|------------|
| Bitrix24 | 192.168.6.67 (prod), .57 / .119 (dev) |
| VDI (Horizon) | 172.20.0.150 |
| Email (Exchange) | 172.20.0.176 |
| ELMA | 172.20.0.226 |
| LeadWMS | 172.20.0.210 |
| CRM (B2C) | 94.26.230.86 |
| SDO | 172.20.0.52 |
| Альта.Максимум | 192.168.6.7 |
| Appius-PLM | 192.168.6.19 |

## Target Architecture (TO-BE)
Source: Confluence "Целевая архитектура (версия 2025.02.20)", id: 2303097

### Storage
- **Database decomposition:** Separate schemas/databases for isolation
- **Valkey:** Caching for high-load services (catalog filters, cart state)
- **API Gateway + nginx:** Intermediate request caching to reduce backend load

### Integration Bus
- **Kafka:** Main data bus — scalable via partitions, topic-based routing
- **Adapters:** HTTP (REST), JDBC (relational DB), S3 (object storage)
- **ETL:** Apache Airflow
- **Schema Registry:** + Git + Confluence — centralized data contract management, version rollback
- **Data format:** JSON standard for all exchanges, contracts pre-agreed, validation in adapters
- **1C inter-config exchange:** Native конвертация данных or HTTP services

### Kafka Topics (Org Structure)
Source: Confluence "Архитектура организационной структуры в Kafka", id: 48202324
| Kafka Topic | Source (1C) | Purpose |
|-------------|-------------|---------|
| hrm.references.departments | ЗУП.Справочник.ПодразделенияОрганизаций | Department hierarchy (via Parent field) |
| hrm.queries.department_chiefs_last | ЗУП.Справочник.РуководителиПодразделений | Department chiefs |
| hrm.references.positions | ЗУП.Справочник.Должности | Position catalog |
| hrm.information_registers.user_positions_last | ЗУП.РегистрСведений.КадроваяИсторияСотрудников | Current employee → position → department → org |

Organization GUID (Электрорешения): `10699588-aa76-4347-89bc-9e109eef5d68`

### Monitoring & Observability
- **Prometheus + Grafana:** Metrics collection and visualization
- **Sentry:** Error and exception tracking
- **Jaeger Tracing:** Distributed tracing (Kafka, backend, frontend)
- **ELK stack:** Log aggregation, indexing, analysis (structured logs with context)
- **Health checks:** All services expose health, technical metrics, business metrics, logs

### Authorization
- **Keycloak:** External user auth (EKF.ID) — stores name, phone, city; services enrich per-service data
- **LDAP ADFS:** Employee auth with 2FA (Multifactor)

## Architecture Pages (Confluence)
| Page | ID | Description |
|------|----|-------------|
| Схема интеграции AS IS | 2294052 | Current integration map (PDF attachment) |
| Целевая архитектура (2025.02.20) | 2303097 | Target architecture (drawio + description) |
| Схема архитектуры TO BE | 15368306 | Target architecture (old version) |
| Архитектура данных | 49450863 | DWH architecture (AR decisions, monitoring, VPN) |
| Архитектура оргструктуры в Kafka | 48202324 | Kafka org structure topics |
| PlantUML Functions | 21301910 | Architecture diagramming |

## Backup & Recovery
Source: Confluence "1C DevOps", id: 86049260

| Service | IP | Purpose |
|---------|-----|---------|
| Veeam Backup Enterprise Manager | 172.20.0.12:9443 | VM and SQL backup management |
| alwayslsr01 | — | SQL Server Always On (source for DB backups) |
| 1c-devsql01 | — | Dev SQL (target for restores, has MaintenancePlan) |

**1C DB restore procedure:**
1. Veeam → Restore SQL DB to alternative location (or alwayslsr01 → backup device → create backup)
2. 1c-devsql01: check MaintenancePlan completed for ut_actual_copy
3. MS SQL Management Studio → Restore → source: DB or device (E:\Backup), overwrite existing, close connections
4. 1C Admin Console → Register restored DB

**DB creation standard:** Data auto-growth 1024 MB, Log auto-growth 512 MB

## 1C DevOps Automation
- **Jenkins:** "1C → run epf_ut" — data cleanup for database connections
- **1C-app-ekf-02 Task Scheduler:** Restart1C (scheduled server restarts), updates, recovery tasks

## Security Infrastructure
- **2FA:** Multifactor (2fa.ekf.su) — mobile app + SMS (via LDAP ADFS)
- **Keycloak:** External user auth for EKF.ID (stores name, phone, city)
- **VPN:** Access for contractors, remote workers, and DWH project
- **Cloud storage:** cloud.ekf.su (NextCloud)
- **Git:** gitlab.ekf.su (internal), GitHub (external)
- **Video:** Контур.Толк (ekfgroup.ktalk.ru)
