#!/bin/bash
echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  💬  TERMCHAT v6.0 — Installation           ║"
echo "║  by Aboudev Labs 🇨🇮                         ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

curl -s https://raw.githubusercontent.com/daboujohan-hub/termchat/main/termchat.py -o "$PREFIX/bin/termchat.py"

sed -i '1s/^\xEF\xBB\xBF//' "$PREFIX/bin/termchat.py"
sed -i 's/\r$//' "$PREFIX/bin/termchat.py"

sed -i 's/127.0.0.1/junction.proxy.rlwy.net/g' "$PREFIX/bin/termchat.py"
sed -i 's/else 9999/else 35030/g' "$PREFIX/bin/termchat.py"

cat > "$PREFIX/bin/termchat" << 'EOL'
#!/data/data/com.termux/files/usr/bin/bash
exec python3 "$PREFIX/bin/termchat.py" "$@"
EOL

chmod +x "$PREFIX/bin/termchat" "$PREFIX/bin/termchat.py"

echo "✅ TermChat installé ! Lancement..."
echo ""
termchat
