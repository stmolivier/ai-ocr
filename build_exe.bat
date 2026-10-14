@echo off
REM Construit ocr_app.exe (un seul fichier, sans console) avec PyInstaller.
REM Lancer depuis le dossier contenant ocr_app.py

python -m pip install --upgrade pyinstaller pytesseract pillow
if errorlevel 1 goto :error

python -m PyInstaller --noconfirm --clean --onefile --windowed --name MiniOCR ocr_app.py
if errorlevel 1 goto :error

echo.
echo Termine : dist\MiniOCR.exe
echo (Optionnel) Pour un mode portable, copiez le dossier "Tesseract-OCR"
echo a cote de MiniOCR.exe.
goto :eof

:error
echo Echec de la compilation.
exit /b 1
