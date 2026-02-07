#!/usr/bin/env node
/**
 * BPMN диаграмма в стиле из примера:
 * - Горизонтальные swimlanes (заголовок слева вертикально)
 * - Поток слева направо
 * - Желтые задачи, XOR с X, зеленые круги старт/конец
 */

import dagre from 'dagre';
import { writeFileSync, mkdirSync, existsSync } from 'fs';
import { execSync } from 'child_process';
import { dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

// Escape special chars for XML attributes
function xmlEncode(str) {
  if (!str) return '';
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/\n/g, '&#xa;');
}

// Рассчитывает размер элемента под текст
function calculateTaskSize(label) {
  if (!label) return { width: CONFIG.taskMinWidth, height: CONFIG.taskMinHeight };

  const lines = label.split('\n');
  const maxLineLength = Math.max(...lines.map(l => l.length));

  // Ширина: на основе самой длинной строки
  const textWidth = maxLineLength * CONFIG.charWidth;
  const width = Math.min(CONFIG.taskMaxWidth, Math.max(CONFIG.taskMinWidth, textWidth + CONFIG.taskPadding));

  // Высота: на основе количества строк
  const textHeight = lines.length * CONFIG.lineHeight;
  const height = Math.max(CONFIG.taskMinHeight, textHeight + CONFIG.taskPadding);

  return { width, height };
}

const CONFIG = {
  taskMinWidth: 100,
  taskMaxWidth: 180,
  taskMinHeight: 50,
  charWidth: 7,        // примерная ширина символа
  lineHeight: 16,      // высота строки
  taskPadding: 20,     // внутренний отступ
  gatewaySize: 45,
  eventSize: 35,
  laneHeaderWidth: 35,
  lanePadding: 30,
  eventLabelSpace: 35,  // место для подписи под событием
  colors: {
    task: '#fff2cc',           // Желтый - задача
    taskError: '#f8cecc',      // Розовый - ошибка
    gateway: '#fff2cc',        // Желтый - XOR
    eventStart: '#d5e8d4',     // Зеленый - старт
    eventEnd: '#d5e8d4',       // Зеленый - конец ОК
    eventEndError: '#f8cecc',  // Розовый - конец ошибка
    subprocess: '#e1d5e7',     // Фиолетовый - подпроцесс
    laneManager: '#dae8fc',    // Голубой
    laneSystem: '#d5e8d4'      // Зеленый
  },
  strokes: {
    task: '#d6b656',
    taskError: '#b85450',
    gateway: '#d6b656',
    event: '#82b366',
    eventError: '#b85450',
    subprocess: '#9673a6',
    lane: '#666666'
  }
};

// Процесс - точно как на картинке
const processDefinition = {
  lanes: [
    { id: 'manager', name: 'Менеджер', color: CONFIG.colors.laneManager },
    { id: 'system', name: 'Контроль рентабельности\n1С:УТ', color: CONFIG.colors.laneSystem }
  ],
  nodes: [
    // Lane: Менеджер
    { id: 'start', type: 'eventStart', label: '', lane: 'manager' },
    { id: 't1', type: 'task', label: 'Создать\nЗаказ клиента', lane: 'manager' },

    // Lane: Система
    { id: 't2', type: 'task', label: 'Проверка актуальности\nсебестоимости\n(возраст НПСС < 90 дн)', lane: 'system' },
    { id: 'x1', type: 'gateway', label: 'X', lane: 'system' },
    { id: 't3', type: 'taskError', label: 'Блокировка\n(обновить НПСС)', lane: 'system' },
    { id: 'e1', type: 'eventEndError', label: 'Заблокирован', lane: 'system' },
    { id: 't4', type: 'task', label: 'Расчет\nрентабельности', lane: 'system' },
    { id: 'x2', type: 'gateway', label: 'X', lane: 'system' },
    { id: 't5', type: 'task', label: 'Авто-\nсогласование', lane: 'system' },
    { id: 'e2', type: 'eventEnd', label: 'Заказ\nсогласован', lane: 'system' },
    { id: 't6', type: 'subprocess', label: 'Согласование\n(см. BPMN 2)', lane: 'system' },
    { id: 'x3', type: 'gateway', label: 'X', lane: 'system' },
    { id: 'e3', type: 'eventEnd', label: 'Согласовано', lane: 'system' },
    { id: 'e4', type: 'eventEndError', label: 'Отклонено', lane: 'system' }
  ],
  edges: [
    { from: 'start', to: 't1' },
    { from: 't1', to: 't2' },
    { from: 't2', to: 'x1' },
    { from: 'x1', to: 't3', label: 'устарела' },
    { from: 't3', to: 'e1' },
    { from: 'x1', to: 't4', label: 'актуальна' },
    { from: 't4', to: 'x2' },
    { from: 'x2', to: 't5', label: '>= 0%' },
    { from: 't5', to: 'e2' },
    { from: 'x2', to: 't6', label: '< 0%' },
    { from: 't6', to: 'x3' },
    { from: 'x3', to: 'e3', label: 'да' },
    { from: 'x3', to: 'e4', label: 'нет' }
  ]
};

