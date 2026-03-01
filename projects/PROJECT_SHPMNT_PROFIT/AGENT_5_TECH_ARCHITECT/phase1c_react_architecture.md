# Phase 1C: React Frontend Architecture

**Проект:** FM-LS-PROFIT (Контроль рентабельности отгрузок по ЛС)
**Версия ФМ:** 1.0.7
**Дата:** 02.03.2026
**Автор:** Шаховский А.С.
**Платформа:** React (Next.js 15 App Router) + Tailwind CSS
**Domain Model:** см. `phase1a_domain_model.md`
**Go Architecture:** см. `phase1b_go_architecture.md`

---

## Содержание

1. [Page Hierarchy and Routing](#1-page-hierarchy-and-routing)
2. [Dashboard](#2-dashboard)
3. [Shipment Analysis](#3-shipment-analysis)
4. [Approval Queue](#4-approval-queue)
5. [AI Insights](#5-ai-insights)
6. [Reports](#6-reports)
7. [Settings](#7-settings)
8. [Component Library (Atomic Design)](#8-component-library-atomic-design)
9. [API Client Architecture](#9-api-client-architecture)
10. [Auth Flow](#10-auth-flow)
11. [State Management](#11-state-management)
12. [Error Handling Strategy](#12-error-handling-strategy)
13. [Responsive Design](#13-responsive-design)
14. [Accessibility (a11y)](#14-accessibility-a11y)
15. [Performance Budget](#15-performance-budget)
16. [Traceability Matrix](#16-traceability-matrix)

---

## 1. Page Hierarchy and Routing

### 1.1. Route Structure (Next.js App Router)

```
app/
  layout.tsx                    # Root layout: AuthProvider, QueryProvider, ThemeProvider
  (auth)/
    login/page.tsx              # /login -- AD authentication
    logout/page.tsx             # /logout -- session cleanup
  (protected)/
    layout.tsx                  # Sidebar + TopBar + RoleGuard
    dashboard/page.tsx          # /dashboard -- main KPI dashboard
    shipments/
      page.tsx                  # /shipments -- shipment analysis table
      [id]/page.tsx             # /shipments/:id -- shipment detail (drawer)
    approvals/
      page.tsx                  # /approvals -- approval queue
      [id]/page.tsx             # /approvals/:id -- approval detail
    insights/
      page.tsx                  # /insights -- AI anomaly dashboard
      [id]/page.tsx             # /insights/:id -- investigation detail
      ask/page.tsx              # /insights/ask -- AI chat interface
    reports/
      page.tsx                  # /reports -- report catalog
      [reportId]/page.tsx       # /reports/:reportId -- specific report
    settings/
      page.tsx                  # /settings -- admin settings
      thresholds/page.tsx       # /settings/thresholds -- threshold configuration
      roles/page.tsx            # /settings/roles -- role management
      notifications/page.tsx    # /settings/notifications -- notification preferences
      features/page.tsx         # /settings/features -- feature flags
      audit/page.tsx            # /settings/audit -- audit log viewer
  api/                          # API routes (BFF, if needed)
    auth/[...nextauth]/route.ts # Auth endpoints
  not-found.tsx                 # 404
  error.tsx                     # Global error boundary
  loading.tsx                   # Global loading skeleton
```

### 1.2. Navigation Sidebar

```
+------------------------------------------+
| [Logo] EKF Profitability Control         |
|                                          |
| -- Основное --                           |
|  [icon] Дашборд            /dashboard    |
|  [icon] Отгрузки           /shipments    |
|  [icon] Согласование       /approvals    |  (badge: queue count)
|  [icon] Аналитика          /insights     |  (badge: open anomalies)
|  [icon] Отчеты             /reports      |
|                                          |
| -- Администрирование --                  |  (visible: fd only)
|  [icon] Настройки          /settings     |
|                                          |
| -- Пользователь --                       |
|  [avatar] Иванов И.И.                    |
|  [role]   Менеджер по продажам           |
|  [btn]    Выход                          |
+------------------------------------------+
```

### 1.3. Role-Based Page Access

| Route | manager | rbu | dp | gd | fd |
|-------|---------|-----|----|----|-----|
| `/dashboard` | read | read | read | read | read+admin |
| `/shipments` | read+create | read | read | read | read |
| `/approvals` | read (own) | approve L1-2 | approve L2-3 | approve L3-4 | read |
| `/insights` | -- | read | read+resolve | read+resolve | read+resolve+ask |
| `/reports` | own reports | BU reports | all reports | all reports | all reports+admin |
| `/settings` | notifications only | -- | -- | -- | full access |

### 1.4. Default Landing by Role

| Role | Default Route | Reason |
|------|--------------|--------|
| manager | `/dashboard` | Overview of own LS and shipments |
| rbu | `/approvals` | Primary task: process approval queue |
| dp | `/approvals` | Primary task: process approval queue |
| gd | `/approvals` | Primary task: process approval queue |
| fd | `/dashboard` | Financial overview and monitoring |

---

## 2. Dashboard

### 2.1. Wireframe

```
+============================================================================+
|  [TopBar: search | notifications (bell + count) | user avatar + role]      |
+============================================================================+
|  +--KPI Row (4 cards)--------------------------------------------------+   |
|  |  +--Card--+  +--Card--+  +--Card---+  +--Card--+                   |   |
|  |  | Общая  |  | Тренд  |  | Аномалии|  | SLA    |                   |   |
|  |  | рент.  |  |   ^    |  |   3     |  | соотв. |                   |   |
|  |  | 12.4%  |  | +0.3%  |  | открытых|  | 94.2%  |                   |   |
|  |  +--------+  +--------+  +---------+  +--------+                   |   |
|  +------------------------------------------------------------------+  |   |
|                                                                         |   |
|  +--Chart (AreaChart, 30 days)-------+  +--Alert Feed-----------------+ |   |
|  |                                    |  |  [!] Аномалия: клиент ООО  | |   |
|  |    ___/\___    ___/\___            |  |     "Фаворит" z=2.8        | |   |
|  |   /        \  /        \           |  |  [!] SLA breach: заявка    | |   |
|  |  /          \/          \--        |  |     #1234, 2ч просрочка    | |   |
|  |                                    |  |  [i] Автосогласовано: 15   | |   |
|  |  [30д] [90д] [180д]               |  |     заявок за сегодня      | |   |
|  +------------------------------------+  |  [!] НПСС устарела: 12    | |   |
|                                          |     товаров > 90 дней      | |   |
|  +--Quick Filters---------------------+ |  [i] ELMA fallback activated| |   |
|  | Период: [Послед. 30 дн.  v]        | |  ...                       | |   |
|  | БЮ:     [Все подразделения v]      | |  (latest 10)               | |   |
|  | Менеджер:[Все менеджеры    v]      | |  [Показать все ->]          | |   |
|  +-------------------------------------+ +----------------------------+ |   |
+=========================================================================+
```

### 2.2. Component Tree

```
DashboardPage
  +-- KPIRow
  |     +-- KPICard (totalProfitability)
  |     |     +-- Badge (trend: up/down/neutral)
  |     |     +-- Sparkline (7-day mini chart)
  |     +-- KPICard (trendChange)
  |     |     +-- TrendArrow (direction + value)
  |     +-- KPICard (anomalyCount)
  |     |     +-- Badge (severity color: red/yellow/green)
  |     +-- KPICard (slaCompliance)
  |           +-- CircularProgress (percentage ring)
  +-- DashboardGrid (2-column layout)
  |     +-- ProfitabilityChart
  |     |     +-- Recharts AreaChart
  |     |     +-- ChartControls (period: 30d/90d/180d)
  |     |     +-- ChartTooltip (date, value, delta)
  |     +-- AlertFeed
  |           +-- AlertItem (repeated, max 10)
  |           |     +-- SeverityIcon (critical/high/medium/info)
  |           |     +-- AlertText (description)
  |           |     +-- TimeAgo (relative timestamp)
  |           +-- ShowAllLink -> /insights
  +-- QuickFilters
        +-- DateRangePicker (period selector)
        +-- Select (business unit)
        +-- Select (manager) -- visible to rbu/dp/gd/fd only
```

### 2.3. Data Flow

```
DashboardPage (Server Component -- initial data)
  |
  +-- GET /api/v1/dashboard/manager         --> KPIRow (profitability, trend)
  |   TanStack Query key: ['dashboard', 'manager', filters]
  |   Refetch: 60 seconds (polling)
  |
  +-- GET /api/v1/kpi/manager/{id}          --> KPICard (slaCompliance)
  |   TanStack Query key: ['kpi', 'manager', userId]
  |   Refetch: 5 minutes
  |
  +-- GET /api/v1/anomalies?status=open&per_page=10  --> AlertFeed
  |   TanStack Query key: ['anomalies', 'open', { limit: 10 }]
  |   Refetch: 2 minutes
  |
  +-- GET /api/v1/reports/daily-efficiency   --> ProfitabilityChart (30d)
  |   TanStack Query key: ['reports', 'daily-efficiency', period]
  |   Refetch: 5 minutes
  |
  +-- GET /api/v1/approvals/queue/count      --> notification badge
      TanStack Query key: ['approvals', 'queue', 'count']
      Refetch: 30 seconds (polling)
```

### 2.4. State Management

```typescript
// stores/dashboard.ts (Zustand)
interface DashboardState {
  filters: {
    period: '30d' | '90d' | '180d';
    businessUnitId: string | null;
    managerId: string | null;
  };
  setFilter: (key: string, value: string | null) => void;
  resetFilters: () => void;
}
```

### 2.5. Role-Specific Views

| Role | KPI Row Content | Chart | Alert Feed |
|------|----------------|-------|------------|
| manager | Own LS profitability, own trend, own anomalies, own SLA | Own shipments trend | Own alerts only |
| rbu | BU profitability, BU trend, BU anomalies, BU SLA | BU aggregate | BU alerts + workload |
| dp | All BU profitability, trend, anomalies, SLA | All BU aggregate | All BU + escalations |
| gd | Company profitability, trend, anomalies, SLA | Company aggregate | Escalations + GD queue |
| fd | Company profitability, trend, AI costs, ELMA status | Company + AI costs | All + system health |

---

## 3. Shipment Analysis

### 3.1. Wireframe

```
+==========================================================================+
| Отгрузки                                         [Создать заказ v]       |
+==========================================================================+
| +--Filters (collapsible)-----------------------------------------+       |
| | Клиент: [____________]  Менеджер: [____________]               |       |
| | Период: [__/__/____] - [__/__/____]  Статус: [Все       v]    |       |
| | Рентабельность: [===|====|====] 0%----50%---100%               |       |
| | [Применить]  [Сбросить]  Найдено: 1 247 записей               |       |
| +----------------------------------------------------------------+       |
|                                                                          |
| +--DataTable----------------------------------------------------------+  |
| | # | ЛС       | Клиент        |Сумма,т.р.| Маржа%| Статус     | >  |  |
| |---|----------|---------------|----------|-------|------------|-----|  |
| | 1 | ЛС-00123 | ООО "Фаворит"| 1 250    | 8.3%  | Согласован | [>]|  |
| | 2 | ЛС-00456 | ИП Иванов    |   340    | 12.1% | На согл.   | [>]|  |
| | 3 | ЛС-00789 | ООО "Альфа"  | 5 680    | -2.4% | Отклонен   | [>]|  |
| | 4 | ЛС-01012 | АО "Строй+"  |   890    | 15.7% | Черновик   | [>]|  |
| |...|..........|...............|..........|.......|............|.....|  |
| +------------------------------------------------------------------+  |
| | << 1 2 3 ... 52 >> | Показывать: [25 v] | Итого: 1 247          |  |
| +------------------------------------------------------------------+  |
|                                                                          |
| +--Drill-Down Drawer (slide from right)-----------------------------+    |
| | [X] Заказ #ЗКК-00456 по ЛС-00456                                |    |
| |                                                                    |    |
| | Клиент: ИП Иванов             Менеджер: Петров А.В.              |    |
| | Сумма: 340 000 руб.           Дата: 15.02.2026                   |    |
| |                                                                    |    |
| | -- Расчет рентабельности --                                       |    |
| | Плановая (ЛС):     15.0%                                         |    |
| | Заказ:              12.1%     [=======---] -2.9 п.п.             |    |
| | Накопл.+Заказ:      13.5%     [========--] -1.5 п.п.             |    |
| | Остаток:            16.2%     [=========+] +1.2 п.п.             |    |
| | Отклонение:         1.5 п.п.  Уровень: РБЮ                      |    |
| |                                                                    |    |
| | -- Позиции заказа --                                              |    |
| | | Товар         | Кол-во | Цена   | НПСС   | Маржа% |           |    |
| | |---------------|--------|--------|--------|--------|           |    |
| | | Кабель КВВГнг |  100м  | 85 руб | 72 руб | 15.3%  |           |    |
| | | Автомат 16А   |   50   | 340р   | 310р   | 8.8%   |           |    |
| | | ...           |        |        |        |        |           |    |
| |                                                                    |    |
| | -- История --                                                     |    |
| | [timeline] 15.02 Создан -> 15.02 Расчет -> 16.02 На согл.       |    |
| | [timeline] 16.02 РБЮ: Одобрено (Сидоров)                        |    |
| |                                                                    |    |
| | [Согласование]  [Корректировка цены]  [Экстренное]               |    |
| +--------------------------------------------------------------------+   |
+==========================================================================+
```

### 3.2. Component Tree

```
ShipmentAnalysisPage
  +-- PageHeader
  |     +-- Title ("Отгрузки")
  |     +-- CreateButton (role: manager only)
  +-- FilterBar (collapsible)
  |     +-- ClientSearch (debounced autocomplete)
  |     +-- ManagerSelect (rbu/dp/gd/fd only)
  |     +-- DateRangePicker
  |     +-- StatusSelect (multi-select)
  |     +-- ProfitabilityRangeSlider
  |     +-- FilterActions (Apply, Reset, ResultCount)
  +-- DataTable
  |     +-- TableHeader (sortable columns)
  |     +-- TableBody
  |     |     +-- ShipmentRow (repeated)
  |     |           +-- ProfitabilityBadge (color-coded %)
  |     |           +-- StatusBadge
  |     |           +-- DrillDownButton
  |     +-- TablePagination (cursor-based)
  |           +-- PageSelector
  |           +-- PerPageSelect (10/25/50/100)
  |           +-- TotalCount
  +-- ShipmentDrawer (Sheet component, slide from right)
        +-- DrawerHeader (shipment ID, close button)
        +-- ShipmentSummary
        |     +-- ClientInfo
        |     +-- ManagerInfo
        |     +-- AmountDisplay
        +-- ProfitabilityBreakdown
        |     +-- ProfitabilityBar (planned vs actual, visual)
        |     +-- DeviationIndicator (pp + direction arrow)
        |     +-- ApprovalLevelBadge (auto/rbu/dp/gd)
        +-- LineItemsTable
        |     +-- LineItemRow (product, qty, price, npss, margin)
        |     +-- BlockedItemWarning (NPSS=0 or Price=0)
        +-- ShipmentTimeline
        |     +-- TimelineStep (status changes, chronological)
        +-- ShipmentActions
              +-- ApprovalButton (if pending_approval, role-appropriate)
              +-- CorrectionButton (if rejected, manager only, iteration < 5)
              +-- EmergencyButton (manager only)
```

### 3.3. Data Flow

```
ShipmentAnalysisPage
  |
  +-- GET /api/v1/local-estimates/{id}/shipments    --> DataTable
  |   Query key: ['shipments', lsId, { status, page, per_page, sort }]
  |   Pagination: cursor-based (cursor = last shipment ID)
  |   Sort: server-side (column + direction)
  |
  +-- GET /api/v1/shipments/{id}                    --> ShipmentDrawer
  |   Query key: ['shipments', shipmentId]
  |   Enabled: only when drawer is open
  |
  +-- GET /api/v1/shipments/{id}/profitability      --> ProfitabilityBreakdown
  |   Query key: ['shipments', shipmentId, 'profitability']
  |
  +-- POST /api/v1/shipments/{id}/calculate         --> recalculate action
  |   Mutation key: ['shipments', 'calculate']
  |   Invalidates: ['shipments', shipmentId, 'profitability']
  |
  +-- POST /api/v1/approvals                        --> submit for approval
  |   Mutation key: ['approvals', 'create']
  |   Invalidates: ['shipments', shipmentId], ['approvals', 'queue', 'count']
  |
  +-- POST /api/v1/approvals/{id}/correct           --> price correction
      Mutation key: ['approvals', 'correct']
      Invalidates: ['approvals', processId], ['shipments', shipmentId]
```

### 3.4. Cursor-Based Pagination

```typescript
// hooks/useShipments.ts
export function useShipments(filters: ShipmentFilters) {
  return useInfiniteQuery({
    queryKey: ['shipments', filters],
    queryFn: async ({ pageParam }) => {
      const params = new URLSearchParams({
        ...filters,
        per_page: '25',
        ...(pageParam ? { cursor: pageParam } : {}),
      });
      const res = await apiClient.get(`/api/v1/local-estimates/${filters.lsId}/shipments?${params}`);
      return res.data;
    },
    getNextPageParam: (lastPage) => lastPage.nextCursor ?? undefined,
    initialPageParam: undefined as string | undefined,
    staleTime: 30_000, // 30s
  });
}
```

### 3.5. Scalability (50-70 Concurrent Users)

| Concern | Solution |
|---------|----------|
| Large datasets | Cursor-based pagination (no OFFSET), server-side sort/filter |
| Concurrent edits | Optimistic locking (version field), conflict toast on 409 |
| Stale data | TanStack Query refetchOnWindowFocus + 30s staleTime |
| Network efficiency | Selective field loading (no line items in list view) |
| Rendering perf | React.memo on rows, virtualized table for 100+ rows |

---

## 4. Approval Queue

### 4.1. Wireframe

```
+==========================================================================+
| Очередь согласования              [Выбрано: 3]  [Согласовать v] [Откл.]  |
+==========================================================================+
| +--Sorting/Filters------+  +--Queue Stats-----------------------+        |
| | Сортировка: [SLA (сроч.)]| | Всего: 28 | Срочных: 5 | Просрочено: 2 | |
| | Уровень:   [Мой уровень] | | Средн. время: 4.2ч                    | |
| | Приоритет: [Все        ] | +---------------------------------------+ |
| +-----------------------+                                                |
|                                                                          |
| +--Task Cards------------------------------------------------------------+
| | +--Card (URGENT)-------------------------------------------------+    |
| | | [!] SLA: 0ч 45мин осталось              Приоритет: P1          |    |
| | | ЛС-00789 / Заказ #ЗКК-00789            Отклонение: 18.5 п.п.  |    |
| | | Клиент: ООО "Альфа"                     Сумма: 5 680 000 руб.  |    |
| | | Менеджер: Козлов С.П.                   Уровень: ДП            |    |
| | | Рекомендация: Одобрить с корректировкой (снижение маржи в пределах|   |
| | |              нормы для стратегического клиента)                  |    |
| | | [checkbox] [Одобрить] [Откл.с комм.] [Корректировка] [Детали]   |    |
| | +------------------------------------------------------------------+   |
| |                                                                        |
| | +--Card (NORMAL)--------------------------------------------------+   |
| | | SLA: 18ч 30мин осталось                 Приоритет: P2           |   |
| | | ЛС-00123 / Заказ #ЗКК-00123            Отклонение: 3.2 п.п.   |   |
| | | Клиент: ООО "Фаворит"                  Сумма: 1 250 000 руб.  |   |
| | | Менеджер: Петров А.В.                   Уровень: РБЮ           |   |
| | | [checkbox] [Одобрить] [Откл.с комм.] [Корректировка] [Детали]  |   |
| | +-----------------------------------------------------------------+   |
| | ...                                                                    |
| +------------------------------------------------------------------------+
+==========================================================================+
```

### 4.2. Component Tree

```
ApprovalQueuePage
  +-- PageHeader
  |     +-- Title ("Очередь согласования")
  |     +-- BatchActions (visible when items selected)
  |           +-- SelectedCount
  |           +-- BatchApproveButton
  |           +-- BatchRejectButton
  +-- QueueControls
  |     +-- SortSelect (sla_urgency, deviation_desc, amount_desc, created_at)
  |     +-- LevelFilter (auto-set to user's level, overridable)
  |     +-- PriorityFilter (P1/P2/all)
  +-- QueueStats
  |     +-- StatBadge (total)
  |     +-- StatBadge (urgent, color: red)
  |     +-- StatBadge (overdue, color: dark red)
  |     +-- StatBadge (avgTime)
  +-- TaskCardList
  |     +-- TaskCard (repeated)
  |           +-- SLATimer (countdown, color: green->yellow->red)
  |           +-- ShipmentBrief (ls, order, client, manager)
  |           +-- DeviationDisplay (pp + level badge)
  |           +-- AmountDisplay (formatted)
  |           +-- RecommendedAction (AI-generated, if available)
  |           +-- CardActions
  |           |     +-- Checkbox (for batch selection)
  |           |     +-- ApproveButton
  |           |     +-- RejectWithCommentButton -> modal
  |           |     +-- CorrectionButton -> modal
  |           |     +-- DetailsLink -> /approvals/:id
  |           +-- SLAProgressBar (visual: time elapsed / total)
  +-- EmptyState (if queue is empty: "Нет заявок на согласование")
```

### 4.3. Data Flow

```
ApprovalQueuePage
  |
  +-- GET /api/v1/approvals/queue                   --> TaskCardList
  |   Query key: ['approvals', 'queue', { priority, level, sort }]
  |   Refetch: 15 seconds (real-time queue)
  |   Sort default: SLA urgency (most urgent first)
  |
  +-- GET /api/v1/approvals/queue/count             --> QueueStats
  |   Query key: ['approvals', 'queue', 'count']
  |   Refetch: 15 seconds
  |
  +-- GET /api/v1/approvals/{id}                    --> TaskCard details
  |   Query key: ['approvals', processId]
  |   Prefetch on hover (staleTime: 60s)
  |
  +-- POST /api/v1/approvals/{id}/decide            --> Approve/Reject
  |   Mutation key: ['approvals', 'decide']
  |   Optimistic update: remove card from list
  |   Invalidates: ['approvals', 'queue'], ['approvals', 'queue', 'count']
  |
  +-- POST /api/v1/approvals/{id}/correct           --> Price correction
  |   Mutation key: ['approvals', 'correct']
  |   Invalidates: ['approvals', processId]
  |
  +-- GET /api/v1/approvals/sla/{id}                --> SLATimer
      Query key: ['approvals', 'sla', processId]
      Refetch: 60 seconds (SLA countdown)
```

### 4.4. Approval Matrix and Role-Based View

| Role | Visible Levels | Can Approve | Can Reject | Can Correct | Batch Ops |
|------|---------------|-------------|------------|-------------|-----------|
| manager | Own submissions | -- | -- | Yes (iteration < 5) | -- |
| rbu | Level 1 (RBU), Level 2 (DRP escalation) | L1-L2 | L1-L2 | Request correction | Yes |
| dp | Level 2 (DP) | L2 | L2 | -- | Yes |
| gd | Level 3 (GD) | L3 | L3 | -- | Yes |
| fd | All (read-only) | -- | -- | -- | -- |

### 4.5. Batch Operations

```typescript
// Batch approve: all selected items with deviation < threshold
async function batchApprove(selectedIds: string[], comment?: string) {
  const results = await Promise.allSettled(
    selectedIds.map(id =>
      apiClient.post(`/api/v1/approvals/${id}/decide`, {
        decision: 'approved',
        comment: comment || 'Массовое согласование',
      })
    )
  );
  const failed = results.filter(r => r.status === 'rejected');
  if (failed.length > 0) {
    toast.warning(`Согласовано: ${results.length - failed.length}, ошибки: ${failed.length}`);
  } else {
    toast.success(`Согласовано: ${results.length} заявок`);
  }
  queryClient.invalidateQueries({ queryKey: ['approvals', 'queue'] });
}
```

### 4.6. SLA Timer Component

```typescript
// components/molecules/SLATimer.tsx
interface SLATimerProps {
  deadline: string;      // ISO 8601
  startedAt: string;     // ISO 8601
  slaHours: number;
  level: ApprovalLevel;
}

// Color logic:
// > 50% remaining: green (#22c55e)
// 20-50% remaining: yellow (#eab308)
// < 20% remaining: red (#ef4444)
// Breached: dark red (#991b1b) + pulsing animation
//
// Format:
// > 24h: "2д 14ч"
// > 1h: "14ч 30мин"
// < 1h: "45мин" (bold, animated pulse if < 20min)
// Breached: "Просрочено на 2ч 15мин"
```

### 4.7. Rejection with Comment Modal

```
+--------------------------------------+
|  Отклонение заявки                   |
|                                      |
|  Заказ: #ЗКК-00789                  |
|  Отклонение: 18.5 п.п.              |
|                                      |
|  Причина отклонения: *               |
|  +--------------------------------+  |
|  | [textarea, min 50 chars]       |  |
|  |                                |  |
|  +--------------------------------+  |
|  Минимум 50 символов (32/50)        |
|                                      |
|  [Отклонить]        [Отмена]        |
+--------------------------------------+
```

---

## 5. AI Insights

### 5.1. Wireframe

```
+==========================================================================+
| Аналитика (AI)                     [Задать вопрос ->] [Стоимость AI ->]  |
+==========================================================================+
| +--Summary Row-----+  +--Level Filter--------+  +--Status Filter------+ |
| | Всего: 47        |  | [x] L1 (детерминист.)|  | [x] Открытые        | |
| | Открытых: 12     |  | [x] L2 (интерпрет.) |  | [ ] В расследовании  | |
| | В расслед.: 3    |  | [ ] L3 (расслед.)   |  | [ ] Решено           | |
| | Решено: 32       |  +---------------------+  | [ ] Ложное срабат.   | |
| +------------------+                            +----------------------+ |
|                                                                          |
| +--Anomaly Cards---------------------------------------------------------+
| | +--Card (CRITICAL, Level 3)--------------------------------------------+
| | | [!!!] z-score: 4.2         Confidence: 0.92                         |
| | | Систематическое снижение маржи по клиенту ООО "Альфа"               |
| | | Затронуто: 5 ЛС, общая сумма 12.4 млн руб.                         |
| | |                                                                      |
| | | Рекомендация: Пересмотреть условия договора. Клиент систематически   |
| | | выбирает низкомаржинальные позиции (cherry-picking).                 |
| | |                                                                      |
| | | Расследование: [Завершено, 7 шагов]  Обнаружено: 15.02.2026         |
| | | [Подробнее]  [Отметить решенной]  [Ложное срабатывание]             |
| | +---------------------------------------------------------------------+
| |                                                                        |
| | +--Card (HIGH, Level 2)------------------------------------------------+
| | | [!!] z-score: 2.8          Confidence: 0.78                          |
| | | Резкое падение рентабельности отгрузок менеджера Козлов С.П.         |
| | | Затронуто: ЛС-00789, сумма 5.68 млн руб.                            |
| | |                                                                      |
| | | Рекомендация: Проверить актуальность НПСС по позициям.              |
| | | [Подробнее]  [Запросить расследование L3]  [Решено]                  |
| | +----------------------------------------------------------------------+
| | ...                                                                     |
| +------------------------------------------------------------------------+
+==========================================================================+
```

### 5.2. Component Tree

```
AIInsightsPage
  +-- PageHeader
  |     +-- Title ("Аналитика (AI)")
  |     +-- AskButton -> /insights/ask
  |     +-- CostButton -> AI cost report
  +-- InsightsSummary
  |     +-- StatBadge (total, open, investigating, resolved)
  +-- InsightsFilters
  |     +-- LevelCheckboxGroup (L1, L2, L3)
  |     +-- StatusCheckboxGroup (open, investigating, resolved, false_positive)
  |     +-- DateRangePicker
  +-- AnomalyCardList
  |     +-- AnomalyCard (repeated)
  |           +-- SeverityHeader (icon + z-score + confidence)
  |           +-- AnomalyDescription (text)
  |           +-- AffectedEntities (count + total amount)
  |           +-- AIRecommendation (text, from Level 2/3)
  |           +-- InvestigationBadge (status + step count)
  |           +-- CardActions
  |                 +-- DetailsLink -> /insights/:id
  |                 +-- ResolveButton (dp/gd/fd)
  |                 +-- FalsePositiveButton (dp/gd/fd)
  |                 +-- EscalateToL3Button (if L2 + confidence < 0.7)
  +-- Pagination (offset-based, 20 per page)

InvestigationDetailPage (/insights/:id)
  +-- AnomalyHeader
  |     +-- SeverityBadge
  |     +-- AnomalyTitle
  |     +-- ConfidenceIndicator (gauge: 0-1.0, color-coded)
  +-- InvestigationTimeline
  |     +-- TimelineStep (repeated, max 10)
  |           +-- StepNumber
  |           +-- ToolUsed (icon + name: query_shipments, etc.)
  |           +-- InputSummary (collapsed JSON)
  |           +-- OutputSummary (key findings highlighted)
  |           +-- Duration (ms)
  +-- RootCauseSection
  |     +-- RootCauseText (from AI)
  |     +-- EvidenceList (links to entities)
  |     +-- ConfidenceScore (with explanation)
  +-- RecommendationSection
  |     +-- RecommendationList (numbered)
  |     +-- ActionButtons (resolve, escalate, false positive)
  +-- CostBreakdown
        +-- Model (Sonnet/Opus)
        +-- TokenCount (input/output/cached)
        +-- CostUSD

AIChatPage (/insights/ask)
  +-- ChatHistory
  |     +-- UserMessage (repeated)
  |     +-- AIMessage (repeated, with streaming)
  |           +-- StreamingText (character-by-character)
  |           +-- ConfidenceBadge
  |           +-- SourceReferences (links to shipments, LS)
  +-- ChatInput
  |     +-- TextArea (multi-line)
  |     +-- SendButton
  |     +-- SuggestedQuestions (3 pre-made queries)
  +-- ChatSidebar
        +-- RecentQuestions (last 10)
        +-- AICostCounter (today's spending)
```

### 5.3. Data Flow

```
AIInsightsPage
  |
  +-- GET /api/v1/anomalies                        --> AnomalyCardList
  |   Query key: ['anomalies', { level, status, date_from, date_to, page }]
  |   Refetch: 2 minutes
  |
  +-- GET /api/v1/anomalies/{id}                   --> AnomalyCard detail
  |   Query key: ['anomalies', anomalyId]
  |
  +-- GET /api/v1/anomalies/{id}/investigation     --> InvestigationTimeline
  |   Query key: ['anomalies', anomalyId, 'investigation']
  |
  +-- POST /api/v1/anomalies/{id}/resolve          --> Resolve/FalsePositive
  |   Mutation key: ['anomalies', 'resolve']
  |   Invalidates: ['anomalies']
  |
  +-- POST /api/v1/ai/ask                          --> AIChatPage (streaming)
  |   Uses fetch() with ReadableStream for SSE
  |   No TanStack Query (streaming)
  |
  +-- GET /api/v1/ai/costs                         --> CostBreakdown
      Query key: ['ai', 'costs', { date_from, date_to }]
```

### 5.4. AI Chat Streaming

```typescript
// hooks/useAIChat.ts
export function useAIChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);

  async function sendMessage(question: string) {
    setIsStreaming(true);
    setMessages(prev => [...prev, { role: 'user', content: question }]);

    const response = await fetch('/api/v1/ai/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ question, context: 'profitability_analysis' }),
    });

    const reader = response.body?.getReader();
    const decoder = new TextDecoder();
    let aiMessage = '';

    setMessages(prev => [...prev, { role: 'assistant', content: '' }]);

    while (reader) {
      const { done, value } = await reader.read();
      if (done) break;
      aiMessage += decoder.decode(value);
      setMessages(prev => {
        const updated = [...prev];
        updated[updated.length - 1] = { role: 'assistant', content: aiMessage };
        return updated;
      });
    }

    setIsStreaming(false);
  }

  return { messages, sendMessage, isStreaming };
}
```

### 5.5. Confidence Indicator

```
Confidence Score visual representation:

  High (>= 0.8):   [==========]  Green    "Высокая уверенность"
  Medium (0.5-0.8): [=======---]  Yellow   "Средняя уверенность"
  Low (< 0.5):      [===-------]  Red      "Низкая уверенность, рекомендуется ручная проверка"

Display: circular gauge (270-degree arc) with numeric value in center
```

---

## 6. Reports

### 6.1. Report Catalog

| Report ID | Name | Frequency | Audience | Priority | API Endpoint |
|-----------|------|-----------|----------|----------|-------------|
| LS-RPT-013 | Накопленная рентабельность по ЛС | По запросу | Менеджер, РБЮ | P1 | `GET /api/v1/local-estimates/{id}/summary` |
| LS-RPT-038 | Устаревшие НПСС | Еженедельно | ФД | P1 | `GET /api/v1/price-sheets/stale` |
| LS-RPT-043 | Конфликты блокировки ЛС | Еженедельно | Руководство | P1 | `GET /api/v1/reports/daily-efficiency` (section) |
| LS-RPT-068 | Клиенты с низким выкупом | Еженедельно | Менеджер, РБЮ | P1 | `GET /api/v1/reports/low-fulfillment` |
| LS-RPT-070 | Дашборд эффективности контроля | Ежедневно | ФД | P1 | `GET /api/v1/reports/daily-efficiency` |
| LS-RPT-072 | Нагрузка согласующих | Еженедельно | ДП, РБЮ | P1 | `GET /api/v1/kpi/approver/{id}/workload` |
| LS-RPT-073 | Базовый замер KPI (пилот) | Перед пилотом | Рабочая группа | P1 | `GET /api/v1/reports/baseline-kpi` |
| LS-RPT-074 | Промежуточный отчет пилота | Через 1 мес. | Рабочая группа | P1 | `GET /api/v1/reports/pilot-progress` |

### 6.2. Wireframe

```
+==========================================================================+
| Отчеты                                                                   |
+==========================================================================+
| +--Report Catalog (card grid)--------------------------------------------+
| | +--Card--+  +--Card--+  +--Card---+  +--Card--+                      |
| | |LS-RPT  |  |LS-RPT  |  |LS-RPT   |  |LS-RPT  |                      |
| | | -013   |  | -038   |  |  -068   |  | -070   |                      |
| | |Рент.   |  |Устар.  |  |Низкий   |  |Дашборд |                      |
| | |по ЛС   |  |НПСС    |  |выкуп    |  |эфф.    |                      |
| | |[Откр.] |  |[Откр.] |  |[Откр.]  |  |[Откр.] |                      |
| | +--------+  +--------+  +---------+  +--------+                      |
| |                                                                        |
| | +--Card--+  +--Card--+  +--Card---+  +--Card--+                      |
| | |LS-RPT  |  |LS-RPT  |  |LS-RPT   |  |LS-RPT  |                      |
| | | -043   |  | -072   |  |  -073   |  | -074   |                      |
| | |Конфл.  |  |Нагруз. |  |Базовый  |  |Пром.   |                      |
| | |блокир. |  |согл.   |  |KPI      |  |отчет   |                      |
| | |[Откр.] |  |[Откр.] |  |[Откр.]  |  |[Откр.] |                      |
| | +--------+  +--------+  +---------+  +--------+                      |
| +------------------------------------------------------------------------+
|                                                                          |
| +--Report Viewer (when report selected)----------------------------------+
| | +--Controls-+                                                          |
| | | Период: [01.02.2026] - [01.03.2026]  БЮ: [Все v]                   |
| | | [Обновить]  [Excel]  [PDF]                                          |
| | +------------+                                                         |
| |                                                                        |
| | +--Report Content (varies by report type)-----+                       |
| | |                                              |                       |
| | | [Table / Chart / Dashboard depending on      |                       |
| | |  report type]                                |                       |
| | |                                              |                       |
| | +----------------------------------------------+                       |
| +------------------------------------------------------------------------+
|                                                                          |
| +--Scheduled Reports-----------------------------------------------------+
| | | Тип          | Получатели      | Расписание    | Канал  | Статус |  |
| | |--------------|----------------|---------------|--------|--------|  |
| | | Ежедневная   | ФД, ДП         | 09:00 ежедн. | Email  | Вкл.   |  |
| | | сводка       |                |               |        |        |  |
| | | Еженедельный | РБЮ, ДП, ФД   | Пн 09:00     | Email  | Вкл.   |  |
| | | обзор        |                |               |        |        |  |
| | [Настроить рассылку]                                                   |
| +------------------------------------------------------------------------+
+==========================================================================+
```

### 6.3. Component Tree

```
ReportsPage
  +-- PageHeader
  |     +-- Title ("Отчеты")
  +-- ReportCatalog (grid: 4 columns desktop, 2 tablet, 1 mobile)
  |     +-- ReportCard (repeated, 8 P1 reports)
  |           +-- ReportIcon (type-specific)
  |           +-- ReportTitle
  |           +-- ReportDescription (1 line)
  |           +-- FrequencyBadge
  |           +-- OpenButton
  +-- Divider
  +-- ScheduledReports (section)
        +-- ScheduleTable
        |     +-- ScheduleRow (daily digest, weekly summary)
        +-- ConfigureButton (fd only)

ReportViewerPage (/reports/:reportId)
  +-- ReportHeader
  |     +-- ReportTitle + ReportID
  |     +-- ReportDescription
  +-- ReportControls
  |     +-- DateRangePicker
  |     +-- BusinessUnitSelect
  |     +-- RefreshButton
  |     +-- ExportDropdown
  |           +-- ExcelExportButton (xlsx via SheetJS)
  |           +-- PDFExportButton (jsPDF + html2canvas)
  +-- ReportContent (dynamic, depends on reportId)
  |     +-- LSProfitabilityReport (LS-RPT-013)
  |     |     +-- LSsummary card
  |     |     +-- DataTable (shipments by LS)
  |     |     +-- Recharts BarChart (plan vs fact by LS)
  |     +-- StaleNPSSReport (LS-RPT-038)
  |     |     +-- DataTable (products with NPSS age > threshold)
  |     |     +-- AgeDistributionChart (histogram)
  |     +-- LowFulfillmentReport (LS-RPT-068)
  |     |     +-- DataTable (clients with < threshold % fulfillment)
  |     |     +-- TrendChart (fulfillment % over time)
  |     +-- DailyEfficiencyReport (LS-RPT-070)
  |     |     +-- KPIGrid (4 main KPIs)
  |     |     +-- Recharts ComposedChart (approvals + SLA + anomalies)
  |     |     +-- DataTable (summary by BU)
  |     +-- ApproverWorkloadReport (LS-RPT-072)
  |     |     +-- Recharts BarChart (approver workload, thresholds at 30/50)
  |     |     +-- DataTable (approver, queue, avg time, SLA %)
  |     +-- BaselineKPIReport (LS-RPT-073)
  |     |     +-- KPIGrid (baseline measurements)
  |     |     +-- ComparisonTable (before/after)
  |     +-- PilotProgressReport (LS-RPT-074)
  |     |     +-- ProgressGauge (completion %)
  |     |     +-- KPIGrid (pilot KPIs vs targets)
  |     |     +-- RiskMatrix
  |     +-- ConflictReport (LS-RPT-043)
  |           +-- DataTable (blocking conflicts)
  |           +-- Timeline (conflict events)
  +-- ReportFooter
        +-- GeneratedAt (timestamp)
        +-- DataFreshness (last update time)
```

### 6.4. Data Flow

```
ReportViewerPage
  |
  +-- LS-RPT-013: GET /api/v1/local-estimates/{id}/summary?include_items=true
  |   Query key: ['reports', 'ls-profitability', lsId]
  |
  +-- LS-RPT-038: GET /api/v1/price-sheets/stale?older_than_days=90
  |   Query key: ['reports', 'stale-npss', { threshold }]
  |
  +-- LS-RPT-043: (derived from daily-efficiency)
  |   Query key: ['reports', 'conflicts', { date_from, date_to }]
  |
  +-- LS-RPT-068: GET /api/v1/reports/low-fulfillment?threshold_pct=50
  |   Query key: ['reports', 'low-fulfillment', { threshold }]
  |
  +-- LS-RPT-070: GET /api/v1/reports/daily-efficiency?date=YYYY-MM-DD
  |   Query key: ['reports', 'daily-efficiency', date]
  |
  +-- LS-RPT-072: GET /api/v1/kpi/approver/{id}/workload
  |   Query key: ['reports', 'approver-workload', approverId]
  |
  +-- LS-RPT-073: GET /api/v1/reports/baseline-kpi
  |   Query key: ['reports', 'baseline-kpi']
  |
  +-- LS-RPT-074: GET /api/v1/reports/pilot-progress
      Query key: ['reports', 'pilot-progress']
```

### 6.5. Export Implementation

```typescript
// lib/export.ts

// Excel export via SheetJS (xlsx)
export async function exportToExcel(data: any[], columns: Column[], filename: string) {
  const XLSX = await import('xlsx');
  const ws = XLSX.utils.json_to_sheet(
    data.map(row =>
      columns.reduce((acc, col) => ({ ...acc, [col.header]: row[col.accessorKey] }), {})
    )
  );
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, 'Report');
  XLSX.writeFile(wb, `${filename}_${format(new Date(), 'yyyy-MM-dd')}.xlsx`);
}

// PDF export via jsPDF + html2canvas
export async function exportToPDF(elementRef: HTMLElement, filename: string) {
  const html2canvas = (await import('html2canvas')).default;
  const { jsPDF } = await import('jspdf');

  const canvas = await html2canvas(elementRef, { scale: 2 });
  const pdf = new jsPDF('landscape', 'mm', 'a4');
  const imgData = canvas.toDataURL('image/png');
  const pdfWidth = pdf.internal.pageSize.getWidth();
  const pdfHeight = (canvas.height * pdfWidth) / canvas.width;
  pdf.addImage(imgData, 'PNG', 0, 0, pdfWidth, pdfHeight);
  pdf.save(`${filename}_${format(new Date(), 'yyyy-MM-dd')}.pdf`);
}
```

### 6.6. Scheduled Reports

| Report | Schedule | Channel | Recipients | Template |
|--------|----------|---------|------------|----------|
| Daily digest | 09:00 MSK daily | Email | fd, dp (configurable) | `daily_digest` |
| Weekly summary | Monday 09:00 MSK | Email | rbu, dp, fd | `weekly_summary` |

Configuration stored in `user_notification_preferences` table. UI allows fd to configure recipients, schedule, and content (which reports to include).

---

## 7. Settings

### 7.1. Wireframe

```
+==========================================================================+
| Настройки                                                                |
+==========================================================================+
| +--Tabs------------------------------------------------------------------+
| | [Пороги] [Роли] [Уведомления] [Функционал] [Журнал]                  |
| +------------------------------------------------------------------------+
|                                                                          |
| +--Tab: Пороги (Thresholds)-----------------------------------------+   |
| |                                                                    |   |
| | Автосогласование                                                   |   |
| | Максимальное отклонение: [==|====] 1.00 п.п.                       |   |
| |                                                                    |   |
| | Лимит менеджера/день: [======|===] 20 000 руб.                     |   |
| | Лимит БЮ/день:        [========|=] 100 000 руб.                    |   |
| |                                                                    |   |
| | Матрица согласования                                               |   |
| |   РБЮ: от [1.00] до [15.00] п.п.                                  |   |
| |   ДП:  от [15.01] до [25.00] п.п.                                 |   |
| |   ГД:  свыше [25.00] п.п.                                         |   |
| |                                                                    |   |
| | SLA (часы)                                                         |   |
| |   |      | P1  | P2  | <100т.р.|                                   |   |
| |   | РБЮ  | [4] | [24]| [2]    |                                    |   |
| |   | ДП   | [8] | [48]| [4]    |                                    |   |
| |   | ГД   |[24] | [72]| [12]   |                                    |   |
| |                                                                    |   |
| | Контроль                                                           |   |
| |   Блокировка ЛС: [5] мин.                                         |   |
| |   Итерации корректировки: [5] макс.                                |   |
| |   Срок согласования: [5] рабочих дней                              |   |
| |   Возраст НПСС: [90] дней (блокировка)                            |   |
| |                                                                    |   |
| | [Сохранить]  [Сбросить]  Последнее изменение: 15.02.2026 Шаховский|   |
| +--------------------------------------------------------------------+   |
|                                                                          |
| +--Tab: Роли (Roles)------------------------------------------------+   |
| |                                                                    |   |
| | AD Group --> App Role mapping                                      |   |
| |                                                                    |   |
| | | AD Group             | Роль        | Пользователей | Статус |   |   |
| | |----------------------|-------------|---------------|--------|   |   |
| | | APP-PROFIT-MANAGER   | manager     | 45            | Active |   |   |
| | | APP-PROFIT-RBU       | rbu         | 12            | Active |   |   |
| | | APP-PROFIT-DP        | dp          | 3             | Active |   |   |
| | | APP-PROFIT-GD        | gd          | 1             | Active |   |   |
| | | APP-PROFIT-FD        | fd          | 2             | Active |   |   |
| |                                                                    |   |
| | Note: Groups managed in Active Directory. This view is read-only. |   |
| +--------------------------------------------------------------------+   |
|                                                                          |
| +--Tab: Уведомления (Notifications)---------------------------------+   |
| |                                                                    |   |
| | Мои каналы                                                         |   |
| | [x] Telegram (chat: @ivanov_profit)  [Привязать]                   |   |
| | [x] Email (ivanov@ekf.su)                                         |   |
| | [ ] Push в 1С                                                      |   |
| |                                                                    |   |
| | Тихие часы: [22:00] - [07:00] (кроме CRITICAL)                    |   |
| |                                                                    |   |
| | Типы уведомлений                                                   |   |
| | | Тип                  | Telegram | Email | 1C Push |              |   |
| | |----------------------|----------|-------|---------|              |   |
| | | Запрос согласования  | [x]      | [x]   | [ ]     |              |   |
| | | Результат согласов.  | [x]      | [ ]   | [ ]     |              |   |
| | | Предупреждение SLA   | [x]      | [x]   | [ ]     |              |   |
| | | Аномалии             | [x]      | [ ]   | [ ]     |              |   |
| | | Ежедневная сводка    | [ ]      | [x]   | [ ]     |              |   |
| |                                                                    |   |
| | [Сохранить]                                                        |   |
| +--------------------------------------------------------------------+   |
|                                                                          |
| +--Tab: Функционал (Feature Flags)----------------------------------+   |
| |                                                                    |   |
| | | Функция                        | Статус  | Описание         |   |   |
| | |--------------------------------|---------|------------------|   |   |
| | | Контроль рентабельности        | [Вкл.]  | Основной модуль  |   |   |
| | | Блокирующий контроль           | [Выкл.] | Мягкий -> жесткий|   |   |
| | | Санкции за невыкуп (P2)        | [Выкл.] | Этап 2           |   |   |
| | | AI-аналитика                   | [Вкл.]  | 3 уровня AI      |   |   |
| | | Экстренные согласования        | [Вкл.]  | Постфактум       |   |   |
| | | Резервный режим ELMA           | [Выкл.] | Ручная активация |   |   |
| |                                                                    |   |
| | [Сохранить]                                                        |   |
| +--------------------------------------------------------------------+   |
|                                                                          |
| +--Tab: Журнал (Audit Log)------------------------------------------+   |
| |                                                                    |   |
| | Кто: [Все пользователи v]  Что: [Все действия v]                  |   |
| | Период: [01.02.2026] - [01.03.2026]  [Применить]                  |   |
| |                                                                    |   |
| | | Дата/Время     | Пользователь | Действие           | Детали |  |   |
| | |----------------|--------------|--------------------|---------| |   |
| | | 15.02 14:30    | Шаховский    | Изменен порог авто | 0.5->1.0| |   |
| | | 14.02 11:00    | Иванов       | Вкл. AI-аналитику  | -       | |   |
| | | 13.02 09:15    | Шаховский    | Изменен SLA P1 РБЮ | 2->4   | |   |
| | ...                                                                |   |
| +--------------------------------------------------------------------+   |
+==========================================================================+
```

### 7.2. Component Tree

```
SettingsPage
  +-- PageHeader
  |     +-- Title ("Настройки")
  |     +-- RoleGuard (fd only, others see Notifications only)
  +-- Tabs (shadcn/ui Tabs)
        +-- ThresholdsTab
        |     +-- AutoApprovalSection
        |     |     +-- Slider (deviationLimit: 0-5 pp, step 0.01)
        |     |     +-- Input (managerDailyLimit: numeric, formatted)
        |     |     +-- Input (buDailyLimit: numeric, formatted)
        |     +-- ApprovalMatrixSection
        |     |     +-- ThresholdInput (rbu: from, to)
        |     |     +-- ThresholdInput (dp: from, to)
        |     |     +-- ThresholdInput (gd: from)
        |     +-- SLAMatrixSection
        |     |     +-- SLAGrid (3x3 editable table: level x priority)
        |     +-- ControlSection
        |     |     +-- Input (lockTimeout: 1-30 min)
        |     |     +-- Input (correctionIterations: 1-10)
        |     |     +-- Input (approvalExpiry: 1-10 business days)
        |     |     +-- Input (npssAge: 30-180 days)
        |     +-- SaveButton + ResetButton + LastModifiedInfo
        +-- RolesTab
        |     +-- ADGroupTable (read-only, from AD sync)
        |     |     +-- ADGroupRow (group, role, user count, status)
        |     +-- ADSyncInfo (last sync time, next scheduled)
        +-- NotificationsTab
        |     +-- ChannelSection
        |     |     +-- ChannelToggle (telegram, with link account button)
        |     |     +-- ChannelToggle (email, with address display)
        |     |     +-- ChannelToggle (1c push)
        |     +-- QuietHoursSection
        |     |     +-- TimePicker (start)
        |     |     +-- TimePicker (end)
        |     +-- NotificationTypesMatrix
        |     |     +-- NotificationTypeRow (type x channel checkboxes)
        |     +-- SaveButton
        +-- FeatureFlagsTab
        |     +-- FeatureFlagRow (repeated, 6 flags)
        |           +-- FlagName + Description
        |           +-- Switch (on/off)
        |           +-- DependencyWarning (if flag depends on another)
        +-- AuditLogTab
              +-- AuditFilters
              |     +-- UserSelect
              |     +-- ActionSelect
              |     +-- DateRangePicker
              +-- AuditTable
              |     +-- AuditRow (timestamp, user, action, details)
              +-- Pagination
```

### 7.3. Data Flow

```
SettingsPage
  |
  +-- ThresholdsTab:
  |   GET /api/v1/settings/thresholds              --> form initial values
  |   PUT /api/v1/settings/thresholds              --> save changes
  |   Query key: ['settings', 'thresholds']
  |   Mutation: invalidates ['settings', 'thresholds']
  |   Note: settings endpoints to be added to api-gateway (admin-only)
  |
  +-- RolesTab:
  |   Derived from AD group query (read-only in UI)
  |   GET /api/v1/mdm/business-units               --> list BUs
  |   Query key: ['mdm', 'business-units']
  |
  +-- NotificationsTab:
  |   GET /api/v1/notifications/preferences         --> current settings
  |   PUT /api/v1/notifications/preferences         --> save settings
  |   Query key: ['notifications', 'preferences']
  |
  +-- FeatureFlagsTab:
  |   GET /api/v1/settings/feature-flags            --> current flags
  |   PUT /api/v1/settings/feature-flags/{id}       --> toggle flag
  |   Query key: ['settings', 'feature-flags']
  |
  +-- AuditLogTab:
      GET /api/v1/settings/audit-log                --> paginated log
      Query key: ['settings', 'audit-log', { user, action, date_from, date_to, page }]
```

### 7.4. 10 Configurable Constants from FM

| # | Constant | FM Reference | Default | UI Control | Validation |
|---|----------|-------------|---------|------------|------------|
| 1 | Auto-approve deviation limit | п. 3.5 | 1.00 п.п. | Slider (0.01-5.00) | min 0.01, max 5.00 |
| 2 | Manager daily limit | п. 3.5, LS-BR-072 | 20 000 руб. | NumberInput | min 1 000, max 200 000 |
| 3 | BU daily limit | п. 3.5, LS-BR-073 | 100 000 руб. | NumberInput | min 10 000, max 1 000 000 |
| 4 | LS lock timeout | LS-BR-035 | 5 мин. | NumberInput | min 1, max 30 |
| 5 | Correction iteration limit | LS-BR-076 | 5 | NumberInput | min 1, max 10 |
| 6 | Approval expiry (business days) | LS-BR-017 | 5 | NumberInput | min 1, max 10 |
| 7 | NPSS age threshold (days) | LS-BR-075 | 90 | NumberInput | min 30, max 180 |
| 8 | SLA hours (3x3 matrix) | п. 3.6, LS-WF-001..003 | see SLA matrix | 3x3 grid | min 1, max 168 (1 week) |
| 9 | Emergency limit per manager/month | п. 3.7 | 3 (peaks: 5) | NumberInput | min 1, max 20 |
| 10 | Emergency limit per client/month | п. 3.7 | 5 (peaks: 8) | NumberInput | min 1, max 30 |

---

## 8. Component Library (Atomic Design)

### 8.1. Atoms

| Component | Description | Props | Storybook |
|-----------|-------------|-------|-----------|
| `Button` | Primary, secondary, outline, ghost, destructive variants | `variant`, `size`, `disabled`, `loading`, `icon` | `button.stories.tsx` |
| `Badge` | Status, severity, role, count indicators | `variant` (default/success/warning/error/info), `size` | `badge.stories.tsx` |
| `Card` | Container with header, content, footer slots | `variant` (default/outlined/elevated), `padding` | `card.stories.tsx` |
| `Input` | Text, number, password with label and error | `type`, `label`, `error`, `helperText`, `required` | `input.stories.tsx` |
| `Select` | Single/multi select with search | `options`, `multi`, `searchable`, `placeholder` | `select.stories.tsx` |
| `Spinner` | Loading indicator (circular) | `size` (sm/md/lg), `color` | `spinner.stories.tsx` |
| `Toast` | Notification popup (success/error/warning/info) | `variant`, `title`, `description`, `duration` | `toast.stories.tsx` |
| `Switch` | Toggle on/off | `checked`, `onChange`, `disabled`, `label` | `switch.stories.tsx` |
| `Tooltip` | Hover/focus tooltip | `content`, `side`, `align` | `tooltip.stories.tsx` |
| `Avatar` | User avatar with initials fallback | `src`, `name`, `size` | `avatar.stories.tsx` |
| `Skeleton` | Loading placeholder | `variant` (text/circular/rect), `width`, `height` | `skeleton.stories.tsx` |

### 8.2. Molecules

| Component | Atoms Used | Description | Props |
|-----------|-----------|-------------|-------|
| `DataTable` | Input, Select, Button, Badge | Sortable, filterable, paginated table | `columns`, `data`, `onSort`, `onFilter`, `pagination` |
| `KPIWidget` | Card, Badge | KPI display with trend arrow and sparkline | `title`, `value`, `trend`, `sparklineData`, `format` |
| `SLATimer` | Badge | Countdown timer with color-coded urgency | `deadline`, `startedAt`, `slaHours`, `level` |
| `ProfitabilityBadge` | Badge | Color-coded profitability percentage | `value`, `threshold`, `showSign` |
| `AnomalyCard` | Card, Badge, Button | Anomaly summary with severity and actions | `anomaly`, `onResolve`, `onEscalate` |
| `FilterBar` | Input, Select, Button | Collapsible filter row with apply/reset | `filters`, `onChange`, `onApply`, `onReset` |
| `DateRangePicker` | Input, Button | Date range selection with presets | `value`, `onChange`, `presets`, `minDate`, `maxDate` |
| `ConfidenceGauge` | -- (custom SVG) | Circular gauge 0-1.0 with color | `value`, `size`, `showLabel` |
| `StatusBadge` | Badge | Shipment/approval status with icon | `status`, `variant` |
| `TrendArrow` | -- (custom SVG) | Direction arrow with value | `value`, `direction` (up/down/neutral) |
| `SearchInput` | Input, Spinner | Debounced search with loading state | `onSearch`, `debounceMs`, `placeholder` |
| `EmptyState` | -- | No data placeholder with illustration | `title`, `description`, `action` |

### 8.3. Organisms

| Component | Molecules Used | Description | Props |
|-----------|---------------|-------------|-------|
| `ShipmentDetail` | DataTable, ProfitabilityBadge, StatusBadge | Full shipment view with line items and calculations | `shipmentId` |
| `ApprovalForm` | SLATimer, ProfitabilityBadge, Button, Input | Approval decision form with comment | `processId`, `onDecide` |
| `InvestigationTimeline` | AnomalyCard, ConfidenceGauge | Step-by-step AI investigation display | `investigationId` |
| `ReportViewer` | DataTable, FilterBar, DateRangePicker | Report rendering with filters and export | `reportId`, `filters` |
| `NotificationPreferences` | Switch, Select | Per-channel notification settings | `preferences`, `onSave` |
| `ManagerDashboard` | KPIWidget, DataTable, AnomalyCard | Dashboard view customized per role | `role`, `userId` |
| `ApprovalQueue` | SLATimer, AnomalyCard, Button | Queue of approval tasks with batch ops | `level`, `onDecide` |
| `ThresholdEditor` | Input, Button | Settings form for thresholds and SLA | `thresholds`, `onSave` |
| `ProfitabilityChart` | -- (Recharts) | AreaChart with period controls | `data`, `period`, `onPeriodChange` |
| `AlertFeed` | Badge, Button | Scrollable list of recent alerts | `alerts`, `onViewAll` |
| `ChatInterface` | Input, Button, Spinner | AI chat with streaming support | `onSend`, `messages`, `isStreaming` |

### 8.4. Storybook Configuration

```typescript
// .storybook/main.ts
import type { StorybookConfig } from '@storybook/nextjs';

const config: StorybookConfig = {
  stories: ['../src/components/**/*.stories.@(ts|tsx)'],
  addons: [
    '@storybook/addon-essentials',
    '@storybook/addon-a11y',       // accessibility checks
    '@storybook/addon-interactions', // interaction testing
  ],
  framework: {
    name: '@storybook/nextjs',
    options: { nextConfigPath: '../next.config.ts' },
  },
};

export default config;
```

### 8.5. Component Directory Structure

```
src/
  components/
    atoms/
      Button/
        Button.tsx
        Button.stories.tsx
        Button.test.tsx
        index.ts
      Badge/
      Card/
      Input/
      Select/
      Spinner/
      Toast/
      Switch/
      Tooltip/
      Avatar/
      Skeleton/
    molecules/
      DataTable/
        DataTable.tsx
        DataTable.stories.tsx
        DataTable.test.tsx
        columns.ts          # column definitions
        index.ts
      KPIWidget/
      SLATimer/
      ProfitabilityBadge/
      AnomalyCard/
      FilterBar/
      DateRangePicker/
      ConfidenceGauge/
      StatusBadge/
      TrendArrow/
      SearchInput/
      EmptyState/
    organisms/
      ShipmentDetail/
      ApprovalForm/
      InvestigationTimeline/
      ReportViewer/
      NotificationPreferences/
      ManagerDashboard/
      ApprovalQueue/
      ThresholdEditor/
      ProfitabilityChart/
      AlertFeed/
      ChatInterface/
    layouts/
      RootLayout.tsx
      ProtectedLayout.tsx   # Sidebar + TopBar
      Sidebar.tsx
      TopBar.tsx
```

---

## 9. API Client Architecture

### 9.1. OpenAPI Codegen

```
openapi-spec.yaml (from api-gateway)
  |
  v
orval (codegen)         # generates:
  |                     #   - TypeScript types (Zod schemas)
  |                     #   - TanStack Query hooks
  |                     #   - Axios/fetch clients
  v
src/api/
  generated/
    types.ts            # All request/response types
    schemas.ts          # Zod validation schemas
    hooks/
      shipments.ts      # useGetShipment, useCalculateProfitability, etc.
      approvals.ts      # useGetApprovalQueue, useDecideApproval, etc.
      analytics.ts      # useGetAnomalies, useAskAI, etc.
      reports.ts        # useGetDailyEfficiency, etc.
      notifications.ts  # useGetPreferences, etc.
      settings.ts       # useGetThresholds, etc.
```

### 9.2. API Client Setup

```typescript
// lib/api-client.ts
import axios, { AxiosInstance, InternalAxiosRequestConfig } from 'axios';
import { getSession } from 'next-auth/react';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://profit-api.ekf.su';

export const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30_000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Auth interceptor: attach JWT
apiClient.interceptors.request.use(async (config: InternalAxiosRequestConfig) => {
  const session = await getSession();
  if (session?.accessToken) {
    config.headers.Authorization = `Bearer ${session.accessToken}`;
  }
  return config;
});

// Response interceptor: handle 401 (token refresh)
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      // Attempt token refresh
      try {
        const session = await getSession();
        if (session?.refreshToken) {
          const refreshResponse = await axios.post(`${API_BASE_URL}/auth/refresh`, {
            refresh_token: session.refreshToken,
          });
          // Update session with new tokens
          // Retry original request
          error.config.headers.Authorization = `Bearer ${refreshResponse.data.access_token}`;
          return apiClient(error.config);
        }
      } catch {
        // Refresh failed, redirect to login
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);
```

### 9.3. TanStack Query Configuration

```typescript
// lib/query-client.ts
import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,          // 30 seconds
      gcTime: 5 * 60_000,         // 5 minutes garbage collection
      retry: 2,                   // retry failed requests twice
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 10000),
      refetchOnWindowFocus: true,  // refresh stale data on focus
      refetchOnReconnect: true,    // refresh on reconnect
    },
    mutations: {
      retry: 1,
    },
  },
});
```

### 9.4. Query Key Factory

```typescript
// lib/query-keys.ts
export const queryKeys = {
  // Dashboard
  dashboard: {
    all: ['dashboard'] as const,
    manager: (filters: DashboardFilters) => ['dashboard', 'manager', filters] as const,
  },

  // Shipments
  shipments: {
    all: ['shipments'] as const,
    list: (filters: ShipmentFilters) => ['shipments', 'list', filters] as const,
    detail: (id: string) => ['shipments', id] as const,
    profitability: (id: string) => ['shipments', id, 'profitability'] as const,
  },

  // Approvals
  approvals: {
    all: ['approvals'] as const,
    queue: (filters: QueueFilters) => ['approvals', 'queue', filters] as const,
    queueCount: () => ['approvals', 'queue', 'count'] as const,
    detail: (id: string) => ['approvals', id] as const,
    sla: (id: string) => ['approvals', 'sla', id] as const,
    limits: (date?: string) => ['approvals', 'limits', date] as const,
  },

  // Analytics
  anomalies: {
    all: ['anomalies'] as const,
    list: (filters: AnomalyFilters) => ['anomalies', 'list', filters] as const,
    detail: (id: string) => ['anomalies', id] as const,
    investigation: (id: string) => ['anomalies', id, 'investigation'] as const,
  },

  // AI
  ai: {
    costs: (filters: DateRange) => ['ai', 'costs', filters] as const,
  },

  // Reports
  reports: {
    all: ['reports'] as const,
    byId: (reportId: string, params: ReportParams) => ['reports', reportId, params] as const,
    dailyEfficiency: (date: string) => ['reports', 'daily-efficiency', date] as const,
    stalenpss: (threshold: number) => ['reports', 'stale-npss', threshold] as const,
    lowFulfillment: (threshold: number) => ['reports', 'low-fulfillment', threshold] as const,
    baselineKpi: () => ['reports', 'baseline-kpi'] as const,
    pilotProgress: () => ['reports', 'pilot-progress'] as const,
  },

  // KPI
  kpi: {
    manager: (id: string, period?: string) => ['kpi', 'manager', id, period] as const,
    approverWorkload: (id: string) => ['kpi', 'approver', id, 'workload'] as const,
  },

  // MDM
  mdm: {
    client: (id: string) => ['mdm', 'client', id] as const,
    priceSheet: (productId: string) => ['mdm', 'price-sheet', productId] as const,
    businessUnits: () => ['mdm', 'business-units'] as const,
  },

  // Notifications
  notifications: {
    all: ['notifications'] as const,
    list: (filters: NotificationFilters) => ['notifications', 'list', filters] as const,
    preferences: () => ['notifications', 'preferences'] as const,
  },

  // Settings
  settings: {
    thresholds: () => ['settings', 'thresholds'] as const,
    featureFlags: () => ['settings', 'feature-flags'] as const,
    auditLog: (filters: AuditFilters) => ['settings', 'audit-log', filters] as const,
  },
};
```

### 9.5. Example Custom Hook

```typescript
// hooks/useApprovalQueue.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-keys';
import { ApprovalQueueItem, DecisionRequest } from '@/api/generated/types';

export function useApprovalQueue(filters: QueueFilters) {
  return useQuery<ApprovalQueueItem[]>({
    queryKey: queryKeys.approvals.queue(filters),
    queryFn: async () => {
      const params = new URLSearchParams();
      if (filters.priority) params.set('priority', filters.priority);
      if (filters.level) params.set('level', filters.level);
      const { data } = await apiClient.get(`/api/v1/approvals/queue?${params}`);
      return data;
    },
    refetchInterval: 15_000, // 15 seconds -- real-time queue
  });
}

export function useDecideApproval() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ processId, decision }: { processId: string; decision: DecisionRequest }) => {
      const { data } = await apiClient.post(`/api/v1/approvals/${processId}/decide`, decision);
      return data;
    },
    onMutate: async ({ processId }) => {
      // Optimistic update: remove from queue
      await queryClient.cancelQueries({ queryKey: queryKeys.approvals.all });
      const previousQueue = queryClient.getQueryData(queryKeys.approvals.queue({}));
      queryClient.setQueryData(queryKeys.approvals.queue({}), (old: ApprovalQueueItem[] | undefined) =>
        old?.filter(item => item.id !== processId)
      );
      return { previousQueue };
    },
    onError: (_err, _vars, context) => {
      // Rollback on error
      if (context?.previousQueue) {
        queryClient.setQueryData(queryKeys.approvals.queue({}), context.previousQueue);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.approvals.all });
    },
  });
}
```

---

## 10. Auth Flow

### 10.1. Authentication Architecture

```
+--------+     +------------+     +-----------+     +----+
| Browser| --> | Next.js    | --> | api-      | --> | AD |
|        |     | (NextAuth) |     | gateway   |     |    |
+--------+     +-----+------+     +-----+-----+     +----+
                      |                  |
                 JWT stored         JWT validated
                 (httpOnly            (RS256 verify)
                  cookie)
```

### 10.2. NextAuth.js Configuration

```typescript
// app/api/auth/[...nextauth]/route.ts
import NextAuth, { type NextAuthOptions } from 'next-auth';
import CredentialsProvider from 'next-auth/providers/credentials';
import { apiClient } from '@/lib/api-client';

export const authOptions: NextAuthOptions = {
  providers: [
    CredentialsProvider({
      name: 'Active Directory',
      credentials: {
        username: { label: 'Логин (AD)', type: 'text' },
        password: { label: 'Пароль', type: 'password' },
      },
      async authorize(credentials) {
        try {
          const { data } = await apiClient.post('/auth/login', {
            username: credentials?.username,
            password: credentials?.password,
          });
          return {
            id: data.user_id,
            name: data.display_name,
            email: data.email,
            role: data.role,           // manager|rbu|dp|gd|fd
            accessToken: data.access_token,
            refreshToken: data.refresh_token,
            businessUnitId: data.business_unit_id,
          };
        } catch {
          return null;
        }
      },
    }),
  ],
  session: {
    strategy: 'jwt',
    maxAge: 7 * 24 * 60 * 60, // 7 days (matches refresh token)
  },
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.role = user.role;
        token.accessToken = user.accessToken;
        token.refreshToken = user.refreshToken;
        token.businessUnitId = user.businessUnitId;
      }
      return token;
    },
    async session({ session, token }) {
      session.user.role = token.role as AppRole;
      session.accessToken = token.accessToken as string;
      session.refreshToken = token.refreshToken as string;
      session.user.businessUnitId = token.businessUnitId as string;
      return session;
    },
  },
  pages: {
    signIn: '/login',
  },
};

const handler = NextAuth(authOptions);
export { handler as GET, handler as POST };
```

### 10.3. Protected Route Middleware

```typescript
// middleware.ts
import { withAuth } from 'next-auth/middleware';
import { NextResponse } from 'next/server';

export default withAuth(
  function middleware(req) {
    const token = req.nextauth.token;
    const pathname = req.nextUrl.pathname;

    // Role-based route protection
    const roleRouteMap: Record<string, AppRole[]> = {
      '/settings/thresholds': ['fd'],
      '/settings/roles': ['fd'],
      '/settings/features': ['fd'],
      '/settings/audit': ['fd'],
      '/insights/ask': ['dp', 'gd', 'fd'],
    };

    for (const [route, allowedRoles] of Object.entries(roleRouteMap)) {
      if (pathname.startsWith(route) && !allowedRoles.includes(token?.role as AppRole)) {
        return NextResponse.redirect(new URL('/dashboard', req.url));
      }
    }

    return NextResponse.next();
  },
  {
    callbacks: {
      authorized: ({ token }) => !!token,
    },
  }
);

export const config = {
  matcher: ['/((?!login|api/auth|_next|favicon.ico).*)'],
};
```

### 10.4. Role Guard Component

```typescript
// components/atoms/RoleGuard.tsx
'use client';

import { useSession } from 'next-auth/react';
import { type AppRole } from '@/types/auth';

interface RoleGuardProps {
  allowedRoles: AppRole[];
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

export function RoleGuard({ allowedRoles, children, fallback = null }: RoleGuardProps) {
  const { data: session } = useSession();
  if (!session?.user?.role || !allowedRoles.includes(session.user.role)) {
    return fallback;
  }
  return <>{children}</>;
}
```

### 10.5. Type Definitions

```typescript
// types/auth.ts
export type AppRole = 'manager' | 'rbu' | 'dp' | 'gd' | 'fd';

declare module 'next-auth' {
  interface User {
    role: AppRole;
    accessToken: string;
    refreshToken: string;
    businessUnitId: string;
  }
  interface Session {
    user: User & { role: AppRole; businessUnitId: string };
    accessToken: string;
    refreshToken: string;
  }
}

declare module 'next-auth/jwt' {
  interface JWT {
    role: AppRole;
    accessToken: string;
    refreshToken: string;
    businessUnitId: string;
  }
}
```

---

## 11. State Management

### 11.1. Strategy

| State Type | Tool | Reason |
|-----------|------|--------|
| Server state (API data) | TanStack Query | Caching, dedup, background refetch, optimistic updates |
| Client UI state | Zustand | Lightweight, no boilerplate, TypeScript-first |
| Form state | React Hook Form + Zod | Validation, field arrays, performance |
| URL state (filters) | nuqs (URL search params) | Shareable URLs, browser back/forward |
| Auth state | NextAuth.js session | JWT-based, server+client access |

### 11.2. Zustand Stores

```typescript
// stores/ui.ts -- global UI state
interface UIState {
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
  activeDrawer: { type: string; id: string } | null;
  openDrawer: (type: string, id: string) => void;
  closeDrawer: () => void;
}

export const useUIStore = create<UIState>((set) => ({
  sidebarCollapsed: false,
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  activeDrawer: null,
  openDrawer: (type, id) => set({ activeDrawer: { type, id } }),
  closeDrawer: () => set({ activeDrawer: null }),
}));
```

```typescript
// stores/filters.ts -- filter state (synced with URL via nuqs)
interface FilterState {
  shipmentFilters: ShipmentFilters;
  approvalFilters: QueueFilters;
  anomalyFilters: AnomalyFilters;
  setShipmentFilter: (key: string, value: any) => void;
  setApprovalFilter: (key: string, value: any) => void;
  setAnomalyFilter: (key: string, value: any) => void;
  resetFilters: (page: 'shipments' | 'approvals' | 'anomalies') => void;
}
```

### 11.3. Form Validation (React Hook Form + Zod)

```typescript
// schemas/approval-decision.ts
import { z } from 'zod';

export const approvalDecisionSchema = z.object({
  decision: z.enum(['approved', 'rejected', 'approved_with_correction']),
  comment: z.string()
    .min(50, 'Комментарий должен содержать минимум 50 символов')
    .max(2000)
    .optional()
    .refine(
      (val) => val !== undefined,
      { message: 'Комментарий обязателен при отклонении' }
    ),
});

export const priceCorrectionSchema = z.object({
  proposedPrice: z.number()
    .positive('Цена должна быть положительной')
    .min(0.01, 'Минимальная цена: 0.01 руб.'),
  justification: z.string()
    .min(50, 'Обоснование должно содержать минимум 50 символов')
    .max(2000),
});

export const thresholdsSchema = z.object({
  autoApproveLimit: z.number().min(0.01).max(5.00),
  managerDailyLimit: z.number().min(1000).max(200000),
  buDailyLimit: z.number().min(10000).max(1000000),
  lockTimeout: z.number().int().min(1).max(30),
  correctionIterations: z.number().int().min(1).max(10),
  approvalExpiry: z.number().int().min(1).max(10),
  npssAge: z.number().int().min(30).max(180),
  slaMatrix: z.object({
    rbu: z.object({ p1: z.number().int().min(1).max(168), p2: z.number().int().min(1).max(168), small: z.number().int().min(1).max(168) }),
    dp: z.object({ p1: z.number().int().min(1).max(168), p2: z.number().int().min(1).max(168), small: z.number().int().min(1).max(168) }),
    gd: z.object({ p1: z.number().int().min(1).max(168), p2: z.number().int().min(1).max(168), small: z.number().int().min(1).max(168) }),
  }),
  emergencyLimitManager: z.number().int().min(1).max(20),
  emergencyLimitClient: z.number().int().min(1).max(30),
});
```

---

## 12. Error Handling Strategy

### 12.1. Error Boundary Hierarchy

```
app/error.tsx (global -- catches unhandled errors)
  |
  +-- (protected)/error.tsx (protected area -- auth errors)
  |     |
  |     +-- Page-level error.tsx (per page)
  |           +-- Component-level ErrorBoundary (inline)
```

### 12.2. Error Types and Handling

| HTTP Status | Error Type | User-Facing Message | Action |
|-------------|-----------|---------------------|--------|
| 400 | Validation | "Проверьте введенные данные" + field errors | Highlight invalid fields |
| 401 | Auth expired | "Сессия истекла" | Redirect to /login |
| 403 | Forbidden | "Недостаточно прав для данного действия" | Show role info, suggest contact |
| 404 | Not found | "Страница не найдена" | Show 404 page with link to dashboard |
| 409 | Conflict | "Данные были изменены другим пользователем" | Offer to reload and retry |
| 429 | Rate limit | "Слишком много запросов, подождите" | Auto-retry with backoff |
| 500 | Server error | "Ошибка сервера, попробуйте позже" | Retry button, contact support link |
| Network | Connection | "Нет соединения с сервером" | Auto-retry on reconnect |

### 12.3. Toast Notification System

```typescript
// lib/toast.ts
import { toast as sonnerToast } from 'sonner';

export const toast = {
  success: (message: string) => sonnerToast.success(message, { duration: 3000 }),
  error: (message: string, description?: string) =>
    sonnerToast.error(message, { description, duration: 5000 }),
  warning: (message: string) => sonnerToast.warning(message, { duration: 4000 }),
  info: (message: string) => sonnerToast.info(message, { duration: 3000 }),
  conflict: (message: string, onRetry: () => void) =>
    sonnerToast.error(message, {
      duration: 10000,
      action: { label: 'Обновить и повторить', onClick: onRetry },
    }),
};
```

### 12.4. Mutation Error Handling

```typescript
// hooks/useMutationWithToast.ts
export function useMutationWithToast<TData, TVariables>(
  options: UseMutationOptions<TData, Error, TVariables>
) {
  return useMutation({
    ...options,
    onError: (error: Error, variables, context) => {
      if (axios.isAxiosError(error)) {
        const status = error.response?.status;
        switch (status) {
          case 409:
            toast.conflict('Данные были изменены другим пользователем', () => {
              queryClient.invalidateQueries();
            });
            break;
          case 400:
            toast.error('Ошибка валидации', error.response?.data?.message);
            break;
          default:
            toast.error('Ошибка', error.response?.data?.message || 'Попробуйте позже');
        }
      } else {
        toast.error('Ошибка сети', 'Проверьте подключение к интернету');
      }
      options.onError?.(error, variables, context);
    },
  });
}
```

---

## 13. Responsive Design

### 13.1. Breakpoints

| Breakpoint | Width | Target | Layout Changes |
|-----------|-------|--------|----------------|
| `sm` | >= 640px | Small tablet | Single column, collapsed sidebar |
| `md` | >= 768px | Tablet | 2 columns, sidebar overlay |
| `lg` | >= 1024px | Laptop | Full sidebar, 2-3 columns |
| `xl` | >= 1280px | Desktop | Full layout, wide tables |
| `2xl` | >= 1536px | Large monitor | Maximum information density |

### 13.2. Responsive Behaviors

| Component | Mobile (< 768px) | Tablet (768-1024px) | Desktop (>= 1024px) |
|-----------|-----------------|--------------------|--------------------|
| Sidebar | Hidden, hamburger menu | Collapsible overlay | Always visible |
| KPI Row | 2x2 grid, scrollable | 4x1 row | 4x1 row |
| DataTable | Card view (stacked) | Scrollable table | Full table |
| Approval Cards | Full-width stack | 2-column grid | Full-width stack (detail-rich) |
| Charts | Full-width, smaller | Full-width, medium | Side-by-side possible |
| Filters | Bottom sheet modal | Collapsible row | Always visible row |
| Drawer | Full-screen modal | Right panel (50%) | Right panel (40%) |
| Report Viewer | Scrollable, no export | Full view | Full view with side panel |

### 13.3. Primary Usage Context

The system is primarily used on desktop (office workstations, 1920x1080+). Tablet support is secondary (management reviewing dashboards). Mobile is not a primary target but should not break.

**Design priority:** Desktop-first, responsive down to tablet (768px). Mobile: read-only dashboard access.

---

## 14. Accessibility (a11y)

### 14.1. WCAG 2.1 AA Requirements

| Category | Requirement | Implementation |
|----------|------------|----------------|
| Perceivable | Color contrast >= 4.5:1 | Tailwind CSS color palette verified, shadcn/ui defaults pass |
| Perceivable | Non-color status indicators | Icons + text labels alongside color badges |
| Perceivable | Text alternatives | All images/icons have `aria-label` or `alt` text |
| Operable | Keyboard navigation | Tab order, focus rings, Enter/Space activation |
| Operable | Focus management | Focus trapped in modals/drawers, restored on close |
| Operable | Skip navigation | "Skip to main content" link at top |
| Understandable | Form labels | Every input has visible `<label>` or `aria-label` |
| Understandable | Error identification | Error messages linked to fields via `aria-describedby` |
| Robust | Semantic HTML | Proper heading hierarchy, landmarks, ARIA roles |

### 14.2. Keyboard Navigation Map

| Key | Context | Action |
|-----|---------|--------|
| `Tab` / `Shift+Tab` | Global | Navigate between focusable elements |
| `Enter` / `Space` | Button, Link | Activate |
| `Escape` | Modal, Drawer, Dropdown | Close |
| `Arrow Up/Down` | Select, Menu | Navigate options |
| `Home` / `End` | Table | Jump to first/last row |
| `Ctrl+K` | Global | Open search |

### 14.3. ARIA Landmarks

```html
<header role="banner">        <!-- TopBar -->
<nav role="navigation">        <!-- Sidebar -->
<main role="main">             <!-- Page content -->
<aside role="complementary">   <!-- Drawer panel -->
<footer role="contentinfo">    <!-- Report footer -->
```

### 14.4. Testing

- Storybook `@storybook/addon-a11y` (automated checks per component)
- Playwright `@axe-core/playwright` (page-level scans in E2E tests)
- Manual testing: keyboard-only navigation, screen reader (NVDA/VoiceOver)

---

## 15. Performance Budget

### 15.1. Targets

| Metric | Target | Measurement |
|--------|--------|------------|
| First Contentful Paint (FCP) | < 1.5s | Lighthouse |
| Largest Contentful Paint (LCP) | < 2.5s | Lighthouse |
| Time to Interactive (TTI) | < 3.5s | Lighthouse |
| Cumulative Layout Shift (CLS) | < 0.1 | Lighthouse |
| First Input Delay (FID) | < 100ms | Lighthouse |
| JS bundle (initial) | < 200KB gzipped | Next.js build analyzer |
| JS bundle (per route) | < 50KB gzipped | Next.js build analyzer |
| API response (p95) | < 500ms | Prometheus metrics |

### 15.2. Optimization Strategies

| Strategy | Implementation |
|----------|---------------|
| Code splitting | Next.js App Router automatic per-route splitting |
| Tree shaking | ES modules, sideEffects: false |
| Lazy loading | `dynamic()` for heavy components (Charts, PDF viewer) |
| Image optimization | Next.js `<Image>` with WebP, lazy loading |
| Font optimization | `next/font` with Google Fonts (Inter), font-display: swap |
| API caching | TanStack Query staleTime + gcTime |
| Prefetching | Router prefetch on link hover, TanStack Query prefetchQuery |
| Virtualization | `@tanstack/react-virtual` for tables with 100+ rows |
| Bundle analysis | `@next/bundle-analyzer` in CI pipeline |

### 15.3. Concurrent Users (50-70)

| Concern | Solution |
|---------|----------|
| API load | Server-side: rate limiting (100 req/min/user). Client-side: dedup via TanStack Query |
| WebSocket alternative | Polling with staleTime (15-60s) is sufficient for 50-70 users. WebSocket can be added in Phase 2 if needed |
| Optimistic concurrency | Version field on all entities. 409 Conflict on stale update. Toast notification + reload |
| Cache invalidation | Aggressive refetch on mutations. Background refetch on window focus |

---

## 16. Traceability Matrix

### 16.1. Pages -> FM Requirements

| Page | FM Sections | Key Requirements |
|------|------------|-----------------|
| Dashboard | п. 3.4, 3.20, LS-RPT-070 | KPI visualization, anomaly feed, efficiency dashboard |
| Shipments | п. 3.1-3.5, 3.8-3.14 | LS/shipment management, profitability calculation, drill-down |
| Approvals | п. 3.5-3.7, 3.11, LS-WF-001..004 | 4-level approval matrix, SLA, batch ops, emergency |
| AI Insights | п. 3.20 (AI) | 3-level AI anomaly detection, investigation, chat |
| Reports | LS-RPT-013..074 (8 P1 reports) | All P1 reports with filtering and export |
| Settings | п. 5, LS-BR-035, LS-BR-072-076 | 10 configurable constants, feature flags, audit log |

### 16.2. Components -> API Endpoints

| Component | API Endpoint | Service |
|-----------|-------------|---------|
| KPIWidget | `GET /dashboard/manager`, `GET /kpi/manager/{id}` | profitability |
| DataTable (shipments) | `GET /local-estimates/{id}/shipments` | profitability |
| ShipmentDrawer | `GET /shipments/{id}`, `GET /shipments/{id}/profitability` | profitability |
| TaskCard | `GET /approvals/queue` | workflow |
| SLATimer | `GET /approvals/sla/{id}` | workflow |
| ApprovalForm | `POST /approvals/{id}/decide` | workflow |
| AnomalyCard | `GET /anomalies`, `GET /anomalies/{id}` | analytics |
| InvestigationTimeline | `GET /anomalies/{id}/investigation` | analytics |
| ChatInterface | `POST /ai/ask` | analytics |
| ReportViewer | Various report endpoints | analytics |
| ThresholdEditor | `GET/PUT /settings/thresholds` | api-gateway |
| NotificationPreferences | `GET/PUT /notifications/preferences` | notification |

### 16.3. Roles -> Features

| Feature | manager | rbu | dp | gd | fd |
|---------|---------|-----|----|----|-----|
| View own shipments | Y | Y (BU) | Y (all) | Y (all) | Y (all) |
| Create shipment | Y | -- | -- | -- | -- |
| Submit for approval | Y | -- | -- | -- | -- |
| Approve/reject | -- | L1-2 | L2-3 | L3-4 | -- |
| Batch approve | -- | Y | Y | Y | -- |
| Price correction | Y | Y (request) | -- | -- | -- |
| Emergency approval | Y (create) | Y (confirm) | Y (confirm) | -- | -- |
| View anomalies | -- | Y | Y | Y | Y |
| Resolve anomalies | -- | -- | Y | Y | Y |
| AI chat | -- | -- | Y | Y | Y |
| View reports | Own | BU | All | All | All |
| Export reports | Y | Y | Y | Y | Y |
| Configure thresholds | -- | -- | -- | -- | Y |
| Feature flags | -- | -- | -- | -- | Y |
| Audit log | -- | -- | -- | -- | Y |
| Notification settings | Y | Y | Y | Y | Y |

---

## Appendix A. Technology Stack Summary

| Category | Technology | Version | Purpose |
|----------|-----------|---------|---------|
| Framework | Next.js | 15.x | App Router, RSC, SSR/SSG |
| UI Library | React | 19.x | Component rendering |
| Language | TypeScript | 5.x | Type safety |
| Styling | Tailwind CSS | 3.x | Utility-first CSS |
| Component Kit | shadcn/ui | latest | Radix-based headless components |
| Data Fetching | TanStack Query | v5 | Server state management |
| Client State | Zustand | 5.x | Lightweight store |
| Forms | React Hook Form | 7.x | Form state + validation |
| Validation | Zod | 3.x | Schema validation |
| Charts | Recharts | 2.x | Data visualization |
| Tables | TanStack Table | v8 | Headless table logic |
| URL State | nuqs | latest | Type-safe URL search params |
| Auth | NextAuth.js | 4.x | AD/JWT auth |
| API Codegen | Orval | latest | OpenAPI -> TypeScript/hooks |
| HTTP Client | Axios | 1.x | API calls with interceptors |
| Date | date-fns | 3.x | Date formatting/manipulation |
| Export (Excel) | SheetJS (xlsx) | latest | Excel export |
| Export (PDF) | jsPDF + html2canvas | latest | PDF export |
| Toast | Sonner | latest | Toast notifications |
| Icons | Lucide React | latest | Icon set |
| Testing (Unit) | Vitest | latest | Component unit tests |
| Testing (E2E) | Playwright | latest | End-to-end tests |
| Storybook | Storybook | 8.x | Component development |
| Virtualization | TanStack Virtual | v3 | Large list rendering |
| Linting | ESLint + Prettier | latest | Code quality |

## Appendix B. File Structure

```
profitability-service/
  frontend/
    .storybook/
      main.ts
      preview.ts
    public/
      favicon.ico
      logo.svg
    src/
      app/                        # Next.js App Router pages
        (auth)/
        (protected)/
        api/
        layout.tsx
        error.tsx
        not-found.tsx
        loading.tsx
      components/                 # Atomic Design
        atoms/
        molecules/
        organisms/
        layouts/
      hooks/                      # Custom React hooks
        useApprovalQueue.ts
        useShipments.ts
        useAIChat.ts
        useSLATimer.ts
        ...
      lib/                        # Utilities
        api-client.ts
        query-client.ts
        query-keys.ts
        toast.ts
        export.ts
        format.ts                 # Number/date/currency formatting
        cn.ts                     # Tailwind class merger
      stores/                     # Zustand stores
        ui.ts
        filters.ts
        dashboard.ts
      api/                        # Generated API client
        generated/
          types.ts
          schemas.ts
          hooks/
      schemas/                    # Zod validation schemas
        approval-decision.ts
        price-correction.ts
        thresholds.ts
        ...
      types/                      # TypeScript type definitions
        auth.ts
        domain.ts
        reports.ts
      styles/
        globals.css               # Tailwind base
    next.config.ts
    tailwind.config.ts
    tsconfig.json
    package.json
    orval.config.ts              # OpenAPI codegen config
    vitest.config.ts
    playwright.config.ts
```

## Appendix C. Settings API Endpoints (New)

The following endpoints need to be added to the api-gateway for the Settings page. They are admin-only (`fd` role).

| Method | Path | Description | Auth Role | Request | Response |
|--------|------|-------------|-----------|---------|----------|
| GET | /api/v1/settings/thresholds | Get current thresholds | fd | - | `ThresholdsConfig` |
| PUT | /api/v1/settings/thresholds | Update thresholds | fd | `ThresholdsConfig` | `ThresholdsConfig` |
| GET | /api/v1/settings/feature-flags | Get feature flags | fd | - | `[]FeatureFlag` |
| PUT | /api/v1/settings/feature-flags/{id} | Toggle feature flag | fd | `{ enabled: bool }` | `FeatureFlag` |
| GET | /api/v1/settings/audit-log | Get audit log entries | fd | query: `user`, `action`, `date_from`, `date_to`, `page`, `per_page` | `PaginatedAuditLog` |

These endpoints manage the `ThresholdsConfig` object which corresponds to the 10 configurable constants from the FM (see Section 7.4).
