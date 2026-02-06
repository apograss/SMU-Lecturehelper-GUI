@echo off
setlocal

where uv >nul 2>&1
if %errorlevel%==0 (
    uv run python -c "import tkinter" >nul 2>&1
    if errorlevel 1 (
        echo tkinter is missing in the current Python environment.
        echo Install Python with tkinter support, then retry.
        pause
        exit /b 1
    )

    echo [1/2] Sync project dependencies...
    uv sync
    if errorlevel 1 (
        echo Dependency sync failed.
        pause
        exit /b 1
    )

    echo [2/2] Build one-file GUI executable...
    uv run --with pyinstaller pyinstaller --noconfirm --clean --windowed --onefile --name SMU-Lecture-Enroller-GUI gui.py
    if errorlevel 1 (
        echo Build failed.
        pause
        exit /b 1
    )
    goto :check_tk
)

echo uv not found, fallback to py + pip.
py -3 -c "import tkinter" >nul 2>&1
if errorlevel 1 (
    echo tkinter is missing in the current Python environment.
    echo Install Python with tkinter support, then retry.
    pause
    exit /b 1
)

echo [1/4] Bootstrap pip...
py -3 -m ensurepip --upgrade
if errorlevel 1 (
    echo pip bootstrap failed.
    pause
    exit /b 1
)

echo [2/4] Install runtime dependencies...
py -3 -m pip install requests beautifulsoup4 lxml pillow pycryptodome
if errorlevel 1 (
    echo Runtime dependency installation failed.
    pause
    exit /b 1
)

echo [3/4] Install pyinstaller...
py -3 -m pip install pyinstaller
if errorlevel 1 (
    echo PyInstaller installation failed.
    pause
    exit /b 1
)

echo [4/4] Build one-file GUI executable...
py -3 -m PyInstaller --noconfirm --clean --windowed --onefile --name SMU-Lecture-Enroller-GUI gui.py
if errorlevel 1 (
    echo Build failed.
    pause
    exit /b 1
)

:check_tk
set WARN_FILE=build\SMU-Lecture-Enroller-GUI\warn-SMU-Lecture-Enroller-GUI.txt
if exist "%WARN_FILE%" (
    findstr /c:"missing module named tkinter" "%WARN_FILE%" >nul
    if not errorlevel 1 (
        echo.
        echo tkinter is missing in current Python environment.
        echo The generated EXE cannot launch GUI.
        echo Install full CPython with tkinter support, then rebuild.
        pause
        exit /b 1
    )
)

:done
echo.
echo Build complete: dist\SMU-Lecture-Enroller-GUI.exe
pause
