#!/usr/bin/env node
/**
 * Рендер BPMN 2.0 XML → PNG через bpmn-to-image.
 *
 * Использование:
 *   node render_png.js <input.bpmn> [output.png]
 *   node render_png.js --all  (все BPMN из output/)
 *
 * Требует: npm install bpmn-to-image (в этой папке)
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const outputDir = path.resolve(__dirname, 'output');

function renderOne(bpmnPath, pngPath) {
  try {
    const cmd = `npx bpmn-to-image --no-footer --min-dimensions=1200x600 "${bpmnPath}:${pngPath}"`;
    execSync(cmd, {
      cwd: __dirname,
      stdio: ['pipe', 'pipe', 'pipe'],
      timeout: 60000
    });
    return true;
  } catch (e) {
    const stderr = e.stderr ? e.stderr.toString() : e.message;
    console.error(`  [ОШИБКА] ${path.basename(bpmnPath)}: ${stderr.substring(0, 200)}`);
    return false;
  }
}

function main() {
  const args = process.argv.slice(2);

  if (args.length === 0) {
    console.log('Использование:');
    console.log('  node render_png.js <input.bpmn> [output.png]');
    console.log('  node render_png.js --all');
    process.exit(1);
  }

  if (args[0] === '--all') {
    const bpmnFiles = fs.readdirSync(outputDir).filter(f => f.endsWith('.bpmn')).sort();
    console.log(`Рендер ${bpmnFiles.length} BPMN -> PNG...\n`);

    let ok = 0, fail = 0;
    for (const file of bpmnFiles) {
      const bpmnPath = path.join(outputDir, file);
      const pngPath = path.join(outputDir, file.replace('.bpmn', '.png'));
      process.stdout.write(`  ${file} -> ${path.basename(pngPath)} ... `);
      if (renderOne(bpmnPath, pngPath)) {
        console.log('OK');
        ok++;
      } else {
        fail++;
      }
    }
    console.log(`\nГотово: ${ok} OK, ${fail} ошибок`);
    console.log(`PNG файлы: ${outputDir}/`);
  } else {
    const bpmnPath = path.resolve(args[0]);
    const pngPath = args[1] || bpmnPath.replace('.bpmn', '.png');
    console.log(`Рендер: ${bpmnPath} -> ${pngPath}`);
    if (renderOne(bpmnPath, pngPath)) {
      console.log('[OK] PNG создан');
    } else {
      process.exit(1);
    }
  }
}

main();
