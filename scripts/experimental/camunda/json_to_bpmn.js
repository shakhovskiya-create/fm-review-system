#!/usr/bin/env node
/**
 * Конвертер JSON (наш формат) → BPMN 2.0 XML (стандартный).
 *
 * Использование:
 *   node json_to_bpmn.js <input.json> [output.bpmn]
 *   node json_to_bpmn.js --all  (конвертирует все 13 процессов)
 */

const fs = require('fs');
const path = require('path');

// Маппинг наших типов → BPMN 2.0 элементы
const TYPE_MAP = {
  eventStart: 'bpmn:startEvent',
  eventEnd: 'bpmn:endEvent',
  eventEndError: 'bpmn:endEvent',
  task: 'bpmn:task',
  taskError: 'bpmn:task',
  subprocess: 'bpmn:subProcess',
  gateway: 'bpmn:exclusiveGateway'
};

/**
 * Генерирует BPMN 2.0 XML из нашего JSON-формата.
 */
function jsonToBpmn(processJson) {
  let { name, lanes, nodes, edges } = processJson;
  const processId = `Process_${sanitizeId(name)}`;

  // Break loops: replace back-edges with end events + link annotations
  // Zeebe forbids straight-through loops in executable processes
  const backEdges = detectBackEdges(nodes, edges);
  if (backEdges.length > 0) {
    const result = breakLoops(nodes, edges, lanes, backEdges);
    nodes = result.nodes;
    edges = result.edges;
  }

  // Координаты для DI (автоматическая раскладка LR)
  const positions = calculatePositions(nodes, edges, lanes);

  // Collect error end events for bpmn:error declarations
  const errorNodes = nodes.filter(n => n.type === 'eventEndError');

  // Build gateway default flow map (first outgoing = default)
  const gwDefaultFlow = {};
  for (const node of nodes) {
    if (node.type === 'gateway') {
      const outgoing = edges.filter(e => e.from === node.id);
      if (outgoing.length > 1) {
        // Last outgoing edge = default (no condition needed)
        gwDefaultFlow[node.id] = `Flow_${outgoing[outgoing.length - 1].from}_${outgoing[outgoing.length - 1].to}`;
      }
    }
  }

  let xml = `<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
                  xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
                  xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"
                  xmlns:di="http://www.omg.org/spec/DD/20100524/DI"
                  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                  xmlns:zeebe="http://camunda.org/schema/zeebe/1.0"
                  id="Definitions_1"
                  targetNamespace="http://bpmn.io/schema/bpmn"
                  exporter="fm-review-system"
                  exporterVersion="1.0">
`;

  // Declare errors
  for (const en of errorNodes) {
    const errorId = `Error_${en.id}`;
    const errorCode = en.id.toUpperCase();
    xml += `  <bpmn:error id="${errorId}" name="${escXml((en.label || en.id).replace(/\n/g, ' '))}" errorCode="${errorCode}" />\n`;
  }

  xml += `  <bpmn:collaboration id="Collaboration_1">
    <bpmn:participant id="Participant_1" name="${escXml(name)}" processRef="${processId}" />
  </bpmn:collaboration>
  <bpmn:process id="${processId}" name="${escXml(name)}" isExecutable="true">
`;

  // Lanes
  if (lanes && lanes.length > 0) {
    xml += `    <bpmn:laneSet id="LaneSet_1">\n`;
    for (const lane of lanes) {
      const laneNodes = nodes.filter(n => n.lane === lane.id);
      xml += `      <bpmn:lane id="Lane_${lane.id}" name="${escXml(lane.name.replace(/\n/g, ' '))}">\n`;
      for (const n of laneNodes) {
        xml += `        <bpmn:flowNodeRef>${n.id}</bpmn:flowNodeRef>\n`;
      }
      xml += `      </bpmn:lane>\n`;
    }
    xml += `    </bpmn:laneSet>\n`;
  }

  // Nodes
  for (const node of nodes) {
    const bpmnType = TYPE_MAP[node.type] || 'bpmn:task';
    const label = (node.label || '').replace(/\n/g, ' ').trim();

    if (bpmnType === 'bpmn:startEvent') {
      xml += `    <bpmn:startEvent id="${node.id}" name="${escXml(label)}">\n`;
      // Outgoing flows
      const outgoing = edges.filter(e => e.from === node.id);
      for (const e of outgoing) xml += `      <bpmn:outgoing>Flow_${e.from}_${e.to}</bpmn:outgoing>\n`;
      xml += `    </bpmn:startEvent>\n`;
    } else if (bpmnType === 'bpmn:endEvent') {
      xml += `    <bpmn:endEvent id="${node.id}" name="${escXml(label)}">\n`;
      const incoming = edges.filter(e => e.to === node.id);
      for (const e of incoming) xml += `      <bpmn:incoming>Flow_${e.from}_${e.to}</bpmn:incoming>\n`;
      if (node.type === 'eventEndError') {
        xml += `      <bpmn:errorEventDefinition id="ErrorDef_${node.id}" errorRef="Error_${node.id}" />\n`;
      }
      xml += `    </bpmn:endEvent>\n`;
    } else if (bpmnType === 'bpmn:exclusiveGateway') {
      const defaultFlowId = gwDefaultFlow[node.id] || '';
      const defaultAttr = defaultFlowId ? ` default="${defaultFlowId}"` : '';
      xml += `    <bpmn:exclusiveGateway id="${node.id}" name="${escXml(label)}"${defaultAttr}>\n`;
      const incoming = edges.filter(e => e.to === node.id);
      const outgoing = edges.filter(e => e.from === node.id);
      for (const e of incoming) xml += `      <bpmn:incoming>Flow_${e.from}_${e.to}</bpmn:incoming>\n`;
      for (const e of outgoing) xml += `      <bpmn:outgoing>Flow_${e.from}_${e.to}</bpmn:outgoing>\n`;
      xml += `    </bpmn:exclusiveGateway>\n`;
    } else if (bpmnType === 'bpmn:subProcess') {
      // Zeebe requires zeebe:calledElement for callActivity
      const calledProcessId = `Process_${sanitizeId(label || node.id)}`;
      xml += `    <bpmn:callActivity id="${node.id}" name="${escXml(label)}">\n`;
      xml += `      <bpmn:extensionElements>\n`;
      xml += `        <zeebe:calledElement processId="${calledProcessId}" propagateAllChildVariables="false" />\n`;
      xml += `      </bpmn:extensionElements>\n`;
      const incoming = edges.filter(e => e.to === node.id);
      const outgoing = edges.filter(e => e.from === node.id);
      for (const e of incoming) xml += `      <bpmn:incoming>Flow_${e.from}_${e.to}</bpmn:incoming>\n`;
      for (const e of outgoing) xml += `      <bpmn:outgoing>Flow_${e.from}_${e.to}</bpmn:outgoing>\n`;
      xml += `    </bpmn:callActivity>\n`;
    } else {
      // task / taskError
      xml += `    <bpmn:task id="${node.id}" name="${escXml(label)}">\n`;
      const incoming = edges.filter(e => e.to === node.id);
      const outgoing = edges.filter(e => e.from === node.id);
      for (const e of incoming) xml += `      <bpmn:incoming>Flow_${e.from}_${e.to}</bpmn:incoming>\n`;
      for (const e of outgoing) xml += `      <bpmn:outgoing>Flow_${e.from}_${e.to}</bpmn:outgoing>\n`;
      xml += `    </bpmn:task>\n`;
    }
  }

  // Sequence Flows (with conditions for gateway outputs)
  // Collect all default flow IDs for quick lookup
  const defaultFlowIds = new Set(Object.values(gwDefaultFlow));

  for (const edge of edges) {
    const flowId = `Flow_${edge.from}_${edge.to}`;
    const label = edge.label ? ` name="${escXml(edge.label)}"` : '';
    const srcNode = nodes.find(n => n.id === edge.from);
    const isFromGateway = srcNode && srcNode.type === 'gateway';
    const isDefault = defaultFlowIds.has(flowId);

    if (isFromGateway && !isDefault && edge.label) {
      // Non-default flow from gateway - add valid FEEL condition expression
      // Convert label to FEEL: condition = "label_text"
      const feelExpr = `=condition = "${edge.label.replace(/"/g, '\\"')}"`;
      xml += `    <bpmn:sequenceFlow id="${flowId}"${label} sourceRef="${edge.from}" targetRef="${edge.to}">\n`;
      xml += `      <bpmn:conditionExpression xsi:type="bpmn:tFormalExpression">${escXml(feelExpr)}</bpmn:conditionExpression>\n`;
      xml += `    </bpmn:sequenceFlow>\n`;
    } else {
      xml += `    <bpmn:sequenceFlow id="${flowId}"${label} sourceRef="${edge.from}" targetRef="${edge.to}" />\n`;
    }
  }

  xml += `  </bpmn:process>\n`;

  // BPMN DI (визуальная информация)
  xml += `  <bpmndi:BPMNDiagram id="BPMNDiagram_1">
    <bpmndi:BPMNPlane id="BPMNPlane_1" bpmnElement="Collaboration_1">
      <bpmndi:BPMNShape id="Participant_1_di" bpmnElement="Participant_1" isHorizontal="true">
        <dc:Bounds x="100" y="60" width="${positions.totalWidth}" height="${positions.totalHeight}" />
      </bpmndi:BPMNShape>\n`;

  // Lane shapes
  if (lanes) {
    let laneY = 60;
    for (const lane of lanes) {
      const laneHeight = positions.laneHeights[lane.id] || 150;
      xml += `      <bpmndi:BPMNShape id="Lane_${lane.id}_di" bpmnElement="Lane_${lane.id}" isHorizontal="true">
        <dc:Bounds x="130" y="${laneY}" width="${positions.totalWidth - 30}" height="${laneHeight}" />
      </bpmndi:BPMNShape>\n`;
      laneY += laneHeight;
    }
  }

  // Node shapes
  for (const node of nodes) {
    const pos = positions.nodes[node.id];
    const isEvent = node.type.startsWith('event');
    const isGateway = node.type === 'gateway';
    const w = isEvent ? 36 : (isGateway ? 50 : 100);
    const h = isEvent ? 36 : (isGateway ? 50 : 80);

    xml += `      <bpmndi:BPMNShape id="${node.id}_di" bpmnElement="${node.id}">
        <dc:Bounds x="${pos.x}" y="${pos.y}" width="${w}" height="${h}" />
      </bpmndi:BPMNShape>\n`;
  }

  // Edge shapes - orthogonal routing with gateway port separation
  // Pre-calculate gateway outgoing edge indices for port assignment
  const gwOutEdgeIdx = {};
  const gwOutEdgeCount = {};
  for (const node of nodes) {
    if (node.type === 'gateway') {
      const outgoing = edges.filter(e => e.from === node.id);
      gwOutEdgeCount[node.id] = outgoing.length;
      outgoing.forEach((e, i) => { gwOutEdgeIdx[`${e.from}_${e.to}`] = i; });
    }
  }

  // Track used vertical channels to offset parallel edges
  const usedChannels = [];

  function getChannelX(idealX) {
    // Find nearest free channel (avoid overlapping vertical segments)
    let x = idealX;
    const MIN_CHANNEL_GAP = 20;
    for (let attempt = 0; attempt < 10; attempt++) {
      const conflict = usedChannels.some(ch => Math.abs(ch - x) < MIN_CHANNEL_GAP);
      if (!conflict) break;
      x += MIN_CHANNEL_GAP;
    }
    usedChannels.push(x);
    return x;
  }

  for (const edge of edges) {
    const flowId = `Flow_${edge.from}_${edge.to}`;
    const srcPos = positions.nodes[edge.from];
    const tgtPos = positions.nodes[edge.to];
    const srcNode = nodes.find(n => n.id === edge.from);
    const tgtNode = nodes.find(n => n.id === edge.to);
    const srcIsEvent = srcNode && srcNode.type.startsWith('event');
    const srcIsGw = srcNode && srcNode.type === 'gateway';
    const tgtIsEvent = tgtNode && tgtNode.type.startsWith('event');
    const tgtIsGw = tgtNode && tgtNode.type === 'gateway';

    const srcW = srcIsEvent ? 36 : (srcIsGw ? 50 : 100);
    const srcH = srcIsEvent ? 36 : (srcIsGw ? 50 : 80);
    const tgtW = tgtIsEvent ? 36 : (tgtIsGw ? 50 : 100);
    const tgtH = tgtIsEvent ? 36 : (tgtIsGw ? 50 : 80);

    // Determine exit port for gateways with multiple outgoing edges
    let x1, y1;
    if (srcIsGw && gwOutEdgeCount[edge.from] > 1) {
      const idx = gwOutEdgeIdx[`${edge.from}_${edge.to}`] || 0;
      const count = gwOutEdgeCount[edge.from];
      const srcCX = srcPos.x + srcW / 2;
      const srcCY = srcPos.y + srcH / 2;
      if (count === 2) {
        // Two exits: top and bottom of diamond
        if (idx === 0) { x1 = srcCX; y1 = srcPos.y; } // top
        else { x1 = srcCX; y1 = srcPos.y + srcH; } // bottom
      } else if (count === 3) {
        // Three exits: top, right, bottom
        if (idx === 0) { x1 = srcCX; y1 = srcPos.y; } // top
        else if (idx === 1) { x1 = srcPos.x + srcW; y1 = srcCY; } // right
        else { x1 = srcCX; y1 = srcPos.y + srcH; } // bottom
      } else {
        // Fallback: right center
        x1 = srcPos.x + srcW;
        y1 = srcCY;
      }
    } else {
      // Non-gateway: exit from right center
      x1 = srcPos.x + srcW;
      y1 = srcPos.y + srcH / 2;
    }

    // Target: enter from left center
    const x2 = tgtPos.x;
    const y2 = tgtPos.y + tgtH / 2;

    // Orthogonal routing
    const waypoints = [];
    waypoints.push({ x: x1, y: y1 });

    if (Math.abs(y1 - y2) < 5 && x2 > x1) {
      // Same height, target to the right - straight horizontal line
      waypoints.push({ x: x2, y: y2 });
    } else if (x2 > x1 + 20) {
      // Target is to the right - use channel-separated vertical segment
      const channelX = getChannelX(Math.round((x1 + x2) / 2));
      waypoints.push({ x: channelX, y: y1 });
      waypoints.push({ x: channelX, y: y2 });
      waypoints.push({ x: x2, y: y2 });
    } else {
      // Target is behind or close - route around
      const detourX = Math.max(x1, x2 + tgtW) + 50;
      const detourY = y1 < y2 ? Math.max(y1, y2) + 80 : Math.min(y1, y2) - 80;
      waypoints.push({ x: detourX, y: y1 });
      waypoints.push({ x: detourX, y: detourY });
      waypoints.push({ x: x2 - 40, y: detourY });
      waypoints.push({ x: x2 - 40, y: y2 });
      waypoints.push({ x: x2, y: y2 });
    }

    xml += `      <bpmndi:BPMNEdge id="${flowId}_di" bpmnElement="${flowId}">\n`;
    for (const wp of waypoints) {
      xml += `        <di:waypoint x="${wp.x}" y="${wp.y}" />\n`;
    }
    xml += `      </bpmndi:BPMNEdge>\n`;
  }

  xml += `    </bpmndi:BPMNPlane>
  </bpmndi:BPMNDiagram>
</bpmn:definitions>`;

  return xml;
}

