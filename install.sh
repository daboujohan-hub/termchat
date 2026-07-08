#!/bin/bash
echo "╔══════════════════════════════════════════════╗"
echo "║  💬  TERMCHAT v6.0 — Installation           ║"
echo "║  by Aboudev Labs 🇨🇮                         ║"
echo "╚══════════════════════════════════════════════╝"
echo "📦 Installation des dependances..."
pip install --break-system-packages -q cryptography 2>/dev/null || pip install -q cryptography
curl -s https://raw.githubusercontent.com/daboujohan-hub/termchat/main/termchat.py -o $PREFIX/bin/termchat
chmod +x $PREFIX/bin/termchat
echo "✅ Installe! Lance: termchat"
