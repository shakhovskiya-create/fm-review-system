# Security & Compliance

## Security Team
| Role | Name | Email |
|------|------|-------|
| Head of InfoSec | Злой Александр Анатольевич | a.zloy@ekf.su |
| Security Engineer | Карагодин Юрий Юрьевич | yu.karagodin@ekf.su |

**JIRA project:** INFOBEZ (Информационная безопасность), 45+ issues

## Authentication & Access
- **2FA:** Multifactor (2fa.ekf.su) — mandatory for all employees
- **Methods:** Mobile app (Multifactor), SMS fallback
- **Password policy:** 10+ chars, upper+lower+special, checked against breach databases
- **Password portal:** 2fa.ekf.su/mfa/

## Personal Data Protection (ПДн)
Key documents (all stored in 1С:ДО + cloud.ekf.su):
| Document | Status |
|----------|--------|
| Политика обработки ПДн | Agreed 01.07.24 |
| СТО-12 Положение о ПДн | Agreed 29.03.24 |
| Регламент по обращениям субъектов ПДн | Agreed 05.06.24 |
| Инструкция по уничтожению ПДн | Agreed 29.02.24 |
| Положение о контроле безопасности ПДн | Agreed 05.06.24 |
| Приказ Комиссия по ИСПДн | Agreed 07.08.24 |
| Приказ ответственный за безопасность ПДн | Agreed 06.06.24 |
| Политика ИБ | Agreed 03.02.25 |

## Programs
### Кибергерои EKF (Bug Bounty)
- Internal bug bounty / security awareness program
- **What to report:** Excessive PD access, process flaws, data exchange without protection, API vulnerabilities, missing 2FA, clone/impersonation sites
- **Rewards:** 5 "Спасибо" points (simple) / branded merch (complex)
- **Report to:** a.zloy@ekf.su

### Cybersecurity Awareness
- **Фишинг:** Training materials on phishing recognition
- **Нейросети:** AI usage safety rules (don't share confidential data, verify outputs)
- **Конфиденциальность:** Confidentiality memo (NDA with contractors, information hygiene)
- **Пароли:** Password management guide

## Active Security Initiatives (JIRA: INFOBEZ)
| Task | Status | Assignee |
|------|--------|----------|
| Пилот SIEM (Kaspersky SMART) | В работе | — |
| Шифрование дисков на ПК и буках | Backlog | Карагодин Ю.Ю. |
| Проверка стойкости паролей | Готово | Карагодин Ю.Ю. |
| Блокировка неактивных учётных записей (>30 дней) | Готово | — |
| Пилот Findler (DLP) | Готово | Злой А.А. |
| Учётные данные на smb-шарах в открытом виде | Backlog | Карагодин Ю.Ю. |
| Атака на MAPI и EWS | Backlog | — |
| CIS Safeguard 3.9: Encrypt Removable Media | Сделать | Злой А.А. |
| CIS Safeguard 5.2: Use Unique Passwords | Backlog | — |
| CIS Safeguard 8.9: Centralize Audit Logs | Backlog | — |

## Compliance
- **NDA:** Required for all contractors (юр.лица and физ.лица)
- **Коммерческая тайна:** Trade secret regulation in place
- **Этический кодекс:** EKF Ethics Code
- **CIS Controls v8:** Critical Security Controls implementation (tracked in JIRA INFOBEZ)

## Key Rules
1. No confidential data in AI/neural networks
2. No work discussions in public / social media
3. Mandatory NDA with all counterparties
4. Encrypted channels only for PD exchange
5. Report suspicious activity immediately
