#!/bin/bash
echo "╔══════════════════════════════════════════════╗"
echo "║  💬  TERMCHAT v6.0 — Installation           ║"
echo "║  by Aboudev Labs 🇨🇮                         ║"
echo "╚══════════════════════════════════════════════╝"
echo "📦 Installation des dependances..."
if command -v pkg >/dev/null 2>&1; then
    # Termux : paquet precompile, evite de compiler cryptography via Rust/maturin
    pkg install -y python-cryptography >/dev/null 2>&1
fi
python3 -c "from cryptography.fernet import Fernet" 2>/dev/null || {
    # cryptography installe mais cffi (dependance native) manquant, ou pkg absent
    pip install --break-system-packages -q cffi cryptography 2>/dev/null || pip install -q cffi cryptography
}
python3 -c "from cryptography.fernet import Fernet" 2>/dev/null && echo "✅ Chiffrement pret." || echo "⚠️  cryptography indisponible - le chiffrement des messages ne fonctionnera pas."
curl -s https://raw.githubusercontent.com/daboujohan-hub/termchat/main/termchat.py -o $PREFIX/bin/termchat
chmod +x $PREFIX/bin/termchat
echo "✅ Installe! Lance: termchat"