/**
 * Обнаружение обратных рёбер (back-edges) в графе через DFS.
 * Возвращает массив back-edge индексов в массиве edges.
 */
function detectBackEdges(nodes, edges) {
  const adj = {};
  for (const n of nodes) adj[n.id] = [];
  for (let i = 0; i < edges.length; i++) {
    adj[edges[i].from].push({ to: edges[i].to, idx: i });
  }

  const visited = new Set();
  const stack = new Set();
  const backEdgeIndices = [];

  function dfs(nodeId) {
    visited.add(nodeId);
    stack.add(nodeId);
    for (const { to, idx } of (adj[nodeId] || [])) {
      if (stack.has(to)) {
        backEdgeIndices.push(idx);
      } else if (!visited.has(to)) {
        dfs(to);
      }
    }
    stack.delete(nodeId);
  }

  for (const n of nodes) {
    if (!visited.has(n.id)) dfs(n.id);
  }
  return backEdgeIndices;
}

/**
 * Разрыв циклов: замена back-edges на end event-ы с аннотацией.
 * Каждое обратное ребро (from → target) заменяется на (from → end_loop_N),
 * где end_loop_N - новый end event с меткой "→ [target label]".
 */
function breakLoops(nodes, edges, lanes, backEdgeIndices) {
  const newNodes = [...nodes];
  const newEdges = [...edges];

  for (let i = 0; i < backEdgeIndices.length; i++) {
    const idx = backEdgeIndices[i];
    const edge = newEdges[idx];
    const targetNode = nodes.find(n => n.id === edge.to);
    const sourceNode = nodes.find(n => n.id === edge.from);
    const targetLabel = targetNode ? (targetNode.label || targetNode.id).replace(/\n/g, ' ') : edge.to;

    // Create end event to replace the back-edge target
    const endId = `end_loop_${i}`;
    const endLabel = `>> ${targetLabel}`;
    const endNode = {
      id: endId,
      type: 'eventEnd',
      label: endLabel,
      lane: sourceNode ? sourceNode.lane : (targetNode ? targetNode.lane : (lanes[0] && lanes[0].id))
    };
    newNodes.push(endNode);

    // Redirect the edge to the new end event
    newEdges[idx] = { ...edge, to: endId };
  }

  return { nodes: newNodes, edges: newEdges };
}

