#!/bin/bash
# Install all dependencies for SoundTouch GUI

echo "========================================"
echo "   SoundTouch GUI - Full Setup"
echo "========================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 nicht gefunden!"
    exit 1
fi

echo "✅ Python: $(python3 --version)"

# Install/Upgrade pip
echo ""
echo "[*] Updating pip..."
python3 -m pip install --upgrade pip setuptools wheel -q

# Install core dependencies
echo "[*] Installing core dependencies..."
python3 -m pip install requests>=2.28.0 -q

# Install PyQt5
echo "[*] Installing PyQt5..."
python3 -m pip install PyQt5>=5.15.0 PyQt5-multimedia>=5.15.0 -q

# Install Kivy (optional, for Android)
echo "[*] Installing Kivy (optional for Android)..."
python3 -m pip install kivy>=2.2.0 -q 2>/dev/null || echo "   ⚠️  Kivy installation skipped (optional)"

# Install buildozer (optional, for Android APK building - Linux only)
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "[*] Installing buildozer (optional for Android APK)..."
    python3 -m pip install buildozer>=1.5.0 -q 2>/dev/null || echo "   ⚠️  Buildozer installation skipped (optional)"
fi

echo ""
echo "========================================"
echo "   Installation Complete"
echo "========================================"
echo ""

# Run diagnostic
echo "[*] Running diagnostic..."
python3 diagnostic.py

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. python3 gui_linux_windows.py    # Start Desktop GUI"
echo "2. ./start_gui.sh                   # Or use startup script"
echo ""
