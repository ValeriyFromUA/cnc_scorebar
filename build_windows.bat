@echo off
REM Збірка Scorebar.exe для Windows. Запускати ЛИШЕ на Windows (PyInstaller
REM не вміє крос-компілювати з macOS/Linux на Windows).
REM
REM Використання:
REM   1. Встановіть Python 3.10+ на Windows.
REM   2. Відкрийте цю папку в cmd/PowerShell і запустіть: build_windows.bat
REM   3. Готовий файл буде в dist\Scorebar.exe

setlocal

python -m venv .venv_win
call .venv_win\Scripts\activate.bat

pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

pyinstaller --noconfirm --onefile --windowed --name Scorebar control_panel.py

echo.
echo Готово: dist\Scorebar.exe
endlocal