/**
 * Простая автоматическая раскладка LR (слева направо).
 * Группировка по уровням через BFS.
 */
function calculatePositions(nodes, edges, lanes) {
  // BFS для определения уровней
  const adjacency = {};
  const inDegree = {};
  for (const n of nodes) {
    adjacency[n.id] = [];
    inDegree[n.id] = 0;
  }
  for (const e of edges) {
    adjacency[e.from].push(e.to);
    inDegree[e.to] = (inDegree[e.to] || 0) + 1;
  }

  // Topological sort (Kahn's algorithm) для определения уровней
  const level = {};
  const queue = [];
  for (const n of nodes) {
    if (inDegree[n.id] === 0) {
      queue.push(n.id);
      level[n.id] = 0;
    }
  }

  while (queue.length > 0) {
    const curr = queue.shift();
    for (const next of adjacency[curr]) {
      level[next] = Math.max(level[next] || 0, (level[curr] || 0) + 1);
      inDegree[next]--;
      if (inDegree[next] === 0) queue.push(next);
    }
  }

  // Назначить уровни нодам без входящих (orphans)
  for (const n of nodes) {
    if (level[n.id] === undefined) level[n.id] = 0;
  }

  // Группируем по уровням
  const levelGroups = {};
  for (const n of nodes) {
    const l = level[n.id];
    if (!levelGroups[l]) levelGroups[l] = [];
    levelGroups[l].push(n);
  }

  // Lane index
  const laneIndex = {};
  (lanes || []).forEach((l, i) => { laneIndex[l.id] = i; });

  // Сортировка внутри уровня по lane
  for (const l in levelGroups) {
    levelGroups[l].sort((a, b) => (laneIndex[a.lane] || 0) - (laneIndex[b.lane] || 0));
  }

  // Размеры (увеличены для предотвращения наложений)
  const xGap = 240;
  const yGap = 150;
  const xOffset = 200;
  const yOffset = 80;
  const laneHeight = 180;

  // Lane Y-offsets
  const laneY = {};
  const laneHeights = {};
  let currentY = 60;
  for (const lane of (lanes || [])) {
    laneY[lane.id] = currentY;
    // Считаем сколько нод в этой lane (max nodes per level)
    let maxPerLevel = 1;
    for (const l in levelGroups) {
      const count = levelGroups[l].filter(n => n.lane === lane.id).length;
      if (count > maxPerLevel) maxPerLevel = count;
    }
    const h = Math.max(laneHeight, maxPerLevel * yGap + 40);
    laneHeights[lane.id] = h;
    currentY += h;
  }

  // Позиции
  const positions = {};
  const maxLevel = Math.max(...Object.keys(levelGroups).map(Number));

  // Для каждого уровня: трекер позиции Y внутри lane
  const laneYCounter = {};

  for (let l = 0; l <= maxLevel; l++) {
    const group = levelGroups[l] || [];
    // Сбрасываем per-lane counter
    for (const lane of (lanes || [])) {
      laneYCounter[lane.id] = 0;
    }

    for (const node of group) {
      const x = xOffset + l * xGap;
      const baseLaneY = laneY[node.lane] || yOffset;
      const laneH = laneHeights[node.lane] || laneHeight;
      const nodeIdx = laneYCounter[node.lane] || 0;

      // Центрируем ноды внутри lane
      const nodesInLane = group.filter(n => n.lane === node.lane).length;
      const totalNodeHeight = nodesInLane * yGap;
      const startY = baseLaneY + (laneH - totalNodeHeight) / 2 + 20;

      const y = startY + nodeIdx * yGap;
      positions[node.id] = { x, y };
      laneYCounter[node.lane] = nodeIdx + 1;
    }
  }

  const totalWidth = (maxLevel + 2) * xGap + xOffset;
  const totalHeight = currentY - 60;

  return { nodes: positions, laneHeights, totalWidth, totalHeight };
}

