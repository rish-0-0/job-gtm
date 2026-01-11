@echo off
REM Test runner script for text-to-SQL feature tests (Windows)
REM Usage: run_tests.bat [option]

setlocal enabledelayedexpansion

echo.
echo ===============================================================
echo Text-to-SQL Feature Test Suite
echo ===============================================================
echo.

REM Check if pytest.ini exists
if not exist "pytest.ini" (
    echo Error: pytest.ini not found. Please run from api\ directory
    exit /b 1
)

REM Determine which tests to run
if "%1"=="" (
    set "TEST_OPTION=all"
) else (
    set "TEST_OPTION=%1"
)

if "%TEST_OPTION%"=="all" (
    echo Running all tests...
    pytest tests/ -v --tb=short
    goto :eof
)

if "%TEST_OPTION%"=="unit" (
    echo Running unit tests...
    pytest tests/unit/ -v --tb=short
    goto :eof
)

if "%TEST_OPTION%"=="integration" (
    echo Running integration tests...
    pytest tests/integration/ -v --tb=short
    goto :eof
)

if "%TEST_OPTION%"=="evals" (
    echo Running evaluation tests...
    pytest tests/evals/ -v --tb=short
    goto :eof
)

if "%TEST_OPTION%"=="fast" (
    echo Running fast tests (excluding slow evals)...
    pytest tests/ -m "not slow" -v --tb=short
    goto :eof
)

if "%TEST_OPTION%"=="coverage" (
    echo Running tests with coverage report...
    pytest tests/ -v --cov=app --cov-report=html --cov-report=term-missing
    echo.
    echo Coverage report generated: htmlcov\index.html
    goto :eof
)

if "%TEST_OPTION%"=="validator" (
    echo Running SQL validator tests...
    pytest tests/unit/test_sql_validator.py -v --tb=short
    goto :eof
)

if "%TEST_OPTION%"=="providers" (
    echo Running LLM provider tests...
    pytest tests/unit/test_llm_providers.py -v --tb=short
    goto :eof
)

if "%TEST_OPTION%"=="test" (
    if "%2"=="" (
        echo Error: Please provide test path
        exit /b 1
    )
    echo Running specific test: %2
    pytest %2 -v --tb=short
    goto :eof
)

if "%TEST_OPTION%"=="verbose" (
    echo Running all tests with verbose output...
    pytest tests/ -vv -s --tb=long
    goto :eof
)

if "%TEST_OPTION%"=="help" (
    echo.
    echo Test Runner - Text-to-SQL Feature
    echo.
    echo Usage: run_tests.bat [option]
    echo.
    echo Options:
    echo     all            Run all tests
    echo     unit           Run unit tests only
    echo     integration    Run integration tests only
    echo     evals          Run evaluation tests only
    echo     fast           Run fast tests (exclude slow evals)
    echo     coverage       Run tests with coverage report
    echo     validator      Run SQL validator tests only
    echo     providers      Run LLM provider tests only
    echo     test ^<path^>    Run specific test
    echo     verbose        Run with verbose output and print statements
    echo     help           Show this help message
    echo.
    echo Examples:
    echo     run_tests.bat all
    echo     run_tests.bat unit
    echo     run_tests.bat coverage
    echo     run_tests.bat test tests/unit/test_sql_validator.py
    echo.
    goto :eof
)

echo Unknown option: %1
echo Run 'run_tests.bat help' for usage information
exit /b 1

:eof
echo.
echo Test run completed
echo ===============================================================
