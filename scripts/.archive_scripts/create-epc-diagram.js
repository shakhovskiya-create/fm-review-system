#!/usr/bin/env node
/**
 * Генератор ePC-диаграмм (Event-driven Process Chain)
 *
 * Стиль:
 * - Шестиугольники (события) - бежевые/зеленые/розовые
 * - Скругленные прямоугольники (функции) - голубые
 * - Ромбы XOR (развилки) - желтые
 * - Овалы (роли/системы) - серые, подключены пунктиром
 * - Вертикальный поток сверху вниз
 */

import dagre from 'dagre';
import { writeFileSync, mkdirSync, existsSync } from 'fs';
import { execSync } from 'child_process';
import { dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

// Конфигурация ePC
const CONFIG = {
  // Размеры элементов
  eventWidth: 120,
  eventHeight: 50,
  functionWidth: 140,
  functionHeight: 50,
  gatewaySize: 50,
  roleWidth: 90,
  roleHeight: 40,
  // Цвета ePC
  colors: {
    eventStart: '#98d8aa',      // Зеленый - стартовое событие
    eventNormal: '#ffd9b3',     // Бежевый - обычное событие
    eventSuccess: '#c8e6c9',    // Светло-зеленый - успех
    eventError: '#ffcdd2',      // Розовый - ошибка
    function: '#b3e0f2',        // Голубой - функция
    gateway: '#fff59d',         // Желтый - XOR
    role: '#f5f5f5',            // Серый - роль/система
    subprocess: '#e1bee7'       // Фиолетовый - подпроцесс
  },
  strokes: {
    event: '#666666',
    function: '#4a90a4',
    gateway: '#c9a227',
    role: '#999999'
  }
};

/**
 * Определение процесса в ePC нотации
 */
const processDefinition = {
  nodes: [
    // Стартовое событие
    { id: 'e1', type: 'eventStart', label: 'Заказ клиента\nсоздан' },
    { id: 'r1', type: 'role', label: '1С:ERP', connectTo: 'f1' },

    // Функция: Проверка НПСС
    { id: 'f1', type: 'function', label: 'Проверка НПСС\n(автоматически)' },

    // XOR: НПСС актуальна?
    { id: 'x1', type: 'gateway', label: 'XOR' },

    // Ветка "нет"
    { id: 'e2', type: 'eventError', label: 'НПСС\nне пройден' },

    // Ветка "да"
    { id: 'e3', type: 'eventNormal', label: 'НПСС\nпройден' },
    { id: 'f2', type: 'function', label: 'Расчет\nрентабельности' },

    // XOR: Рентабельность
    { id: 'x2', type: 'gateway', label: 'XOR' },

    // Ветка >= 0%
    { id: 'e4', type: 'eventNormal', label: 'Рентабельность\n>= 0%' },
    { id: 'f3', type: 'function', label: 'Авто-\nсогласование' },

    // Ветка < 0%
    { id: 'e5', type: 'eventNormal', label: 'Рентабельность\n< 0%' },
    { id: 'f4', type: 'subprocess', label: 'Процесс\nсогласования' },
    { id: 'r2', type: 'role', label: 'Согласующий', connectTo: 'f4' },

    // Результат согласования
    { id: 'e6', type: 'eventSuccess', label: 'Заказ\nсогласован' },
    { id: 'r3', type: 'role', label: 'Менеджер', connectTo: 'f5' },

    // Продолжение процесса
    { id: 'f5', type: 'function', label: 'Создание\nрезерва' },
    { id: 'e7', type: 'eventSuccess', label: 'Резерв\nсоздан' },
    { id: 'r4', type: 'role', label: 'Склад', connectTo: 'f6' },
    { id: 'f6', type: 'function', label: 'Отгрузка\nтовара' },
    { id: 'e8', type: 'eventSuccess', label: 'Заказ\nотгружен' }
  ],
  edges: [
    { from: 'e1', to: 'f1' },
    { from: 'f1', to: 'x1' },
    { from: 'x1', to: 'e2', label: 'нет' },
    { from: 'x1', to: 'e3', label: 'да' },
    { from: 'e3', to: 'f2' },
    { from: 'f2', to: 'x2' },
    { from: 'x2', to: 'e4', label: '>= 0%' },
    { from: 'x2', to: 'e5', label: '< 0%' },
    { from: 'e4', to: 'f3' },
    { from: 'e5', to: 'f4' },
    { from: 'f3', to: 'e6' },
    { from: 'f4', to: 'e6', label: 'согласовано' },
    { from: 'e6', to: 'f5' },
    { from: 'f5', to: 'e7' },
    { from: 'e7', to: 'f6' },
    { from: 'f6', to: 'e8' }
  ]
};

/**
 * Рассчитывает layout с помощью dagre
 */
function calculateLayout(process) {
  const g = new dagre.graphlib.Graph();

  g.setGraph({
    rankdir: 'TB',  // Top to Bottom (вертикальный поток)
    nodesep: 60,
    ranksep: 50,
    marginx: 80,
    marginy: 40
  });

  g.setDefaultEdgeLabel(() => ({}));

  // Добавляем только основные узлы (без ролей)
  const mainNodes = process.nodes.filter(n => n.type !== 'role');
  for (const node of mainNodes) {
    let size;
    switch (node.type) {
      case 'gateway':
        size = { width: CONFIG.gatewaySize, height: CONFIG.gatewaySize };
        break;
      case 'function':
      case 'subprocess':
        size = { width: CONFIG.functionWidth, height: CONFIG.functionHeight };
        break;
      default: // events
        size = { width: CONFIG.eventWidth, height: CONFIG.eventHeight };
    }
    g.setNode(node.id, { ...size, ...node });
  }

  // Добавляем связи (без ролей)
  for (const edge of process.edges) {
    g.setEdge(edge.from, edge.to, { label: edge.label });
  }

  dagre.layout(g);

  // Извлекаем результаты
  const layoutedNodes = [];
  g.nodes().forEach(nodeId => {
    const node = g.node(nodeId);
    layoutedNodes.push({
      ...node,
      x: Math.round(node.x),
      y: Math.round(node.y)
    });
  });

  // Добавляем роли сбоку от их функций
  const roles = process.nodes.filter(n => n.type === 'role');
  for (const role of roles) {
    const targetNode = layoutedNodes.find(n => n.id === role.connectTo);
    if (targetNode) {
      layoutedNodes.push({
        ...role,
        width: CONFIG.roleWidth,
        height: CONFIG.roleHeight,
        x: targetNode.x + targetNode.width/2 + 80,
        y: targetNode.y
      });
    }
  }

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

  return { nodes: layoutedNodes, edges: layoutedEdges, roles };
}

/**
 * Генерирует draw.io XML в стиле ePC
 */
function generateDrawioXml(layout, roles) {
  let cellId = 2;
  const nodeIdMap = {};
  const cells = [];

  // Создаем узлы
  for (const node of layout.nodes) {
    const id = cellId++;
    nodeIdMap[node.id] = id;

    const x = node.x - node.width / 2;
    const y = node.y - node.height / 2;

    let style = '';
    let fillColor = '';
    let strokeColor = CONFIG.strokes.event;

    switch (node.type) {
      case 'eventStart':
        fillColor = CONFIG.colors.eventStart;
        style = `shape=hexagon;perimeter=hexagonPerimeter2;fixedSize=1;fillColor=${fillColor};strokeColor=${strokeColor};`;
        break;
      case 'eventNormal':
        fillColor = CONFIG.colors.eventNormal;
        style = `shape=hexagon;perimeter=hexagonPerimeter2;fixedSize=1;fillColor=${fillColor};strokeColor=${strokeColor};`;
        break;
      case 'eventSuccess':
        fillColor = CONFIG.colors.eventSuccess;
        style = `shape=hexagon;perimeter=hexagonPerimeter2;fixedSize=1;fillColor=${fillColor};strokeColor=${strokeColor};`;
        break;
      case 'eventError':
        fillColor = CONFIG.colors.eventError;
        style = `shape=hexagon;perimeter=hexagonPerimeter2;fixedSize=1;fillColor=${fillColor};strokeColor=${strokeColor};`;
        break;
      case 'function':
        fillColor = CONFIG.colors.function;
        strokeColor = CONFIG.strokes.function;
        style = `rounded=1;fillColor=${fillColor};strokeColor=${strokeColor};`;
        break;
      case 'subprocess':
        fillColor = CONFIG.colors.subprocess;
        style = `rounded=1;fillColor=${fillColor};strokeColor=#9c27b0;dashed=1;dashPattern=8 8;`;
        break;
      case 'gateway':
        fillColor = CONFIG.colors.gateway;
        strokeColor = CONFIG.strokes.gateway;
        style = `rhombus;fillColor=${fillColor};strokeColor=${strokeColor};`;
        break;
      case 'role':
        fillColor = CONFIG.colors.role;
        strokeColor = CONFIG.strokes.role;
        style = `ellipse;fillColor=${fillColor};strokeColor=${strokeColor};`;
        break;
    }

    cells.push(`
      <mxCell id="${id}" value="${node.label}" style="${style}" vertex="1" parent="1">
        <mxGeometry x="${x}" y="${y}" width="${node.width}" height="${node.height}" as="geometry"/>
      </mxCell>`);
  }

  // Создаем обычные связи (сплошные стрелки)
  for (const edge of layout.edges) {
    const id = cellId++;
    const sourceId = nodeIdMap[edge.from];
    const targetId = nodeIdMap[edge.to];

    cells.push(`
      <mxCell id="${id}" value="${edge.label || ''}" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;endArrow=block;endFill=1;strokeColor=#333333;" edge="1" parent="1" source="${sourceId}" target="${targetId}">
        <mxGeometry relative="1" as="geometry"/>
      </mxCell>`);
  }

  // Создаем связи ролей (пунктирные линии)
  const roleNodes = layout.nodes.filter(n => n.type === 'role');
  for (const role of roleNodes) {
    const originalRole = roles.find(r => r.id === role.id);
    if (originalRole && originalRole.connectTo) {
      const id = cellId++;
      const sourceId = nodeIdMap[role.id];
      const targetId = nodeIdMap[originalRole.connectTo];

      cells.push(`
        <mxCell id="${id}" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;endArrow=none;dashed=1;strokeColor=#999999;" edge="1" parent="1" source="${sourceId}" target="${targetId}">
          <mxGeometry relative="1" as="geometry"/>
        </mxCell>`);
    }
  }

  return `<?xml version="1.0" encoding="UTF-8"?>
<mxfile host="app.diagrams.net" modified="${new Date().toISOString()}" agent="ePC Generator" version="21.0.0" type="device">
  <diagram name="ePC Process" id="epc-1">
    <mxGraphModel dx="1000" dy="1000" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1200" pageHeight="1600" math="0" shadow="0">
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

  console.log('📐 Расчет layout для ePC...');
  const roles = processDefinition.nodes.filter(n => n.type === 'role');
  const layout = calculateLayout(processDefinition);

  console.log('📝 Генерация draw.io XML в стиле ePC...');
  const xml = generateDrawioXml(layout, roles);

  const outputPath = `${outputDir}/epc-autolayout.drawio`;
  writeFileSync(outputPath, xml);
  console.log(`💾 Сохранено: ${outputPath}`);

  // Экспорт в PNG
  const pngPath = `${outputDir}/epc-autolayout.png`;
  try {
    console.log('🖼️  Экспорт в PNG...');
    execSync(`/Applications/draw.io.app/Contents/MacOS/draw.io -x -f png -o "${pngPath}" "${outputPath}"`, {
      timeout: 30000,
      stdio: 'pipe'
    });
    console.log(`✅ PNG: ${pngPath}`);
  } catch (e) {
    console.log('ℹ️  PNG экспорт пропущен');
  }

  // Открываем
  if (process.platform === 'darwin') {
    execSync(`open "${outputPath}"`);
  }

  console.log('\n✨ ePC диаграмма готова!');
}

main().catch(console.error);