function sanitizeId(name) {
  // BPMN ID must be NCName (ASCII only)
  const map = {
    'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ж':'zh','з':'z',
    'и':'i','й':'j','к':'k','л':'l','м':'m','н':'n','о':'o','п':'p',
    'р':'r','с':'s','т':'t','у':'u','ф':'f','х':'h','ц':'c','ч':'ch',
    'ш':'sh','щ':'sch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya',
    'ё':'e',' ':'_'
  };
  let result = '';
  for (const ch of name.toLowerCase()) {
    result += map[ch] || (/[a-z0-9_]/.test(ch) ? ch : '_');
  }
  return result.replace(/_+/g, '_').replace(/^_|_$/g, '').substring(0, 50);
}

function escXml(str) {
  if (!str) return '';
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

// === CLI ===

function main() {
  const args = process.argv.slice(2);

  if (args.length === 0) {
    console.log('Использование:');
    console.log('  node json_to_bpmn.js <input.json> [output.bpmn]');
    console.log('  node json_to_bpmn.js --all');
    process.exit(1);
  }

  const processesDir = path.resolve(__dirname, '../../bpmn-processes');
  const outputDir = path.resolve(__dirname, 'output');

  if (!fs.existsSync(outputDir)) fs.mkdirSync(outputDir, { recursive: true });

  if (args[0] === '--all') {
    // Конвертировать все 13 процессов
    const files = fs.readdirSync(processesDir).filter(f => f.endsWith('.json')).sort();
    console.log(`Конвертация ${files.length} процессов JSON -> BPMN 2.0 XML...\n`);

    for (const file of files) {
      const inputPath = path.join(processesDir, file);
      const baseName = path.basename(file, '.json');
      const outputPath = path.join(outputDir, `${baseName}.bpmn`);

      try {
        const json = JSON.parse(fs.readFileSync(inputPath, 'utf-8'));
        const bpmnXml = jsonToBpmn(json);
        fs.writeFileSync(outputPath, bpmnXml, 'utf-8');
        console.log(`  [OK] ${file} -> ${baseName}.bpmn (${json.name})`);
      } catch (e) {
        console.error(`  [ОШИБКА] ${file}: ${e.message}`);
      }
    }
    console.log(`\nГотово. BPMN файлы: ${outputDir}/`);
  } else {
    // Один файл
    const inputPath = path.resolve(args[0]);
    const baseName = path.basename(inputPath, '.json');
    const outputPath = args[1] || path.join(outputDir, `${baseName}.bpmn`);

    const json = JSON.parse(fs.readFileSync(inputPath, 'utf-8'));
    const bpmnXml = jsonToBpmn(json);
    fs.writeFileSync(outputPath, bpmnXml, 'utf-8');
    console.log(`[OK] ${inputPath} -> ${outputPath}`);
    console.log(`  Процесс: ${json.name}`);
    console.log(`  Ноды: ${json.nodes.length}, Ребра: ${json.edges.length}, Дорожки: ${json.lanes.length}`);
  }
}

main();
