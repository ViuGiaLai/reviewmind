@echo off
REM ReviewMind Database & Migration Test Runner
REM ============================================

echo.
echo ========================================
echo  ReviewMind Database Test Runner
echo ========================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10+.
    exit /b 1
)

REM Install dependencies
echo [1/4] Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] pip install failed.
    exit /b 1
)
echo OK.

REM Run Alembic migration (SQLite)
echo.
echo [2/4] Running Alembic migration on SQLite...
set REVIEWMIND_AUTO_MIGRATE=false
python -m alembic upgrade head
if errorlevel 1 (
    echo [WARN] Alembic migration had issues - database may already exist.
)
echo OK.

REM Run database tests
echo.
echo [3/4] Running database tests...
python -m pytest tests/test_database.py -v --tb=short
if errorlevel 1 (
    echo.
    echo [WARN] Some tests failed. Check output above.
) else (
    echo All tests passed!
)

REM Also run engine tests
echo.
echo [4/4] Running existing engine tests...
python -m pytest tests/test_engine.py -v --tb=short
if errorlevel 1 (
    echo [WARN] Engine tests had failures.
)

echo.
echo ========================================
echo  Done!
echo ========================================
echo.
echo For PostgreSQL testing, set:
echo   set REVIEWMIND_PG_DSN=postgresql://user:pass@localhost:5432/reviewmind_test
echo   python -m pytest tests/test_database.py -v
echo.
pause
