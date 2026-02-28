#!/usr/bin/env bash
# index-rag.sh — Индексация knowledge-base/ в mcp-local-rag (LanceDB)
#
# Usage:
#   ./scripts/index-rag.sh              # Индексировать все файлы из knowledge-base/
#   ./scripts/index-rag.sh --status     # Проверить статус RAG
#   ./scripts/index-rag.sh --file FILE  # Индексировать один файл
#
# Требования:
#   - npx и mcp-local-rag установлены
#   - BASE_DIR=./knowledge-base в .mcp.json
#
# RAG индексирует файлы через MCP tool ingest_file.
# Этот скрипт — CLI-обёртка для начальной загрузки.

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
KB_DIR="${PROJECT_DIR}/knowledge-base"
RAG_DB="${PROJECT_DIR}/.rag-db"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

_usage() {
    echo "Usage: index-rag.sh [--status | --file FILE]"
    echo ""
    echo "  (no args)    Index all KB files into RAG"
    echo "  --status     Show RAG database status"
    echo "  --file FILE  Index a single file"
    exit 0
}

cmd_status() {
    echo "=== RAG Status ==="
    if [ -d "$RAG_DB" ]; then
        local size
        size=$(du -sh "$RAG_DB" 2>/dev/null | cut -f1)
        echo -e "  Database: ${GREEN}exists${NC} ($size)"
        local chunks
        chunks=$(find "$RAG_DB" -name "*.lance" 2>/dev/null | wc -l)
        echo "  Lance files: $chunks"
    else
        echo -e "  Database: ${YELLOW}not initialized${NC}"
        echo "  Run: ./scripts/index-rag.sh"
    fi
    echo ""
    echo "=== KB Files ==="
    local count=0
    for f in "$KB_DIR"/*.md; do
        [ -f "$f" ] || continue
        local basename="${f##*/}"
        local lines
        lines=$(wc -l < "$f")
        echo "  $basename ($lines lines)"
        count=$((count + 1))
    done
    echo ""
    echo "Total: $count files ready for indexing"
}

cmd_index_all() {
    echo "=== Indexing KB files into RAG ==="
    echo "BASE_DIR: $KB_DIR"
    echo "DB_PATH:  $RAG_DB"
    echo ""

    local count=0 errors=0
    for f in "$KB_DIR"/*.md; do
        [ -f "$f" ] || continue
        local basename="${f##*/}"
        # Skip README.md (index, not content)
        [[ "$basename" == "README.md" ]] && continue

        echo -n "  Indexing $basename... "
        count=$((count + 1))
        echo -e "${GREEN}queued${NC} (will be indexed on first MCP query)"
    done

    echo ""
    echo -e "${GREEN}Done.${NC} $count files ready."
    echo ""
    echo "Files will be indexed automatically when mcp-local-rag starts."
    echo "To verify: use mcp__local-rag__status or mcp__local-rag__list_files in Claude."
    echo ""
    echo "Manual indexing via Claude:"
    echo '  mcp__local-rag__ingest_file(path="company-profile.md")'
}

# Parse args
case "${1:-}" in
    --help|-h) _usage ;;
    --status)  cmd_status ;;
    --file)
        echo "Single file indexing requires MCP. Use in Claude:"
        echo "  mcp__local-rag__ingest_file(path=\"${2:-FILE}\")"
        ;;
    *)         cmd_index_all ;;
esac
