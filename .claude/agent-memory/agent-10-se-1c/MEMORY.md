# Agent 10 SE-1C Memory

## Key Platform Facts (confirmed in review)

### 1C:UT 10.2 Ordinary Forms -- Critical Knowledge
- `ElementsForm.Insert()` does NOT exist in ordinary forms -- cannot programmatically add elements
- All form elements must be created in the configurator (extension configurator for .cfe)
- From ordinary form module, ANY server module can be called (not only Global ones)
- `ConnectWaitHandler` works on ordinary forms in platform 8.3
- No conditional formatting object on ordinary forms -- use OnRowOutput for table fields
- No form commands object -- use Button elements with Action property
- No NotifyUser() -- use Alert(), Question(), labels on form, information register
- Full form replacement via extension is safe for UT 10.2 (vendor stopped updates 01.04.2024)

### Information Registers vs Accumulation Registers
- Information registers have: dimensions, attributes, period -- NO "resources"
- Accumulation registers have: dimensions, resources -- Period is standard (not a dimension)
- String statuses in registers = anti-pattern, always use enumerations

### Extension (.cfe) on Platform 8.3
- New objects (catalogs, documents, registers, processing) supported from 8.3.22+
- Always verify actual platform version before development
- Minimum requirement: 8.3.22 for full extension object support

## Review Patterns
- Cache invalidation: modules with reuse "per session" need explicit invalidation mechanism
- Timer interval: 60 sec creates load with 70 sessions, recommend 120 sec minimum
- Privileged modules: always document explicit operation list and add call logging
- JSON in string attributes: anti-pattern for 1C, replace with tabular sections
- Background jobs: always describe idempotency mechanism

## Project: PROJECT_SHPMNT_PROFIT
- Platform: 1C:UT 10.2 on 8.3, ordinary forms, thick client
- Users: 50-70 concurrent
- Extension: KontrolRentabelnostiOtgruzok (.cfe)
- Estimate reviewed: 3675h (recommended 3915h, +6.5%)
- Review date: 2026-02-26, verdict: APPROVED WITH CONDITIONS (4C/5H/6M/3L)
