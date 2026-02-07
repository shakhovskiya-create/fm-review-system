#!/usr/bin/env node
/**
 * Универсальный генератор BPMN-диаграмм из JSON
 *
 * Использование:
 *   node generate-bpmn.js <input.json> [output-dir]
 *
 * Примеры:
 *   node generate-bpmn.js bpmn-processes/process-1-rentability.json
 *   node generate-bpmn.js bpmn-processes/process-1-rentability.json ./output
 */

import dagre from 'dagre';
import { writeFileSync, readFileSync, mkdirSync, existsSync } from 'fs';
import { execSync } from 'child_process';
import { dirname, basename, join } from 'path';
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

const CONFIG = {
  taskMinWidth: 100,
  taskMaxWidth: 180,
  taskMinHeight: 50,
  charWidth: 7,
  lineHeight: 16,
  taskPadding: 20,
  gatewaySize: 45,
  eventSize: 35,
  laneHeaderWidth: 35,
  lanePadding: 30,
  eventLabelSpace: 35,
  colors: {
    task: '#fff2cc',
    taskError: '#f8cecc',
    gateway: '#fff2cc',
    eventStart: '#d5e8d4',
    eventEnd: '#d5e8d4',
    eventEndError: '#f8cecc',
    subprocess: '#e1d5e7',
    pool: '#f5f5f5',
    // Дефолтные цвета lanes (можно переопределить в JSON)
    laneDefault: '#ffffff'
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

function calculateTaskSize(label) {
  if (!label) return { width: CONFIG.taskMinWidth, height: CONFIG.taskMinHeight };

  const lines = label.split('\n');
  const maxLineLength = Math.max(...lines.map(l => l.length));
  const textWidth = maxLineLength * CONFIG.charWidth;
  const width = Math.min(CONFIG.taskMaxWidth, Math.max(CONFIG.taskMinWidth, textWidth + CONFIG.taskPadding));
  const textHeight = lines.length * CONFIG.lineHeight;
  const height = Math.max(CONFIG.taskMinHeight, textHeight + CONFIG.taskPadding);

  return { width, height };
}

function calculateLayout(process) {
  const g = new dagre.graphlib.Graph();
  g.setGraph({
    rankdir: 'LR',
    nodesep: 70,
    ranksep: 70,
    marginx: 40,
    marginy: 50
  });
  g.setDefaultEdgeLabel(() => ({}));

  for (const node of process.nodes) {
    let size;
    if (node.type === 'gateway') {
      size = { width: CONFIG.gatewaySize, height: CONFIG.gatewaySize };
    } else if (node.type.includes('event')) {
      size = { width: CONFIG.eventSize, height: CONFIG.eventSize };
    } else {
      size = calculateTaskSize(node.label);
    }
    g.setNode(node.id, { ...size, ...node });
  }

  for (const edge of process.edges) {
    g.setEdge(edge.from, edge.to, { label: edge.label });
  }

  dagre.layout(g);

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

  const laneInfo = {};
  let currentY = 0;

  for (const lane of process.lanes) {
    const nodes = laneNodes[lane.id];
    if (nodes.length === 0) {
      laneInfo[lane.id] = { y: currentY, height: 100 };
      currentY += 100;
      continue;
    }

    let minY = Infinity, maxY = -Infinity;
    for (const node of nodes) {
      minY = Math.min(minY, node.y - node.height / 2);
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

  let globalMinX = Infinity;
  for (const lane of process.lanes) {
    for (const node of laneNodes[lane.id]) {
      globalMinX = Math.min(globalMinX, node.x - node.width / 2);
    }
  }

  const layoutedNodes = [];
  for (const lane of process.lanes) {
    const nodes = laneNodes[lane.id];
    const info = laneInfo[lane.id];

    for (const node of nodes) {
      const relX = (node.x - globalMinX) + 80 + CONFIG.lanePadding;
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

function generateDrawioXml(layout, processName, diagramName) {
  let cellId = 2;
  const nodeIdMap = {};
  const cells = [];
  const laneIdMap = {};

  const maxX = Math.max(...layout.nodes.map(n => n.x + n.width/2)) + CONFIG.lanePadding;
  const totalWidth = maxX + CONFIG.laneHeaderWidth + 50;
  const totalHeight = Object.values(layout.laneInfo).reduce((sum, info) => Math.max(sum, info.y + info.height), 0);

  const poolId = cellId++;
  cells.push(`
      <mxCell id="${poolId}" value="${xmlEncode(processName)}" style="swimlane;html=1;horizontal=0;startSize=30;fillColor=${CONFIG.colors.pool};strokeColor=#666666;" vertex="1" parent="1">
        <mxGeometry x="40" y="60" width="${totalWidth}" height="${totalHeight}" as="geometry"/>
      </mxCell>`);

  let laneY = 0;
  for (const lane of layout.lanes) {
    const info = layout.laneInfo[lane.id];
    const laneId = cellId++;
    laneIdMap[lane.id] = laneId;
    const laneColor = lane.color || CONFIG.colors.laneDefault;

    cells.push(`
      <mxCell id="${laneId}" value="${xmlEncode(lane.name)}" style="swimlane;html=1;horizontal=0;startSize=80;fillColor=${laneColor};strokeColor=${CONFIG.strokes.lane};" vertex="1" parent="${poolId}">
        <mxGeometry x="30" y="${laneY}" width="${totalWidth - 30}" height="${info.height}" as="geometry"/>
      </mxCell>`);
    laneY += info.height;
  }

  for (const node of layout.nodes) {
    const id = cellId++;
    nodeIdMap[node.id] = id;

    const parentLaneId = laneIdMap[node.lane];
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

    const cellValue = (node.type === 'gateway' || node.type.includes('event')) ? '' : xmlEncode(node.label);

    cells.push(`
      <mxCell id="${id}" value="${cellValue}" style="${style}" vertex="1" parent="${parentLaneId}">
        <mxGeometry x="${relX}" y="${relY}" width="${node.width}" height="${node.height}" as="geometry"/>
      </mxCell>`);

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

  // Легенда убрана - описание есть в тексте ФМ

  return `<?xml version="1.0" encoding="UTF-8"?>
<mxfile host="app.diagrams.net" modified="${new Date().toISOString()}" agent="BPMN Generator" version="21.0.0">
  <diagram name="${xmlEncode(diagramName)}" id="bpmn-1">
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
  const args = process.argv.slice(2);
  const noOpen = args.includes('--no-open');
  const positionalArgs = args.filter(a => !a.startsWith('--'));

  if (positionalArgs.length === 0) {
    console.log(`
Использование: node generate-bpmn.js <input.json> [output-dir] [--no-open]

Примеры:
  node generate-bpmn.js bpmn-processes/process-1-rentability.json
  node generate-bpmn.js bpmn-processes/process-1-rentability.json ./output
  node generate-bpmn.js bpmn-processes/process-1-rentability.json --no-open
    `);
    process.exit(1);
  }

  const inputPath = positionalArgs[0];
  const outputDir = positionalArgs[1] || `${__dirname}/output`;

  if (!existsSync(inputPath)) {
    console.error(`Ошибка: файл не найден: ${inputPath}`);
    process.exit(1);
  }

  if (!existsSync(outputDir)) {
    mkdirSync(outputDir, { recursive: true });
  }

  console.log(`📄 Загрузка: ${inputPath}`);
  const processDefinition = JSON.parse(readFileSync(inputPath, 'utf-8'));

  const processName = processDefinition.name || 'BPMN Process';
  const diagramName = processDefinition.diagramName || `BPMN: ${processName}`;

  console.log(`📐 Расчет layout для "${processName}"...`);
  const layout = calculateLayout(processDefinition);

  console.log('📝 Генерация draw.io XML...');
  const xml = generateDrawioXml(layout, processName, diagramName);

  // Имя выходного файла на основе имени входного
  const inputBaseName = basename(inputPath, '.json');
  const outputPath = join(outputDir, `${inputBaseName}.drawio`);
  writeFileSync(outputPath, xml);
  console.log(`💾 Сохранено: ${outputPath}`);

  const pngPath = join(outputDir, `${inputBaseName}.png`);
  try {
    console.log('🖼️  Экспорт в PNG...');
    execSync(`/Applications/draw.io.app/Contents/MacOS/draw.io -x -f png -o "${pngPath}" "${outputPath}"`, {
      timeout: 30000,
      stdio: 'pipe'
    });
    console.log(`✅ PNG: ${pngPath}`);
  } catch (e) {
    console.log('⚠️  PNG экспорт пропущен (draw.io не найден или ошибка)');
  }

  if (process.platform === 'darwin' && !noOpen) {
    execSync(`open "${outputPath}"`);
  }

  console.log(`\n✨ Диаграмма "${processName}" готова!`);
}

main().catch(console.error);
