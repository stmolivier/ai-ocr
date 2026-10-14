
# Installation

## Install Python env

```
# Install a venv
python -m venv venv

# Activate
venv\Scripts\activate

# Dépendencies
pip install pytesseract pillow
```

## Install tesseract

https://tesseract-ocr.github.io/tessdoc/Installation.html

For windows : https://github.com/UB-Mannheim/tesseract/wiki#tesseract-installer-for-windows
When Installing
- add language data
- select the "Add to PATH" option. (default C:\Program Files\Tesseract-OCR)


# Launch

```
python ocr_app.py
```

# Or create a executable `MiniOCR.exe`

Use `build_exe.bat`

If tesseract is installed, and you want to make this tool portable, you can copy the tesseract folder next to the executable (eg :C:\Program Files\Tesseract-OCR)


TODO : 
- improve the language detection
- add a translation system