@echo off
cd /d %~dp0
set PYTHONPATH=%~dp0vendor
python -m PyInstaller --noconfirm --clean --windowed --onefile --name MedSAM-Platform --collect-all tkinterdnd2 --add-data "vendor\tkinterdnd2\tkdnd;tkinterdnd2\tkdnd" app.py
if not exist D:\Download mkdir D:\Download
copy /Y dist\MedSAM-Platform.exe D:\Download\MedSAM-Platform.exe
echo.
echo Build complete: D:\Download\MedSAM-Platform.exe
pause
