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

    uv run gui.py
    if errorlevel 1 (
        echo.
        echo GUI exited with an error.
        pause
        exit /b 1
    )
    exit /b 0
)

py -3 -c "import tkinter" >nul 2>&1
if errorlevel 1 (
    echo tkinter is missing in the current Python environment.
    echo Install Python with tkinter support, then retry.
    pause
    exit /b 1
)

py -3 gui.py
if errorlevel 1 (
    echo.
    echo GUI exited with an error.
    pause
    exit /b 1
)
