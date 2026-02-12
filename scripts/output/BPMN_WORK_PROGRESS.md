# BPMN Work Progress — Paused

## Status: PAUSED (switched to HTML approach)

## Completed BPMN files (with colors, lanes, types, DI):
- process-0-overview.bpmn — Done
- process-1-rentability.bpmn — Done (user fixed layout in Camunda)
- process-2-approval.bpmn — Done (user fixed layout in Camunda)
- process-3-emergency.bpmn — Done (user fixed)
- process-4-order-lifecycle.bpmn — Done (full DI rewrite + Gateway_Rtu fix)

## Remaining BPMN files (raw from generate-bpmn.js, need finishing):
- process-5 through process-12 — need: colors, task types, lanes DI, flowNodeRef

## Open issue in process-4:
- EndEvent_Cancelled name="Завершен" should be "Отменен"

## Workflow was "Variant 3":
1. Assistant provides text prompt for diagram
2. User creates in Camunda Modeler
3. Assistant adds: colors, semantic task types, lane assignments (flowNodeRef),
   errorEventDefinitions, pool/lane DI shapes with coordinate adjustments

## Color scheme:
- System (serviceTask/sendTask): stroke="#0d4372" fill="#bbdefb"
- Human (userTask) + Gateways: stroke="#6b3c00" fill="#ffe0b2"
- Start + Success end: stroke="#205022" fill="#c8e6c9"
- Error/rejection end: stroke="#831311" fill="#ffcdd2"

## To resume: say "Продолжи BPMN работу" or "Resume BPMN work"
