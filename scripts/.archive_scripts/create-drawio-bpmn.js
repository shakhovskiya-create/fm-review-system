#!/usr/bin/env node
/**
 * Создание draw.io BPMN диаграммы с авто-layout
 *
 * Использует: dagre для layout + генерация draw.io XML
 * Результат: .drawio файл для импорта в Confluence
 */

import dagre from 'dagre';
import { writeFileSync, mkdirSync, existsSync } from 'fs';
import { execSync } from 'child_process';
import { dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

// Конфигурация
const CONFIG = {
  nodeWidth: 140,
  nodeHeight: 60,
  gatewaySize: 50,
  eventSize: 30,
  lanePadding: 30,
  laneHeaderHeight: 30,
  // Цвета
  colors: {
    startEvent: '#d5e8d4',      // Зеленый
    endEventOk: '#d5e8d4',
    endEventError: '#f8cecc',   // Красный
    task: '#dae8fc',            // Синий
    gateway: '#fff2cc',         // Желтый
    laneManager: '#e1d5e7',     // Фиолетовый
    laneSystem: '#d5e8d4',      // Зеленый
    laneApprover: '#fff2cc'     // Желтый
  },
  strokes: {
    startEvent: '#82b366',
    endEventOk: '#82b366',
    endEventError: '#b85450',
    task: '#6c8ebf',
    gateway: '#d6b656',
    lane: '#666666'
  }
};

/**
 * Определение процесса
 */
const processDefinition = {
  lanes: [
    { id: 'lane_manager', name: 'Менеджер', color: CONFIG.colors.laneManager },
    { id: 'lane_system', name: 'Система 1С:УТ', color: CONFIG.colors.laneSystem },
    { id: 'lane_approver', name: 'Согласующий', color: CONFIG.colors.laneApprover }
  ],
  nodes: [
    { id: 'start', type: 'startEvent', label: '', lane: 'lane_manager' },
    { id: 'task1', type: 'task', label: 'Создать заказ клиента', lane: 'lane_manager' },
    { id: 'task2', type: 'task', label: 'Проверить НПСС', lane: 'lane_system' },
    { id: 'gw1', type: 'gateway', label: 'НПСС актуальна?', lane: 'lane_system' },
    { id: 'task3', type: 'task', label: 'Блокировка заказа', lane: 'lane_system' },
    { id: 'end1', type: 'endEventError', label: '', lane: 'lane_system' },
    { id: 'task4', type: 'task', label: 'Рассчитать рентабельность', lane: 'lane_system' },
    { id: 'gw2', type: 'gateway', label: 'Рент >= 0%?', lane: 'lane_system' },
    { id: 'task5', type: 'task', label: 'Автосогласование', lane: 'lane_system' },
    { id: 'end2', type: 'endEventOk', label: '', lane: 'lane_system' },
    { id: 'task6', type: 'task', label: 'На согласование', lane: 'lane_system' },
    { id: 'task7', type: 'task', label: 'Принять решение', lane: 'lane_approver' },
    { id: 'gw3', type: 'gateway', label: 'Решение?', lane: 'lane_approver' },
    { id: 'end3', type: 'endEventOk', label: '', lane: 'lane_approver' },
    { id: 'end4', type: 'endEventError', label: '', lane: 'lane_approver' }
  ],
  edges: [
    { from: 'start', to: 'task1' },
    { from: 'task1', to: 'task2' },
    { from: 'task2', to: 'gw1' },
    { from: 'gw1', to: 'task3', label: 'Нет' },
    { from: 'task3', to: 'end1' },
    { from: 'gw1', to: 'task4', label: 'Да' },
    { from: 'task4', to: 'gw2' },
    { from: 'gw2', to: 'task5', label: 'Да' },
    { from: 'task5', to: 'end2' },
    { from: 'gw2', to: 'task6', label: 'Нет' },
    { from: 'task6', to: 'task7' },
    { from: 'task7', to: 'gw3' },
    { from: 'gw3', to: 'end3', label: 'Да' },
    { from: 'gw3', to: 'end4', label: 'Нет' }
  ]
};

/**
 * Рассчитывает layout с помощью dagre
 */
function calculateLayout(process) {
  const g = new dagre.graphlib.Graph();

  g.setGraph({
    rankdir: 'LR',  // Left to Right (горизонтальный поток)
    nodesep: 60,
    ranksep: 80,
    marginx: 40,
    marginy: 40
  });

  g.setDefaultEdgeLabel(() => ({}));

  for (const node of process.nodes) {
    const size = node.type === 'gateway'
      ? { width: CONFIG.gatewaySize, height: CONFIG.gatewaySize }
      : node.type.includes('Event')
        ? { width: CONFIG.eventSize, height: CONFIG.eventSize }
        : { width: CONFIG.nodeWidth, height: CONFIG.nodeHeight };

    g.setNode(node.id, { ...size, ...node });
  }

  for (const edge of process.edges) {
    g.setEdge(edge.from, edge.to, { label: edge.label });
  }

  dagre.layout(g);

  const layoutedNodes = [];
  g.nodes().forEach(nodeId => {
    const node = g.node(nodeId);
    layoutedNodes.push({
      ...node,
      x: Math.round(node.x),
      y: Math.round(node.y),
      width: node.width,
      height: node.height
    });
  });

  const layoutedEdges = [];
  g.edges().forEach(e => {
    const edge = g.edge(e);
    layoutedEdges.push({
      from: e.v,
      to: e.w,
      label: edge.label,
      points: edge.points
    });
  });

  return { nodes: layoutedNodes, edges: layoutedEdges, lanes: process.lanes };
}

/**
 * Генерирует draw.io XML
 */
function generateDrawioXml(layout) {
  let cellId = 2;
  const nodeIdMap = {};
  const cells = [];

  // Считаем границы для каждого lane (горизонтальный layout - lanes по вертикали)
  const laneBounds = {};
  const laneHeaderWidth = 40;  // Ширина заголовка swimlane слева

  // Находим общую ширину диаграммы
  const allMinX = Math.min(...layout.nodes.map(n => n.x - n.width/2));
  const allMaxX = Math.max(...layout.nodes.map(n => n.x + n.width/2));
  const totalWidth = allMaxX - allMinX + CONFIG.lanePadding * 2 + laneHeaderWidth;

  for (const lane of layout.lanes) {
    const laneNodes = layout.nodes.filter(n => n.lane === lane.id);
    if (laneNodes.length === 0) continue;

    const minY = Math.min(...laneNodes.map(n => n.y - n.height/2));
    const maxY = Math.max(...laneNodes.map(n => n.y + n.height/2));

    laneBounds[lane.id] = {
      x: allMinX - CONFIG.lanePadding - laneHeaderWidth,
      y: minY - CONFIG.lanePadding,
      width: totalWidth,
      height: maxY - minY + CONFIG.lanePadding * 2
    };
  }

  // Создаем swimlanes
  for (const lane of layout.lanes) {
    const bounds = laneBounds[lane.id];
    if (!bounds) continue;

    const id = cellId++;
    cells.push(`
      <mxCell id="${id}" value="${lane.name}" style="swimlane;horizontal=0;startSize=40;fillColor=${lane.color};strokeColor=${CONFIG.strokes.lane};fontStyle=1;" vertex="1" parent="1">
        <mxGeometry x="${bounds.x}" y="${bounds.y}" width="${bounds.width}" height="${bounds.height}" as="geometry"/>
      </mxCell>`);
  }

  // Создаем nodes
  for (const node of layout.nodes) {
    const id = cellId++;
    nodeIdMap[node.id] = id;

    let style = '';
    const x = node.x - node.width / 2;
    const y = node.y - node.height / 2;

    switch (node.type) {
      case 'startEvent':
        style = `ellipse;fillColor=${CONFIG.colors.startEvent};strokeColor=${CONFIG.strokes.startEvent};strokeWidth=2;`;
        break;
      case 'endEventOk':
        style = `ellipse;fillColor=${CONFIG.colors.endEventOk};strokeColor=${CONFIG.strokes.endEventOk};strokeWidth=3;`;
        break;
      case 'endEventError':
        style = `ellipse;fillColor=${CONFIG.colors.endEventError};strokeColor=${CONFIG.strokes.endEventError};strokeWidth=3;`;
        break;
      case 'task':
        style = `rounded=1;fillColor=${CONFIG.colors.task};strokeColor=${CONFIG.strokes.task};`;
        break;
      case 'gateway':
        style = `rhombus;fillColor=${CONFIG.colors.gateway};strokeColor=${CONFIG.strokes.gateway};`;
        break;
    }

    cells.push(`
      <mxCell id="${id}" value="${node.label}" style="${style}" vertex="1" parent="1">
        <mxGeometry x="${x}" y="${y}" width="${node.width}" height="${node.height}" as="geometry"/>
      </mxCell>`);
  }

  // Создаем edges
  for (const edge of layout.edges) {
    const id = cellId++;
    const sourceId = nodeIdMap[edge.from];
    const targetId = nodeIdMap[edge.to];

    cells.push(`
      <mxCell id="${id}" value="${edge.label || ''}" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;endArrow=block;endFill=1;" edge="1" parent="1" source="${sourceId}" target="${targetId}">
        <mxGeometry relative="1" as="geometry"/>
      </mxCell>`);
  }

  return `<?xml version="1.0" encoding="UTF-8"?>
<mxfile host="app.diagrams.net" modified="${new Date().toISOString()}" agent="BPMN Generator" version="21.0.0" type="device">
  <diagram name="BPMN Process" id="process-1">
    <mxGraphModel dx="1000" dy="800" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1200" pageHeight="900" math="0" shadow="0">
      <root>
        <mxCell id="0"/>
        <mxCell id="1" parent="0"/>
        ${cells.join('')}
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>`;
}

async function main() {
  const outputDir = `${__dirname}/output`;
  if (!existsSync(outputDir)) mkdirSync(outputDir);

  console.log('📐 Расчет layout...');
  const layout = calculateLayout(processDefinition);

  console.log('📝 Генерация draw.io XML...');
  const xml = generateDrawioXml(layout);

  const outputPath = `${outputDir}/bpmn-autolayout.drawio`;
  writeFileSync(outputPath, xml);
  console.log(`💾 Сохранено: ${outputPath}`);

  // Экспорт в PNG через draw.io CLI
  const pngPath = `${outputDir}/bpmn-autolayout.png`;
  try {
    console.log('🖼️  Экспорт в PNG...');
    execSync(`/Applications/draw.io.app/Contents/MacOS/draw.io -x -f png -o "${pngPath}" "${outputPath}"`, {
      timeout: 30000,
      stdio: 'pipe'
    });
    console.log(`✅ PNG: ${pngPath}`);
  } catch (e) {
    console.log('ℹ️  PNG экспорт пропущен (draw.io CLI не отвечает в headless)');
  }

  // Открываем
  if (process.platform === 'darwin') {
    execSync(`open "${outputPath}"`);
  }

  console.log('\n✨ Готово! Файл можно импортировать в Confluence draw.io');
}

main().catch(console.error);
