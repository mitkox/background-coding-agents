#!/bin/bash
# Setup Verification Script for Background Coding Agents
# This script tests that the package is installed and configured correctly

set -e  # Exit on error

echo "========================================"
echo "Background Coding Agents - Setup Verification"
echo "========================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print success
success() {
    echo -e "${GREEN}✓${NC} $1"
}

# Function to print error
error() {
    echo -e "${RED}✗${NC} $1"
}

# Function to print warning
warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Track overall status
ERRORS=0

# 1. Check Python version
echo "1. Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
REQUIRED="3.10"
if python3 -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)"; then
    success "Python $PYTHON_VERSION (>= 3.10 required)"
else
    error "Python $PYTHON_VERSION found, but 3.10+ is required"
    ((ERRORS++))
fi
echo ""

# 2. Check if package is installed
echo "2. Checking package installation..."
if python3 -c "import background_coding_agents" 2>/dev/null; then
    VERSION=$(python3 -c "import background_coding_agents; print(background_coding_agents.__version__)")
    success "background-coding-agents v$VERSION installed"
else
    error "Package not installed. Run: pip install -e '.[dev]'"
    ((ERRORS++))
fi
echo ""

# 3. Check development dependencies
echo "3. Checking development dependencies..."
DEPS=("black" "ruff" "mypy" "pytest" "pre-commit")
for dep in "${DEPS[@]}"; do
    if python3 -c "import $dep" 2>/dev/null || command -v $dep &> /dev/null; then
        success "$dep installed"
    else
        error "$dep not found. Run: pip install -e '.[dev]'"
        ((ERRORS++))
    fi
done
echo ""

# 4. Check linting (ruff)
echo "4. Running ruff linting..."
if command -v ruff &> /dev/null; then
    if ruff check src/ --quiet 2>&1 | grep -q "error"; then
        warning "Ruff found some issues (this is okay for now)"
    else
        success "Ruff check passed"
    fi
else
    error "Ruff not installed"
    ((ERRORS++))
fi
echo ""

# 5. Check formatting (black)
echo "5. Checking code formatting..."
if command -v black &> /dev/null; then
    if black src/ --check --quiet 2>/dev/null; then
        success "Code formatting is correct"
    else
        warning "Code needs formatting. Run: black src/"
    fi
else
    error "Black not installed"
    ((ERRORS++))
fi
echo ""

# 6. Check if .env.example exists
echo "6. Checking configuration files..."
if [ -f ".env.example" ]; then
    success ".env.example found"
    if [ -f ".env" ]; then
        success ".env file exists"
    else
        warning ".env file not found. Copy .env.example to .env and configure"
    fi
else
    error ".env.example not found"
    ((ERRORS++))
fi
echo ""

# 7. Check if pyproject.toml exists
echo "7. Checking project configuration..."
if [ -f "pyproject.toml" ]; then
    success "pyproject.toml found"
else
    error "pyproject.toml not found"
    ((ERRORS++))
fi
echo ""

# 8. Check pre-commit
echo "8. Checking pre-commit hooks..."
if [ -f ".pre-commit-config.yaml" ]; then
    success ".pre-commit-config.yaml found"
    if command -v pre-commit &> /dev/null; then
        if [ -f ".git/hooks/pre-commit" ]; then
            success "Pre-commit hooks installed"
        else
            warning "Pre-commit hooks not installed. Run: pre-commit install"
        fi
    else
        error "pre-commit not installed"
        ((ERRORS++))
    fi
else
    error ".pre-commit-config.yaml not found"
    ((ERRORS++))
fi
echo ""

# 9. Test package imports
echo "9. Testing package imports..."
if python3 -c "
from background_coding_agents import PLCAgent, FleetManager, SafetyVerifier, PLCCompilerVerifier
from background_coding_agents.agents.plc_agent import PLCChange
print('All imports successful')
" 2>/dev/null; then
    success "All package imports working"
else
    error "Package import failed"
    ((ERRORS++))
fi
echo ""

# 10. Check directory structure
echo "10. Checking directory structure..."
REQUIRED_DIRS=("src/background_coding_agents" "src/background_coding_agents/agents" "src/background_coding_agents/verifiers" "src/background_coding_agents/fleet_manager")
for dir in "${REQUIRED_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        success "$dir exists"
    else
        error "$dir missing"
        ((ERRORS++))
    fi
done
echo ""

# Summary
echo "========================================"
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed!${NC}"
    echo ""
    echo "Your setup is ready. Next steps:"
    echo "1. Copy .env.example to .env and configure"
    echo "2. Run: pre-commit install"
    echo "3. Review the documentation in AGENTS.md"
else
    echo -e "${RED}✗ $ERRORS check(s) failed${NC}"
    echo ""
    echo "Please fix the issues above before proceeding."
    exit 1
fi
echo "========================================"
