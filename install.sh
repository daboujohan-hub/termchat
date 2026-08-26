#!/bin/bash
# -*- coding: utf-8 -*-
"""
TermChat v6.3 — Script d'installation
by Aboudev Labs 🇨🇮 @github.dev.d.a.j
"""

set -e

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  💬 TERMCHAT v6.3 Installation DEV.D.A.J    ║"
echo "║  by Aboudev Labs 🇨🇮 @github.dev.d.a.j       ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ── Vérifications ──
if [ -z "$PREFIX" ]; then
    echo "❌ ERREUR : cette installation est prévue pour Termux."
    echo "   La variable PREFIX n'est pas définie."
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo "📦 Python3 non trouvé. Installation..."
    pkg install -y python
fi

if ! python3 -c "import cryptography" 2>/dev/null; then
    echo "📦 Installation des dépendances (cryptography, cffi)..."
    pkg install -y python-cryptography 2>/dev/null || true
    pip install --break-system-packages cffi cryptography 2>/dev/null || pip install cffi cryptography
fi

# ── Téléchargement ──
INSTALL_DIR="$PREFIX/bin"
CLIENT_URL="https://raw.githubusercontent.com/daboujohan-hub/termchat/main/termchat.py"

echo "⬇️  Téléchargement du client TermChat v6.3..."
curl -sL "$CLIENT_URL" -o "$INSTALL_DIR/termchat.py"

if [ ! -s "$INSTALL_DIR/termchat.py" ]; then
    echo "❌ ERREUR : le téléchargement a échoué."
    echo "   Vérifie ta connexion internet et l'URL du repo."
    exit 1
fi

# ── Nettoyage ──
sed -i '1s/^\xEF\xBB\xBF//' "$INSTALL_DIR/termchat.py"
sed -i 's/\r$//' "$INSTALL_DIR/termchat.py"

# ── Configuration serveur (par défaut Railway) ──
sed -i 's/127\.0\.0\.1/junction.proxy.rlwy.net/g' "$INSTALL_DIR/termchat.py"
sed -i 's/else 9999/else 35030/g' "$INSTALL_DIR/termchat.py"

# ── Wrapper ──
cat > "$INSTALL_DIR/termchat" << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
exec python3 "$PREFIX/bin/termchat.py" "$@"
EOF

chmod +x "$INSTALL_DIR/termchat" "$INSTALL_DIR/termchat.py"

# ── Création du dossier downloads ──
mkdir -p "$HOME/termchat_downloads"

# ── Fin ──
echo ""
echo "✅ TermChat v6.3 installé avec succès !"
echo ""
echo "📱 Pour lancer :"
echo "   termchat"
echo ""
echo "📁 Fichiers reçus : ~/termchat_downloads/"
echo "🔐 Certificats TLS : ~/.termchat_tls/"
echo ""
echo "🆕 Nouveautés v6.3 :"
echo "   • Connexion directe (sans 2FA)"
echo "   • /signaler pour alerter l'administration"
echo "   • Surveillance et modération renforcées"
echo ""
