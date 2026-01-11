#!/bin/bash
# Test runner script for text-to-SQL feature tests
# Usage: ./run_tests.sh [option]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}Text-to-SQL Feature Test Suite${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"

# Ensure we're in the API directory
if [ ! -f "pytest.ini" ]; then
    echo -e "${RED}Error: pytest.ini not found. Please run from api/ directory${NC}"
    exit 1
fi

# Function to run tests
run_all_tests() {
    echo -e "\n${YELLOW}Running all tests...${NC}"
    pytest tests/ -v --tb=short
}

run_unit_tests() {
    echo -e "\n${YELLOW}Running unit tests...${NC}"
    pytest tests/unit/ -v --tb=short
}

run_integration_tests() {
    echo -e "\n${YELLOW}Running integration tests...${NC}"
    pytest tests/integration/ -v --tb=short
}

run_evals() {
    echo -e "\n${YELLOW}Running evaluation tests...${NC}"
    pytest tests/evals/ -v --tb=short
}

run_fast_tests() {
    echo -e "\n${YELLOW}Running fast tests (excluding slow evals)...${NC}"
    pytest tests/ -m "not slow" -v --tb=short
}

run_with_coverage() {
    echo -e "\n${YELLOW}Running tests with coverage report...${NC}"
    pytest tests/ -v --cov=app --cov-report=html --cov-report=term-missing
    echo -e "\n${GREEN}Coverage report generated: htmlcov/index.html${NC}"
}

run_sql_validator_tests() {
    echo -e "\n${YELLOW}Running SQL validator tests...${NC}"
    pytest tests/unit/test_sql_validator.py -v --tb=short
}

run_llm_provider_tests() {
    echo -e "\n${YELLOW}Running LLM provider tests...${NC}"
    pytest tests/unit/test_llm_providers.py -v --tb=short
}

run_specific_test() {
    if [ -z "$1" ]; then
        echo -e "${RED}Error: Please provide test path${NC}"
        exit 1
    fi
    echo -e "\n${YELLOW}Running specific test: $1${NC}"
    pytest "$1" -v --tb=short
}

run_verbose() {
    echo -e "\n${YELLOW}Running all tests with verbose output...${NC}"
    pytest tests/ -vv -s --tb=long
}

show_help() {
    cat <<EOF
${BLUE}Test Runner - Text-to-SQL Feature${NC}

Usage: ./run_tests.sh [option]

Options:
    all            Run all tests
    unit           Run unit tests only
    integration    Run integration tests only
    evals          Run evaluation tests only
    fast           Run fast tests (exclude slow evals)
    coverage       Run tests with coverage report
    validator      Run SQL validator tests only
    providers      Run LLM provider tests only
    test <path>    Run specific test (e.g., tests/unit/test_sql_validator.py)
    verbose        Run with verbose output and print statements
    help           Show this help message

Examples:
    ./run_tests.sh all
    ./run_tests.sh unit
    ./run_tests.sh coverage
    ./run_tests.sh test tests/unit/test_sql_validator.py::TestSQLValidator::test_simple_select_query_valid

EOF
}

# Main logic
case "${1:-all}" in
    all)
        run_all_tests
        ;;
    unit)
        run_unit_tests
        ;;
    integration)
        run_integration_tests
        ;;
    evals)
        run_evals
        ;;
    fast)
        run_fast_tests
        ;;
    coverage)
        run_with_coverage
        ;;
    validator)
        run_sql_validator_tests
        ;;
    providers)
        run_llm_provider_tests
        ;;
    test)
        run_specific_test "$2"
        ;;
    verbose)
        run_verbose
        ;;
    help)
        show_help
        ;;
    *)
        echo -e "${RED}Unknown option: $1${NC}"
        show_help
        exit 1
        ;;
esac

echo -e "\n${GREEN}✓ Test run completed${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