function calculateLayout(process) {
  // Создаем единый граф для всего процесса
  const g = new dagre.graphlib.Graph();
  g.setGraph({
    rankdir: 'LR',
    nodesep: 70,
    ranksep: 70,
    marginx: 40,
    marginy: 50
  });
  g.setDefaultEdgeLabel(() => ({}));

  // Добавляем все узлы
  for (const node of process.nodes) {
    let size;
    if (node.type === 'gateway') {
      size = { width: CONFIG.gatewaySize, height: CONFIG.gatewaySize };
    } else if (node.type.includes('event')) {
      size = { width: CONFIG.eventSize, height: CONFIG.eventSize };
    } else {
      // Динамический размер на основе текста
      size = calculateTaskSize(node.label);
    }
    g.setNode(node.id, { ...size, ...node });
  }

  // Добавляем все связи
  for (const edge of process.edges) {
    g.setEdge(edge.from, edge.to, { label: edge.label });
  }

  dagre.layout(g);

  // Группируем узлы по lanes и находим границы
  const laneNodes = {};
  for (const lane of process.lanes) {
    laneNodes[lane.id] = [];
  }

  g.nodes().forEach(nodeId => {
    const node = g.node(nodeId);
    if (node.lane && laneNodes[node.lane]) {
      laneNodes[node.lane].push({ ...node, id: nodeId });
    }
  });

  // Вычисляем высоту каждого lane
  const laneInfo = {};
  let currentY = 0;

  for (const lane of process.lanes) {
    const nodes = laneNodes[lane.id];
    if (nodes.length === 0) {
      laneInfo[lane.id] = { y: currentY, height: 100 };
      currentY += 100;
      continue;
    }

    // Находим мин/макс Y для узлов этого lane
    let minY = Infinity, maxY = -Infinity;
    for (const node of nodes) {
      minY = Math.min(minY, node.y - node.height / 2);
      // Для событий добавляем место под подпись
      const extraSpace = node.type.includes('event') ? CONFIG.eventLabelSpace : 0;
      maxY = Math.max(maxY, node.y + node.height / 2 + extraSpace);
    }

    const contentHeight = maxY - minY;
    const laneHeight = Math.max(contentHeight + CONFIG.lanePadding * 2, 120);

    laneInfo[lane.id] = {
      y: currentY,
      height: laneHeight,
      minContentY: minY,
      maxContentY: maxY
    };
    currentY += laneHeight;
  }

  // Находим минимальный X по всем узлам для нормализации
  let globalMinX = Infinity;
  for (const lane of process.lanes) {
    for (const node of laneNodes[lane.id]) {
      globalMinX = Math.min(globalMinX, node.x - node.width / 2);
    }
  }

  // Преобразуем координаты узлов в координаты относительно их lane
  const layoutedNodes = [];
  for (const lane of process.lanes) {
    const nodes = laneNodes[lane.id];
    const info = laneInfo[lane.id];

    for (const node of nodes) {
      // X: нормализуем от левого края + отступ для заголовка lane (80px) + padding
      const relX = (node.x - globalMinX) + 80 + CONFIG.lanePadding;

      // Y: позиция относительно верхней границы контента lane + padding
      const relY = (node.y - info.minContentY) + CONFIG.lanePadding;

      layoutedNodes.push({
        ...node,
        x: Math.round(relX),
        y: Math.round(relY),
        width: node.width,
        height: node.height,
        laneY: info.y,
        laneHeight: info.height
      });
    }
  }

  return { nodes: layoutedNodes, edges: process.edges, lanes: process.lanes, laneInfo };
}

