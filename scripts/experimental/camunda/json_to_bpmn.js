#!/usr/bin/env node
/**
 * Конвертер JSON (наш формат) → BPMN 2.0 XML (стандартный).
 * Layout генерируется автоматически через bpmn-auto-layout.
 * Fallback: собственный BFS-layout для сложных графов, где auto-layout падает.
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
 * Генерирует BPMN 2.0 XML (без DI) из нашего JSON-формата.
 * DI-секция добавляется позже через bpmn-auto-layout.
 * Возвращает { xml, processId, nodes, edges, lanes } — nodes/edges после обработки (loops broken, orphans removed).
 */
function jsonToBpmnSemantic(processJson) {
  let { name, lanes, nodes, edges } = processJson;
  nodes = nodes.map(n => ({...n}));
  edges = edges.map(e => ({...e}));
  const processId = `Process_${sanitizeId(name)}`;

  // Break loops: replace back-edges with end events + link annotations
  // Zeebe forbids straight-through loops in executable processes
  const backEdges = detectBackEdges(nodes, edges);
  if (backEdges.length > 0) {
    const result = breakLoops(nodes, edges, lanes, backEdges);
    nodes = result.nodes;
    edges = result.edges;
  }

  // Fix orphan nodes: non-start nodes with no incoming edges
  // bpmn-auto-layout crashes on these. Connect them via a gateway from start.
  const startNodes = nodes.filter(n => n.type === 'eventStart');
  const orphans = nodes.filter(n => {
    if (n.type === 'eventStart') return false;
    return !edges.some(e => e.to === n.id);
  });
  if (orphans.length > 0 && startNodes.length > 0) {
    // Find the first task connected to start
    const startEdge = edges.find(e => e.from === startNodes[0].id);
    const firstTask = startEdge ? startEdge.to : null;
    if (firstTask) {
      // Connect orphans: start → firstTask is already there
      // Add orphans as alternative paths from a gateway after start
      // Simplest: just remove orphan nodes and their edges (they're unreachable anyway)
      const orphanIds = new Set(orphans.map(n => n.id));
      // Also remove any nodes only reachable from orphans
      let changed = true;
      while (changed) {
        changed = false;
        for (const e of edges) {
          if (orphanIds.has(e.from) && !orphanIds.has(e.to)) {
            // Check if target has other incoming edges
            const otherIncoming = edges.filter(e2 => e2.to === e.to && !orphanIds.has(e2.from));
            if (otherIncoming.length === 0) {
              orphanIds.add(e.to);
              changed = true;
            }
          }
        }
      }
      nodes = nodes.filter(n => !orphanIds.has(n.id));
      edges = edges.filter(e => !orphanIds.has(e.from) && !orphanIds.has(e.to));
    }
  }

  // Collect error end events for bpmn:error declarations
  const errorNodes = nodes.filter(n => n.type === 'eventEndError');

  // Build gateway default flow map (last outgoing = default)
  const gwDefaultFlow = {};
  for (const node of nodes) {
    if (node.type === 'gateway') {
      const outgoing = edges.filter(e => e.from === node.id);
      if (outgoing.length > 1) {
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
                  exporterVersion="2.0">
`;

  // Declare errors
  for (const en of errorNodes) {
    const errorId = `Error_${en.id}`;
    const errorCode = en.id.toUpperCase();
    xml += `  <bpmn:error id="${errorId}" name="${escXml((en.label || en.id).replace(/\n/g, ' '))}" errorCode="${errorCode}" />\n`;
  }

  xml += `  <bpmn:process id="${processId}" name="${escXml(name)}" isExecutable="true">
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
      xml += `    <bpmn:task id="${node.id}" name="${escXml(label)}">\n`;
      const incoming = edges.filter(e => e.to === node.id);
      const outgoing = edges.filter(e => e.from === node.id);
      for (const e of incoming) xml += `      <bpmn:incoming>Flow_${e.from}_${e.to}</bpmn:incoming>\n`;
      for (const e of outgoing) xml += `      <bpmn:outgoing>Flow_${e.from}_${e.to}</bpmn:outgoing>\n`;
      xml += `    </bpmn:task>\n`;
    }
  }

  // Sequence Flows
  const defaultFlowIds = new Set(Object.values(gwDefaultFlow));

  for (const edge of edges) {
    const flowId = `Flow_${edge.from}_${edge.to}`;
    const label = edge.label ? ` name="${escXml(edge.label)}"` : '';
    const srcNode = nodes.find(n => n.id === edge.from);
    const isFromGateway = srcNode && srcNode.type === 'gateway';
    const isDefault = defaultFlowIds.has(flowId);

    if (isFromGateway && !isDefault && edge.label) {
      const feelExpr = `=condition = "${edge.label.replace(/"/g, '\\"')}"`;
      xml += `    <bpmn:sequenceFlow id="${flowId}"${label} sourceRef="${edge.from}" targetRef="${edge.to}">\n`;
      xml += `      <bpmn:conditionExpression xsi:type="bpmn:tFormalExpression">${escXml(feelExpr)}</bpmn:conditionExpression>\n`;
      xml += `    </bpmn:sequenceFlow>\n`;
    } else {
      xml += `    <bpmn:sequenceFlow id="${flowId}"${label} sourceRef="${edge.from}" targetRef="${edge.to}" />\n`;
    }
  }

  xml += `  </bpmn:process>
</bpmn:definitions>`;

  return { xml, processId, nodes, edges, lanes: lanes || [] };
}

/**
 * Обнаружение обратных ребер (back-edges) в графе через DFS.
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

    const endId = `end_loop_${i}`;
    const endLabel = `>> ${targetLabel}`;
    const endNode = {
      id: endId,
      type: 'eventEnd',
      label: endLabel,
      lane: sourceNode ? sourceNode.lane : (targetNode ? targetNode.lane : (lanes[0] && lanes[0].id))
    };
    newNodes.push(endNode);
    newEdges[idx] = { ...edge, to: endId };
  }

  return { nodes: newNodes, edges: newEdges };
}

function sanitizeId(name) {
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

/**
 * Fallback DI generator: BFS-based layout for processes where bpmn-auto-layout crashes.
 * Generates BPMN DI section with proper coordinates using topological ordering.
 */
function addFallbackDI(semanticXml, processId, nodes, edges) {
  const TASK_W = 100, TASK_H = 80;
  const EVENT_SIZE = 36;
  const GW_SIZE = 50;
  const X_GAP = 180;  // horizontal gap between columns
  const Y_GAP = 120;  // vertical gap between rows

  // BFS to assign columns (longest path from start for better visual)
  const adj = {};
  for (const n of nodes) adj[n.id] = [];
  for (const e of edges) {
    if (adj[e.from]) adj[e.from].push(e.to);
  }

  // Compute longest path from start to each node (for column assignment)
  const depth = {};
  for (const n of nodes) depth[n.id] = 0;

  // Topological sort via Kahn's algorithm
  const inDegree = {};
  for (const n of nodes) inDegree[n.id] = 0;
  for (const e of edges) inDegree[e.to] = (inDegree[e.to] || 0) + 1;

  const queue = nodes.filter(n => inDegree[n.id] === 0).map(n => n.id);
  const topoOrder = [];

  while (queue.length > 0) {
    const id = queue.shift();
    topoOrder.push(id);
    for (const next of (adj[id] || [])) {
      depth[next] = Math.max(depth[next], depth[id] + 1);
      inDegree[next]--;
      if (inDegree[next] === 0) queue.push(next);
    }
  }

  // Handle nodes not reached by topo sort (disconnected)
  for (const n of nodes) {
    if (!topoOrder.includes(n.id)) {
      topoOrder.push(n.id);
    }
  }

  // Group nodes by column
  const columns = {};
  for (const n of nodes) {
    const col = depth[n.id];
    if (!columns[col]) columns[col] = [];
    columns[col].push(n);
  }

  // Calculate positions
  const pos = {};
  const maxCol = Math.max(...Object.keys(columns).map(Number));

  for (let col = 0; col <= maxCol; col++) {
    const colNodes = columns[col] || [];
    for (let row = 0; row < colNodes.length; row++) {
      const n = colNodes[row];
      const isEvent = n.type === 'eventStart' || n.type === 'eventEnd' || n.type === 'eventEndError';
      const isGw = n.type === 'gateway';
      const w = isEvent ? EVENT_SIZE : (isGw ? GW_SIZE : TASK_W);
      const h = isEvent ? EVENT_SIZE : (isGw ? GW_SIZE : TASK_H);

      const x = 80 + col * X_GAP;
      const y = 60 + row * Y_GAP;

      pos[n.id] = { x, y, w, h };
    }
  }

  // Generate DI XML
  let di = `  <bpmndi:BPMNDiagram id="BPMNDiagram_${processId}">
    <bpmndi:BPMNPlane id="BPMNPlane_${processId}" bpmnElement="${processId}">
`;

  // Shape DI
  for (const n of nodes) {
    const p = pos[n.id];
    if (!p) continue;
    const isGw = n.type === 'gateway';
    di += `      <bpmndi:BPMNShape id="${n.id}_di" bpmnElement="${n.id}"${isGw ? ' isMarkerVisible="true"' : ''}>
        <dc:Bounds x="${p.x}" y="${p.y}" width="${p.w}" height="${p.h}" />
      </bpmndi:BPMNShape>
`;
  }

  // Edge DI
  for (const e of edges) {
    const flowId = `Flow_${e.from}_${e.to}`;
    const src = pos[e.from];
    const tgt = pos[e.to];
    if (!src || !tgt) continue;

    // Calculate connection points (right side of source, left side of target)
    const sx = src.x + src.w;
    const sy = src.y + src.h / 2;
    const tx = tgt.x;
    const ty = tgt.y + tgt.h / 2;

    if (Math.abs(sx - tx) < 10 && Math.abs(sy - ty) < 10) {
      // Same position, add offset
      di += `      <bpmndi:BPMNEdge id="${flowId}_di" bpmnElement="${flowId}">
        <di:waypoint x="${sx}" y="${sy}" />
        <di:waypoint x="${tx + 10}" y="${ty}" />
      </bpmndi:BPMNEdge>
`;
    } else if (tx <= sx) {
      // Backward/same-column edge: route around via bottom
      const midY = Math.max(sy, ty) + Y_GAP / 2;
      di += `      <bpmndi:BPMNEdge id="${flowId}_di" bpmnElement="${flowId}">
        <di:waypoint x="${sx}" y="${sy}" />
        <di:waypoint x="${sx + 30}" y="${sy}" />
        <di:waypoint x="${sx + 30}" y="${midY}" />
        <di:waypoint x="${tx - 30}" y="${midY}" />
        <di:waypoint x="${tx - 30}" y="${ty}" />
        <di:waypoint x="${tx}" y="${ty}" />
      </bpmndi:BPMNEdge>
`;
    } else if (Math.abs(sy - ty) < 5) {
      // Straight horizontal
      di += `      <bpmndi:BPMNEdge id="${flowId}_di" bpmnElement="${flowId}">
        <di:waypoint x="${sx}" y="${sy}" />
        <di:waypoint x="${tx}" y="${ty}" />
      </bpmndi:BPMNEdge>
`;
    } else {
      // L-shaped: go right, then up/down
      const midX = (sx + tx) / 2;
      di += `      <bpmndi:BPMNEdge id="${flowId}_di" bpmnElement="${flowId}">
        <di:waypoint x="${sx}" y="${sy}" />
        <di:waypoint x="${midX}" y="${sy}" />
        <di:waypoint x="${midX}" y="${ty}" />
        <di:waypoint x="${tx}" y="${ty}" />
      </bpmndi:BPMNEdge>
`;
    }
  }

  di += `    </bpmndi:BPMNPlane>
  </bpmndi:BPMNDiagram>`;

  // Insert DI before closing </bpmn:definitions>
  return semanticXml.replace('</bpmn:definitions>', di + '\n</bpmn:definitions>');
}

// === CLI ===

async function main() {
  const { layoutProcess } = await import('bpmn-auto-layout');

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
    const files = fs.readdirSync(processesDir).filter(f => f.endsWith('.json')).sort();
    console.log(`Конвертация ${files.length} процессов JSON -> BPMN 2.0 XML (auto-layout)...\n`);

    let ok = 0, fail = 0;
    for (const file of files) {
      const inputPath = path.join(processesDir, file);
      const baseName = path.basename(file, '.json');
      const outputPath = path.join(outputDir, `${baseName}.bpmn`);

      try {
        const json = JSON.parse(fs.readFileSync(inputPath, 'utf-8'));
        const { xml: semanticXml, processId, nodes, edges } = jsonToBpmnSemantic(json);
        let finalXml;
        try {
          finalXml = await layoutProcess(semanticXml);
        } catch (layoutErr) {
          // Fallback: own BFS-based DI layout
          console.warn(`  [WARN] auto-layout failed for ${file}, using BFS fallback`);
          finalXml = addFallbackDI(semanticXml, processId, nodes, edges);
        }
        fs.writeFileSync(outputPath, finalXml, 'utf-8');
        console.log(`  [OK] ${file} -> ${baseName}.bpmn (${json.name})`);
        ok++;
      } catch (e) {
        console.error(`  [ОШИБКА] ${file}: ${e.message}`);
        fail++;
      }
    }
    console.log(`\nГотово: ${ok} OK, ${fail} ошибок. BPMN файлы: ${outputDir}/`);
  } else {
    const inputPath = path.resolve(args[0]);
    const baseName = path.basename(inputPath, '.json');
    const outputPath = args[1] || path.join(outputDir, `${baseName}.bpmn`);

    const json = JSON.parse(fs.readFileSync(inputPath, 'utf-8'));
    const { xml: semanticXml, processId, nodes, edges } = jsonToBpmnSemantic(json);
    let layoutedXml;
    try {
      layoutedXml = await layoutProcess(semanticXml);
    } catch (layoutErr) {
      console.warn(`  [WARN] auto-layout failed, using BFS fallback`);
      layoutedXml = addFallbackDI(semanticXml, processId, nodes, edges);
    }
    fs.writeFileSync(outputPath, layoutedXml, 'utf-8');
    console.log(`[OK] ${inputPath} -> ${outputPath}`);
    console.log(`  Процесс: ${json.name}`);
    console.log(`  Ноды: ${json.nodes.length}, Ребра: ${json.edges.length}, Дорожки: ${json.lanes.length}`);
  }
}

main().catch(e => { console.error(e); process.exit(1); });
