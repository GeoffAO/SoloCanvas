@echo off
setlocal

echo ============================================================
echo  SoloCanvas - Launch Script
echo ============================================================
echo.

:: Python executable (same environment used by build.bat)
set PYTHON=C:\Users\popes\AppData\Local\Python\bin\python.exe
set PIP=C:\Users\popes\AppData\Local\Python\bin\pip.exe
set PYTHONW=C:\Users\popes\AppData\Local\Python\bin\pythonw.exe

:: ── 1. Check Python exists ───────────────────────────────────────
if not exist "%PYTHON%" (
    echo [ERROR] Python not found at:
    echo         %PYTHON%
    echo.
    echo Please install Python 3.14 to that location and re-run.
    pause
    exit /b 1
)

:: ── 2. Check Python version (must be 3.x) ────────────────────────
for /f "tokens=2 delims= " %%V in ('"%PYTHON%" --version 2^>^&1') do set PYVER=%%V
echo Found Python %PYVER%

:: Extract major.minor  (e.g. 3.14)
for /f "tokens=1,2 delims=." %%A in ("%PYVER%") do (
    set PY_MAJOR=%%A
    set PY_MINOR=%%B
)

if "%PY_MAJOR%" NEQ "3" (
    echo [ERROR] Python 3 is required. Found: %PYVER%
    pause
    exit /b 1
)

:: ── 3. Check / install required packages ────────────────────────
echo Checking prerequisites...
echo.

set MISSING=0

call :check_pkg PyQt6      PyQt6
call :check_pkg Pillow     PIL
call :check_pkg qtawesome  qtawesome

if "%MISSING%"=="1" (
    echo.
    echo [WARNING] Some packages are missing.
    set /p INSTALL="Install missing packages now? (Y/N): "
    if /i "%INSTALL%"=="Y" (
        echo.
        echo Installing missing packages...
        %PIP% install PyQt6 Pillow "qtawesome>=1.3.0"
        if errorlevel 1 (
            echo [ERROR] Installation failed. See output above.
            pause
            exit /b 1
        )
        echo.
        echo All packages installed successfully.
    ) else (
        echo Aborting launch. Install the missing packages and try again.
        pause
        exit /b 1
    )
) else (
    echo All prerequisites satisfied.
)

:: ── 4. Launch app (pythonw = no terminal window) ─────────────────
echo.
echo Launching SoloCanvas...

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

if exist "%PYTHONW%" (
    start "" "%PYTHONW%" "%ROOT%\main.py"
) else (
    :: Fallback: launch with python but hide window via start /b
    start "" /b "%PYTHON%" "%ROOT%\main.py"
)

exit /b 0

:: ── Helper: check if a package is importable ────────────────────
:check_pkg
set PKG_LABEL=%1
set PKG_IMPORT=%2
"%PYTHON%" -c "import %PKG_IMPORT%" >nul 2>&1
if errorlevel 1 (
    echo   [MISSING] %PKG_LABEL%
    set MISSING=1
) else (
    echo   [OK]      %PKG_LABEL%
)
goto :eof