function generateDrawioXml(layout) {
  let cellId = 2;
  const nodeIdMap = {};
  const cells = [];
  const laneIdMap = {};

  // Находим общую ширину и высоту
  const maxX = Math.max(...layout.nodes.map(n => n.x + n.width/2)) + CONFIG.lanePadding;
  const totalWidth = maxX + CONFIG.laneHeaderWidth + 50;
  const totalHeight = Object.values(layout.laneInfo).reduce((sum, info) => Math.max(sum, info.y + info.height), 0);

  // Создаем Pool контейнер
  const poolId = cellId++;
  cells.push(`
      <mxCell id="${poolId}" value="${xmlEncode('Контроль рентабельности')}" style="swimlane;html=1;horizontal=0;startSize=30;fillColor=#f5f5f5;strokeColor=#666666;" vertex="1" parent="1">
        <mxGeometry x="40" y="60" width="${totalWidth}" height="${totalHeight}" as="geometry"/>
      </mxCell>`);

  // Создаем swimlanes как дочерние элементы pool
  let laneY = 0;
  for (const lane of layout.lanes) {
    const info = layout.laneInfo[lane.id];
    const laneId = cellId++;
    laneIdMap[lane.id] = laneId;

    cells.push(`
      <mxCell id="${laneId}" value="${xmlEncode(lane.name)}" style="swimlane;html=1;horizontal=0;startSize=80;fillColor=${lane.color};strokeColor=${CONFIG.strokes.lane};" vertex="1" parent="${poolId}">
        <mxGeometry x="30" y="${laneY}" width="${totalWidth - 30}" height="${info.height}" as="geometry"/>
      </mxCell>`);
    laneY += info.height;
  }

  // Создаем узлы как дочерние элементы lanes
  for (const node of layout.nodes) {
    const id = cellId++;
    nodeIdMap[node.id] = id;

    // Координаты относительно lane (уже вычислены в calculateLayout)
    const parentLaneId = laneIdMap[node.lane];
    // node.x и node.y - это позиция центра, преобразуем в верхний левый угол
    const relX = node.x - node.width / 2;
    const relY = node.y - node.height / 2;

    let style = '';

    switch (node.type) {
      case 'eventStart':
        style = `ellipse;html=1;fillColor=#67AB9F;strokeWidth=2;`;
        break;
      case 'eventEnd':
        style = `ellipse;html=1;fillColor=#67AB9F;strokeWidth=4;`;
        break;
      case 'eventEndError':
        style = `ellipse;html=1;fillColor=${CONFIG.colors.eventEndError};strokeWidth=4;`;
        break;
      case 'task':
        style = `rounded=1;whiteSpace=wrap;html=1;fillColor=${CONFIG.colors.task};strokeColor=${CONFIG.strokes.task};`;
        break;
      case 'taskError':
        style = `rounded=1;whiteSpace=wrap;html=1;fillColor=${CONFIG.colors.taskError};strokeColor=${CONFIG.strokes.taskError};`;
        break;
      case 'subprocess':
        style = `rounded=1;whiteSpace=wrap;html=1;fillColor=${CONFIG.colors.subprocess};strokeColor=${CONFIG.strokes.subprocess};dashed=1;dashPattern=8 4;`;
        break;
      case 'gateway':
        style = `rhombus;html=1;fillColor=${CONFIG.colors.gateway};strokeColor=${CONFIG.strokes.gateway};strokeWidth=2;`;
        break;
    }

    // Для gateway и events используем пустое значение (текст отдельно)
    const cellValue = (node.type === 'gateway' || node.type.includes('event')) ? '' : xmlEncode(node.label);

    cells.push(`
      <mxCell id="${id}" value="${cellValue}" style="${style}" vertex="1" parent="${parentLaneId}">
        <mxGeometry x="${relX}" y="${relY}" width="${node.width}" height="${node.height}" as="geometry"/>
      </mxCell>`);

    // Добавляем текст "X" поверх gateway
    if (node.type === 'gateway') {
      const xTextId = cellId++;
      const xSize = 20;
      const xX = relX + (node.width - xSize) / 2;
      const xY = relY + (node.height - xSize) / 2;
      cells.push(`
      <mxCell id="${xTextId}" value="X" style="text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;fontSize=14;fontStyle=1;" vertex="1" parent="${parentLaneId}">
        <mxGeometry x="${xX}" y="${xY}" width="${xSize}" height="${xSize}" as="geometry"/>
      </mxCell>`);
    }

    // Добавляем текстовую подпись под end events
    if (node.type.includes('event') && node.type !== 'eventStart' && node.label) {
      const labelId = cellId++;
      const labelWidth = 90;
      const labelX = relX + (node.width - labelWidth) / 2;
      const labelY = relY + node.height + 5;
      cells.push(`
      <mxCell id="${labelId}" value="${xmlEncode(node.label)}" style="text;html=1;strokeColor=none;fillColor=none;align=center;fontSize=9;fontColor=#333333;" vertex="1" parent="${parentLaneId}">
        <mxGeometry x="${labelX}" y="${labelY}" width="${labelWidth}" height="30" as="geometry"/>
      </mxCell>`);
    }
  }

  // Создаем связи (parent = pool, не root!)
  for (const edge of layout.edges) {
    const id = cellId++;
    const sourceId = nodeIdMap[edge.from];
    const targetId = nodeIdMap[edge.to];
    if (!sourceId || !targetId) continue;

    cells.push(`
      <mxCell id="${id}" value="${xmlEncode(edge.label || '')}" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;endArrow=block;endFill=1;strokeWidth=2;labelBackgroundColor=#ffffff;" edge="1" parent="${poolId}" source="${sourceId}" target="${targetId}">
        <mxGeometry relative="1" as="geometry"/>
      </mxCell>`);
  }

  // Добавляем легенду
  const legendX = totalWidth + 60;
  const legendY = 100;
  const legendId = cellId++;
  cells.push(`
    <mxCell id="${legendId}" value="Легенда BPMN" style="swimlane;fontStyle=1;startSize=23;fillColor=#f5f5f5;strokeColor=#666666;" vertex="1" parent="1">
      <mxGeometry x="${legendX}" y="${legendY}" width="180" height="150" as="geometry"/>
    </mxCell>`);

  // Легенда - элементы
  const leg1 = cellId++;
  cells.push(`<mxCell id="${leg1}" value="" style="ellipse;fillColor=#67AB9F;strokeWidth=2;" vertex="1" parent="${legendId}"><mxGeometry x="10" y="33" width="20" height="20" as="geometry"/></mxCell>`);
  const leg1t = cellId++;
  cells.push(`<mxCell id="${leg1t}" value="Начало / Конец" style="text;fontSize=10;align=left;" vertex="1" parent="${legendId}"><mxGeometry x="40" y="33" width="120" height="20" as="geometry"/></mxCell>`);

  const leg2 = cellId++;
  cells.push(`<mxCell id="${leg2}" value="" style="rounded=1;fillColor=${CONFIG.colors.task};strokeColor=${CONFIG.strokes.task};" vertex="1" parent="${legendId}"><mxGeometry x="10" y="60" width="22" height="16" as="geometry"/></mxCell>`);
  const leg2t = cellId++;
  cells.push(`<mxCell id="${leg2t}" value="Задача" style="text;fontSize=10;align=left;" vertex="1" parent="${legendId}"><mxGeometry x="40" y="58" width="120" height="20" as="geometry"/></mxCell>`);

  const leg3 = cellId++;
  cells.push(`<mxCell id="${leg3}" value="X" style="rhombus;fillColor=${CONFIG.colors.gateway};strokeColor=${CONFIG.strokes.gateway};fontSize=10;" vertex="1" parent="${legendId}"><mxGeometry x="10" y="83" width="22" height="22" as="geometry"/></mxCell>`);
  const leg3t = cellId++;
  cells.push(`<mxCell id="${leg3t}" value="XOR шлюз (выбор)" style="text;fontSize=10;align=left;" vertex="1" parent="${legendId}"><mxGeometry x="40" y="85" width="120" height="20" as="geometry"/></mxCell>`);

  const leg4 = cellId++;
  cells.push(`<mxCell id="${leg4}" value="" style="rounded=1;fillColor=${CONFIG.colors.subprocess};strokeColor=${CONFIG.strokes.subprocess};dashed=1;" vertex="1" parent="${legendId}"><mxGeometry x="10" y="110" width="22" height="16" as="geometry"/></mxCell>`);
  const leg4t = cellId++;
  cells.push(`<mxCell id="${leg4t}" value="Подпроцесс" style="text;fontSize=10;align=left;" vertex="1" parent="${legendId}"><mxGeometry x="40" y="108" width="120" height="20" as="geometry"/></mxCell>`);

  return `<?xml version="1.0" encoding="UTF-8"?>
<mxfile host="app.diagrams.net" modified="${new Date().toISOString()}" agent="BPMN Generator" version="21.0.0">
  <diagram name="BPMN: Контроль рентабельности" id="bpmn-1">
    <mxGraphModel dx="1200" dy="800" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1600" pageHeight="900">
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

  console.log('📝 Генерация BPMN draw.io...');
  const xml = generateDrawioXml(layout);

  const outputPath = `${outputDir}/bpmn-proper.drawio`;
  writeFileSync(outputPath, xml);
  console.log(`💾 Сохранено: ${outputPath}`);

  const pngPath = `${outputDir}/bpmn-proper.png`;
  try {
    console.log('🖼️  Экспорт в PNG...');
    execSync(`/Applications/draw.io.app/Contents/MacOS/draw.io -x -f png -o "${pngPath}" "${outputPath}"`, {
      timeout: 30000,
      stdio: 'pipe'
    });
    console.log(`✅ PNG: ${pngPath}`);
  } catch (e) {
    console.log('ℹ️  PNG экспорт...');
  }

  if (process.platform === 'darwin') {
    execSync(`open "${outputPath}"`);
  }

  console.log('\n✨ BPMN диаграмма готова!');
}

main().catch(console.error);
