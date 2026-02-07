#!/usr/bin/env node
/**
 * Создание BPMN диаграммы в Miro с авто-layout
 *
 * Использует: dagre для layout + Miro REST API для создания
 *
 * Требуется: MIRO_ACCESS_TOKEN и MIRO_BOARD_ID
 */

import dagre from 'dagre';

// Конфигурация
const CONFIG = {
  miroToken: process.env.MIRO_ACCESS_TOKEN,
  boardId: process.env.MIRO_BOARD_ID,
  // Размеры элементов
  nodeWidth: 180,
  nodeHeight: 80,
  gatewaySize: 60,
  eventSize: 40,
  // Отступы
  laneWidth: 250,
  lanePadding: 40,
  // Цвета BPMN
  colors: {
    startEvent: '#c8e6c9',
    endEventOk: '#c8e6c9',
    endEventError: '#ffcdd2',
    task: '#fff3e0',
    gateway: '#fff9c4',
    laneManager: '#e3f2fd',
    laneSystem: '#e8f5e9',
    laneApprover: '#fff8e1'
  }
};

/**
 * Определение процесса согласования рентабельности
 */
const processDefinition = {
  lanes: [
    { id: 'lane_manager', name: 'Менеджер', color: CONFIG.colors.laneManager },
    { id: 'lane_system', name: 'Система 1С:УТ', color: CONFIG.colors.laneSystem },
    { id: 'lane_approver', name: 'Согласующий (РБЮ/ДП/ГД)', color: CONFIG.colors.laneApprover }
  ],
  nodes: [
    { id: 'start', type: 'startEvent', label: 'Старт', lane: 'lane_manager' },
    { id: 'task1', type: 'task', label: 'Создать заказ клиента', lane: 'lane_manager' },
    { id: 'task2', type: 'task', label: 'Проверить актуальность НПСС', lane: 'lane_system' },
    { id: 'gw1', type: 'gateway', label: 'НПСС актуальна?', lane: 'lane_system' },
    { id: 'task3', type: 'task', label: 'Заблокировать заказ', lane: 'lane_system' },
    { id: 'end1', type: 'endEventError', label: 'Заблокирован', lane: 'lane_system' },
    { id: 'task4', type: 'task', label: 'Рассчитать рентабельность', lane: 'lane_system' },
    { id: 'gw2', type: 'gateway', label: 'Рент >= 0%?', lane: 'lane_system' },
    { id: 'task5', type: 'task', label: 'Автосогласование', lane: 'lane_system' },
    { id: 'end2', type: 'endEventOk', label: 'Согласовано', lane: 'lane_system' },
    { id: 'task6', type: 'task', label: 'Отправить на согласование', lane: 'lane_system' },
    { id: 'task7', type: 'task', label: 'Принять решение', lane: 'lane_approver' },
    { id: 'gw3', type: 'gateway', label: 'Решение?', lane: 'lane_approver' },
    { id: 'end3', type: 'endEventOk', label: 'Согласовано', lane: 'lane_approver' },
    { id: 'end4', type: 'endEventError', label: 'Отклонено', lane: 'lane_approver' }
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
    nodesep: 80,
    ranksep: 100,
    marginx: 50,
    marginy: 50
  });

  g.setDefaultEdgeLabel(() => ({}));

  // Добавляем узлы
  for (const node of process.nodes) {
    const size = node.type === 'gateway'
      ? { width: CONFIG.gatewaySize, height: CONFIG.gatewaySize }
      : node.type.includes('Event')
        ? { width: CONFIG.eventSize, height: CONFIG.eventSize }
        : { width: CONFIG.nodeWidth, height: CONFIG.nodeHeight };

    g.setNode(node.id, { ...size, ...node });
  }

  // Добавляем связи
  for (const edge of process.edges) {
    g.setEdge(edge.from, edge.to, { label: edge.label });
  }

  // Выполняем layout
  dagre.layout(g);

  // Извлекаем результаты
  const layoutedNodes = [];
  g.nodes().forEach(nodeId => {
    const node = g.node(nodeId);
    layoutedNodes.push({
      ...node,
      x: node.x,
      y: node.y,
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

  return { nodes: layoutedNodes, edges: layoutedEdges };
}

/**
 * Создает shape в Miro
 */
async function createMiroShape(node) {
  const shapeType = {
    startEvent: 'circle',
    endEventOk: 'circle',
    endEventError: 'circle',
    task: 'round_rectangle',
    gateway: 'rhombus'
  }[node.type] || 'rectangle';

  const fillColor = {
    startEvent: CONFIG.colors.startEvent,
    endEventOk: CONFIG.colors.endEventOk,
    endEventError: CONFIG.colors.endEventError,
    task: CONFIG.colors.task,
    gateway: CONFIG.colors.gateway
  }[node.type] || '#ffffff';

  const body = {
    data: {
      shape: shapeType,
      content: `<p>${node.label}</p>`
    },
    style: {
      fillColor: fillColor,
      borderColor: '#333333',
      borderWidth: '2'
    },
    geometry: {
      width: node.width,
      height: node.height
    },
    position: {
      x: node.x,
      y: node.y
    }
  };

  const response = await fetch(
    `https://api.miro.com/v2/boards/${CONFIG.boardId}/shapes`,
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${CONFIG.miroToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(body)
    }
  );

  if (!response.ok) {
    throw new Error(`Miro API error: ${response.status} ${await response.text()}`);
  }

  return response.json();
}

/**
 * Создает connector в Miro
 */
async function createMiroConnector(edge, nodeIdMap) {
  const body = {
    startItem: {
      id: nodeIdMap[edge.from]
    },
    endItem: {
      id: nodeIdMap[edge.to]
    },
    style: {
      strokeColor: '#333333',
      strokeWidth: '2',
      endStrokeCap: 'stealth'
    }
  };

  // Добавляем label если есть
  if (edge.label) {
    body.captions = [{
      content: edge.label,
      position: '50%'
    }];
  }

  const response = await fetch(
    `https://api.miro.com/v2/boards/${CONFIG.boardId}/connectors`,
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${CONFIG.miroToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(body)
    }
  );

  if (!response.ok) {
    throw new Error(`Miro connector error: ${response.status} ${await response.text()}`);
  }

  return response.json();
}

/**
 * Создает swimlane (frame) в Miro
 */
async function createMiroLane(lane, nodes, yOffset) {
  // Находим границы элементов в этом lane
  const laneNodes = nodes.filter(n => n.lane === lane.id);
  if (laneNodes.length === 0) return null;

  const minX = Math.min(...laneNodes.map(n => n.x - n.width/2)) - CONFIG.lanePadding;
  const maxX = Math.max(...laneNodes.map(n => n.x + n.width/2)) + CONFIG.lanePadding;
  const minY = Math.min(...laneNodes.map(n => n.y - n.height/2)) - CONFIG.lanePadding;
  const maxY = Math.max(...laneNodes.map(n => n.y + n.height/2)) + CONFIG.lanePadding;

  const body = {
    data: {
      title: lane.name,
      format: 'custom'
    },
    style: {
      fillColor: lane.color
    },
    geometry: {
      width: maxX - minX,
      height: maxY - minY
    },
    position: {
      x: (minX + maxX) / 2,
      y: (minY + maxY) / 2 + yOffset
    }
  };

  const response = await fetch(
    `https://api.miro.com/v2/boards/${CONFIG.boardId}/frames`,
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${CONFIG.miroToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(body)
    }
  );

  if (!response.ok) {
    console.warn(`Frame creation warning: ${response.status}`);
    return null;
  }

  return response.json();
}

/**
 * Создает swimlanes (frames) в Miro
 */
async function createSwimlanesInMiro(lanes, layoutedNodes) {
  console.log('📊 Создание swimlanes...');

  for (const lane of lanes) {
    const laneNodes = layoutedNodes.filter(n => n.lane === lane.id);
    if (laneNodes.length === 0) continue;

    // Считаем границы для горизонтального layout (LR)
    const minX = Math.min(...laneNodes.map(n => n.x - n.width/2)) - 40;
    const maxX = Math.max(...laneNodes.map(n => n.x + n.width/2)) + 40;
    const minY = Math.min(...laneNodes.map(n => n.y - n.height/2)) - 30;
    const maxY = Math.max(...laneNodes.map(n => n.y + n.height/2)) + 30;

    const body = {
      data: {
        title: lane.name,
        format: 'custom'
      },
      style: {
        fillColor: lane.color
      },
      geometry: {
        width: maxX - minX,
        height: maxY - minY
      },
      position: {
        x: (minX + maxX) / 2,
        y: (minY + maxY) / 2
      }
    };

    try {
      const response = await fetch(
        `https://api.miro.com/v2/boards/${CONFIG.boardId}/frames`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${CONFIG.miroToken}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(body)
        }
      );

      if (response.ok) {
        console.log(`  Swimlane: ${lane.name}`);
      } else {
        console.log(`  ⚠️ Swimlane ${lane.name}: ${response.status}`);
      }
    } catch (e) {
      console.log(`  ⚠️ Swimlane ${lane.name}: ${e.message}`);
    }
  }
}

async function main() {
  // Проверяем credentials
  if (!CONFIG.miroToken) {
    console.error('❌ MIRO_ACCESS_TOKEN не задан');
    console.log('\nУстановите переменные окружения:');
    console.log('  export MIRO_ACCESS_TOKEN="your-token"');
    console.log('  export MIRO_BOARD_ID="your-board-id"');
    console.log('\nПолучить токен: https://miro.com/app/settings/user-profile/apps');

    // Выводим layout для проверки
    console.log('\n--- Layout Preview (без Miro) ---');
    const layout = calculateLayout(processDefinition);
    console.log('Nodes:');
    layout.nodes.forEach(n => {
      console.log(`  ${n.id}: (${Math.round(n.x)}, ${Math.round(n.y)}) - ${n.label}`);
    });
    return;
  }

  if (!CONFIG.boardId) {
    console.error('❌ MIRO_BOARD_ID не задан');
    return;
  }

  console.log('📐 Расчет layout...');
  const layout = calculateLayout(processDefinition);

  // Сначала создаем swimlanes (frames)
  await createSwimlanesInMiro(processDefinition.lanes, layout.nodes);

  console.log('🎨 Создание элементов в Miro...');

  // Создаем shapes и сохраняем их ID
  const nodeIdMap = {};
  for (const node of layout.nodes) {
    console.log(`  Creating: ${node.label}`);
    const result = await createMiroShape(node);
    nodeIdMap[node.id] = result.id;
  }

  // Создаем connectors
  console.log('🔗 Создание связей...');
  for (const edge of layout.edges) {
    console.log(`  Connecting: ${edge.from} → ${edge.to}`);
    await createMiroConnector(edge, nodeIdMap);
  }

  console.log('\n✅ Диаграмма создана в Miro!');
  console.log(`   Board: https://miro.com/app/board/${CONFIG.boardId}/`);
}

main().catch(console.error);
