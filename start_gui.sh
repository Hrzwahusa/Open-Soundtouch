#!/bin/bash
# Quick Start Script für SoundTouch GUI
# Prüft Dependencies und startet die GUI

echo "========================================"
echo "   SoundTouch GUI - Quick Start"
echo "========================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 nicht gefunden!"
    echo "   Bitte installiere Python 3.7 oder höher"
    exit 1
fi

echo "✅ Python gefunden: $(python3 --version)"

# Check pip
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 nicht gefunden!"
    echo "   Bitte installiere pip3"
    exit 1
fi

echo "✅ pip3 gefunden"
echo ""

# Check PyQt5
echo "Prüfe Dependencies..."
if ! python3 -c "import PyQt5" 2>/dev/null; then
    echo "❌ PyQt5 nicht installiert"
    echo ""
    read -p "Möchtest du PyQt5 jetzt installieren? (j/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Jj]$ ]]; then
        echo "Installiere PyQt5..."
        pip3 install PyQt5 PyQt5-multimedia requests
    else
        echo "Installation abgebrochen"
        exit 1
    fi
else
    echo "✅ PyQt5 installiert"
fi

# Check PyQt5-multimedia
if ! python3 -c "import PyQt5.QtMultimedia" 2>/dev/null; then
    echo "⚠️  PyQt5-multimedia nicht installiert (für Media Player)"
    echo "   Installiere mit: pip3 install PyQt5-multimedia"
fi

# Check requests
if ! python3 -c "import requests" 2>/dev/null; then
    echo "❌ requests nicht installiert"
    pip3 install requests
fi

echo ""
echo "========================================"
echo "Starte SoundTouch GUI..."
echo "========================================"
echo ""

# Start GUI
python3 gui_linux_windows.py

echo ""
echo "GUI wurde geschlossen"
