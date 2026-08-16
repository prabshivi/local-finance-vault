#!/bin/bash
# Security Verification Suite (OSFI B-13 & PIPEDA Compliant)
set -e

# Change directory to script location
cd "$(dirname "$0")"

echo "=================================================="
echo "🔒 Running compliance & security audits..."
echo "=================================================="

echo ""
echo "🔍 [1/3] Running Bandit Static AST Vulnerability Scan..."
./.venv/bin/bandit -r src -ll

echo ""
echo "📦 [2/3] Running pip-audit Dependency Vulnerability Scan..."
./.venv/bin/pip-audit

echo ""
echo "🧪 [3/3] Running pytest Compliance & Security Tests..."
./.venv/bin/pytest --cov=core tests/

echo ""
echo "✅ All security and compliance validation checks passed!"
echo "=================================================="
