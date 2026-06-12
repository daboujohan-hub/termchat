#!/bin/bash
echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  💬  TERMCHAT v4.0 — Installation           ║"
echo "║  by Aboudev Labs 🇨🇮                         ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

curl -s https://raw.githubusercontent.com/daboujohan-hub/termchat/main/termchat.py -o $PREFIX/bin/termchat
sed -i 's/127.0.0.1/junction.proxy.rlwy.net/g' $PREFIX/bin/termchat
sed -i 's/else 9999/else 35030/g' $PREFIX/bin/termchat
chmod +x $PREFIX/bin/termchat

echo "✅ TermChat installé ! Lancement..."
echo ""
termchat
