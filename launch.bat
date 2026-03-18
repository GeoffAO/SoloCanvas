@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo  SoloCanvas - Launch Script
echo ============================================================
echo.

:: Project root = directory containing this batch file
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

set "VENV_DIR=%ROOT%\.venv"

:: ── 1. Locate Python 3 on PATH ───────────────────────────────
set SYSTEM_PYTHON=

for %%C in (python3.exe python.exe) do (
    if not defined SYSTEM_PYTHON (
        for /f "delims=" %%P in ('where %%C 2^>nul') do (
            if not defined SYSTEM_PYTHON (
                echo %%P | findstr /i "WindowsApps" >nul 2>&1
                if errorlevel 1 (
                    for /f "tokens=2 delims= " %%V in ('"%%P" --version 2^>^&1') do (
                        for /f "tokens=1 delims=." %%M in ("%%V") do (
                            if "%%M"=="3" set SYSTEM_PYTHON=%%P
                        )
                    )
                )
            )
        )
    )
)

if not defined SYSTEM_PYTHON (
    echo [ERROR] Python 3 not found on PATH.
    echo.
    echo Please install Python 3 from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

for /f "tokens=2 delims= " %%V in ('"%SYSTEM_PYTHON%" --version 2^>^&1') do set PYVER=%%V
echo Found Python %PYVER%  (%SYSTEM_PYTHON%)

:: ── 2. Create virtual environment if needed ──────────────────
if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo.
    echo Creating virtual environment...
    "%SYSTEM_PYTHON%" -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        echo.
        echo Your Python installation may be missing the 'venv' module.
        echo Try: pip install virtualenv
        pause
        exit /b 1
    )
    echo   [OK] Virtual environment created at .venv\
)

set "PYTHON=%VENV_DIR%\Scripts\python.exe"
set "PYTHONW=%VENV_DIR%\Scripts\pythonw.exe"
set "PIP=%VENV_DIR%\Scripts\pip.exe"

:: ── 3. Check / install required packages ─────────────────────
echo.
echo Checking prerequisites...
echo.

set MISSING=0

call :check_pkg PyQt6        PyQt6
call :check_pkg qtawesome    qtawesome
call :check_pkg markdown     markdown
call :check_pkg markdownify  markdownify

if "%MISSING%"=="1" (
    echo.
    echo [INFO] Missing packages will be installed into the virtual environment.
    echo        Your system Python will not be modified.
    echo.
    set /p INSTALL="Install missing packages now? (Y/N): "
    if /i "!INSTALL!"=="Y" (
        echo.
        echo Installing missing packages...
        "%PIP%" install -r "%ROOT%\requirements.txt"
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

:: ── 4. Launch app (pythonw = no terminal window) ─────────────
echo.
echo Launching SoloCanvas...

if exist "%PYTHONW%" (
    start "" "%PYTHONW%" "%ROOT%\main.py"
) else (
    start "" /b "%PYTHON%" "%ROOT%\main.py"
)

exit /b 0

:: ── Helper: check if a package is importable ─────────────────
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
