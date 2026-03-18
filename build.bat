@echo off
setlocal

echo ============================================================
echo  SoloCanvas - Build Script
echo ============================================================
echo.

:: Project root = directory containing this batch file
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

:: Locate Python 3 on PATH
set PYTHON=
for %%C in (python3.exe python.exe) do (
    if not defined PYTHON (
        for /f "delims=" %%P in ('where %%C 2^>nul') do (
            if not defined PYTHON (
                echo %%P | findstr /i "WindowsApps" >nul 2>&1
                if errorlevel 1 (
                    for /f "tokens=2 delims= " %%V in ('"%%P" --version 2^>^&1') do (
                        for /f "tokens=1 delims=." %%M in ("%%V") do (
                            if "%%M"=="3" set PYTHON=%%P
                        )
                    )
                )
            )
        )
    )
)

if not defined PYTHON (
    echo [ERROR] Python 3 not found on PATH.
    echo.
    echo Please install Python 3 from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

for /f "tokens=2 delims= " %%V in ('"%PYTHON%" --version 2^>^&1') do set PYVER=%%V
echo Found Python %PYVER%  (%PYTHON%)
echo.

:: Derive pip from the same directory as python
for /f "delims=" %%D in ("%PYTHON%") do set PYDIR=%%~dpD
set PIP=%PYDIR%pip.exe

:: Ensure PyInstaller is installed in the correct Python environment
echo Installing/verifying PyInstaller...
%PIP% install pyinstaller
if errorlevel 1 (
    echo [ERROR] Failed to install PyInstaller.
    pause
    exit /b 1
)

:: Clean previous build artefacts
if exist "dist\SoloCanvas" (
    echo Removing previous dist...
    rmdir /s /q "dist\SoloCanvas"
)
if exist "build\SoloCanvas" (
    rmdir /s /q "build\SoloCanvas"
)

echo Building SoloCanvas...
echo.

%PYTHON% -m PyInstaller ^
    --noconfirm ^
    --windowed ^
    --onedir ^
    --name SoloCanvas ^
    --distpath dist ^
    --workpath build ^
    --specpath build ^
    --icon "%ROOT%\resources\images\scrollcanvas.io.ico" ^
    --hidden-import "PyQt6.QtSvg" ^
    --hidden-import "PyQt6.QtSvgWidgets" ^
    --hidden-import "PyQt6.QtPdf" ^
    --hidden-import "PyQt6.QtPdfWidgets" ^
    --collect-all qtawesome ^
    --collect-all markdown ^
    main.py

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed. See output above.
    pause
    exit /b 1
)

:: Copy Dice and resources folders next to the exe
echo Copying Dice assets...
xcopy /e /i /y "%ROOT%\Dice" "dist\SoloCanvas\Dice" >nul

echo Copying resources...
xcopy /e /i /y "%ROOT%\resources" "dist\SoloCanvas\resources" >nul

:: Create the Decks folder next to the exe (users populate this with their own decks)
if not exist "dist\SoloCanvas\Decks" (
    mkdir "dist\SoloCanvas\Decks"
    echo Created dist\SoloCanvas\Decks\
)

:: Create the Images folder next to the exe (user image library)
if not exist "dist\SoloCanvas\Images" (
    mkdir "dist\SoloCanvas\Images"
    echo Created dist\SoloCanvas\Images\
)

:: Create the Notes folder next to the exe (global Markdown notepad storage)
if not exist "dist\SoloCanvas\Notes" (
    mkdir "dist\SoloCanvas\Notes"
    mkdir "dist\SoloCanvas\Notes\Images"
    echo Created dist\SoloCanvas\Notes\
)

echo.
echo ============================================================
echo  Build complete!
echo  Executable:  dist\SoloCanvas\SoloCanvas.exe
echo  Dice assets: dist\SoloCanvas\Dice\      (copied next to exe)
echo  Resources:   dist\SoloCanvas\resources\ (copied next to exe)
echo  Deck folder: dist\SoloCanvas\Decks\     (add your card decks here)
echo  Img folder:  dist\SoloCanvas\Images\    (add your images here)
echo ============================================================
echo.

endlocal
pause
