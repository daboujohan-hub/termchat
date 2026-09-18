#!/data/data/com.termux/files/usr/bin/bash

# TermChat v6.3 — Script d'installation
# by Aboudev Labs 🇨🇮 @github.dev.d.a.j

set -e

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  💬 TERMCHAT v6.3 Installation DEV.D.A.J    ║"
echo "║  by Aboudev Labs 🇨🇮 @github.dev.d.a.j       ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ── Vérification Termux ──
if [ -z "$PREFIX" ]; then
    echo "❌ ERREUR : cette installation est prévue pour Termux."
    echo "   La variable PREFIX n'est pas définie."
    exit 1
fi

# ── Vérification de curl ──
if ! command -v curl >/dev/null 2>&1; then
    echo "📦 Installation de curl..."
    pkg install -y curl
fi

# ── Vérification de Python ──
if ! command -v python3 >/dev/null 2>&1; then
    echo "📦 Python3 non trouvé. Installation..."
    pkg install -y python
fi

# ── Dépendances cryptographiques ──
if ! python3 -c "import cryptography" >/dev/null 2>&1; then
    echo "📦 Installation des dépendances..."

    pkg install -y python-cryptography 2>/dev/null || true

    if ! python3 -c "import cryptography" >/dev/null 2>&1; then
        pip install --break-system-packages cffi cryptography 2>/dev/null || \
        pip install cffi cryptography
    fi
fi

# ── Dossier d'installation ──
INSTALL_DIR="$PREFIX/bin"

# ── URL du client ──
CLIENT_URL="https://raw.githubusercontent.com/daboujohan-hub/termchat/main/termchat.py"

echo "⬇️  Téléchargement du client TermChat v6.3..."

curl -fLsS "$CLIENT_URL" -o "$INSTALL_DIR/termchat.py"

if [ ! -s "$INSTALL_DIR/termchat.py" ]; then
    echo "❌ ERREUR : le téléchargement a échoué."
    echo "   Vérifie ta connexion internet et le dépôt GitHub."
    exit 1
fi

# ── Nettoyage du fichier ──
sed -i '1s/^\xEF\xBB\xBF//' "$INSTALL_DIR/termchat.py"
sed -i 's/\r$//' "$INSTALL_DIR/termchat.py"

# ── Configuration serveur ──
sed -i 's/127\.0\.0\.1/junction.proxy.rlwy.net/g' "$INSTALL_DIR/termchat.py"
sed -i 's/else 9999/else 35030/g' "$INSTALL_DIR/termchat.py"

# ── Vérification Python du client ──
if ! python3 -m py_compile "$INSTALL_DIR/termchat.py"; then
    echo "❌ ERREUR : termchat.py contient une erreur Python."
    rm -f "$INSTALL_DIR/termchat.py"
    exit 1
fi

# ── Création du lanceur ──
cat > "$INSTALL_DIR/termchat" <<'WRAPPER'
#!/data/data/com.termux/files/usr/bin/bash
exec python3 "$PREFIX/bin/termchat.py" "$@"
WRAPPER

chmod +x "$INSTALL_DIR/termchat"
chmod +x "$INSTALL_DIR/termchat.py"

# ── Dossiers TermChat ──
mkdir -p "$HOME/termchat_downloads"
mkdir -p "$HOME/.termchat_tls"

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
