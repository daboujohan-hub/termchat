#!/data/data/com.termux/files/usr/bin/bash

# ============================================================
# TermChat v6.3 — Script d'installation
# by Aboudev Labs 🇨🇮 @github.dev.d.a.j
# ============================================================

set -e

VERSION="6.3"
INSTALL_DIR="$PREFIX/bin"
CLIENT_URL="https://raw.githubusercontent.com/daboujohan-hub/termchat/main/termchat.py"
DOC_DIR="$HOME/termchat_docs"

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  💬 TERMCHAT v6.3 Installation DEV.D.A.J    ║"
echo "║  by Aboudev Labs 🇨🇮 @github.dev.d.a.j       ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ============================================================
# POLITIQUE DE CONFIANCE
# ============================================================

echo "🔐 POLITIQUE DE CONFIANCE"
echo ""
echo "Cette installation va :"
echo "  • télécharger le client TermChat depuis GitHub ;"
echo "  • installer les dépendances nécessaires ;"
echo "  • créer la commande « termchat » ;"
echo "  • créer le dossier des téléchargements ;"
echo "  • créer le dossier des certificats TLS ;"
echo "  • créer une documentation locale."
echo ""
echo "ℹ️  L'installateur ne demande pas :"
echo "  • votre mot de passe personnel ;"
echo "  • vos codes de paiement ;"
echo "  • votre code PIN ;"
echo "  • vos informations bancaires."
echo ""
echo "📌 Source du client :"
echo "   $CLIENT_URL"
echo ""

printf "Continuer l'installation ? [O/n] : "
read -r CONFIRM < /dev/tty

case "$CONFIRM" in
    n|N|non|NON|Non)
        echo ""
        echo "❌ Installation annulée."
        exit 0
        ;;
esac

echo ""
echo "✅ Installation autorisée."
echo ""

# ============================================================
# VÉRIFICATION TERMUX
# ============================================================

if [ -z "$PREFIX" ]; then
    echo "❌ ERREUR : cette installation est prévue pour Termux."
    echo "   La variable PREFIX n'est pas définie."
    exit 1
fi

# ============================================================
# CURL
# ============================================================

if ! command -v curl >/dev/null 2>&1; then
    echo "📦 Installation de curl..."
    pkg install -y curl
fi

# ============================================================
# PYTHON
# ============================================================

if ! command -v python3 >/dev/null 2>&1; then
    echo "📦 Python3 non trouvé. Installation..."
    pkg install -y python
fi

# ============================================================
# CRYPTOGRAPHY
# ============================================================

if ! python3 -c "import cryptography" >/dev/null 2>&1; then
    echo "📦 Installation des dépendances cryptographiques..."

    pkg install -y python-cryptography 2>/dev/null || true

    if ! python3 -c "import cryptography" >/dev/null 2>&1; then
        pip install --break-system-packages cffi cryptography 2>/dev/null || \
        pip install cffi cryptography
    fi
fi

# ============================================================
# TÉLÉCHARGEMENT DU CLIENT
# ============================================================

echo "⬇️  Téléchargement du client TermChat v$VERSION..."

curl -fLsS "$CLIENT_URL" -o "$INSTALL_DIR/termchat.py"

if [ ! -s "$INSTALL_DIR/termchat.py" ]; then
    echo "❌ ERREUR : le téléchargement du client a échoué."
    echo "   Vérifie ta connexion internet et le dépôt GitHub."
    exit 1
fi

# ============================================================
# NETTOYAGE
# ============================================================

sed -i '1s/^\xEF\xBB\xBF//' "$INSTALL_DIR/termchat.py"
sed -i 's/\r$//' "$INSTALL_DIR/termchat.py"

# ============================================================
# CONFIGURATION SERVEUR
# ============================================================

sed -i 's/127\.0\.0\.1/junction.proxy.rlwy.net/g' "$INSTALL_DIR/termchat.py"
sed -i 's/else 9999/else 35030/g' "$INSTALL_DIR/termchat.py"

# ============================================================
# VÉRIFICATION DU CLIENT PYTHON
# ============================================================

echo "🔎 Vérification du client..."

if ! python3 -m py_compile "$INSTALL_DIR/termchat.py"; then
    echo "❌ ERREUR : termchat.py contient une erreur Python."
    rm -f "$INSTALL_DIR/termchat.py"
    exit 1
fi

echo "✅ Client Python vérifié."

# ============================================================
# CRÉATION DU LANCEUR
# ============================================================

cat > "$INSTALL_DIR/termchat" <<'WRAPPER'
#!/data/data/com.termux/files/usr/bin/bash
exec python3 "$PREFIX/bin/termchat.py" "$@"
WRAPPER

chmod +x "$INSTALL_DIR/termchat"
chmod +x "$INSTALL_DIR/termchat.py"

# ============================================================
# DOSSIERS
# ============================================================

mkdir -p "$HOME/termchat_downloads"
mkdir -p "$HOME/.termchat_tls"
mkdir -p "$DOC_DIR"

# ============================================================
# DOCUMENTATION
# ============================================================

cat > "$DOC_DIR/DOCUMENTATION.md" <<'DOC'
# 💬 TermChat v6.3

**Aboudev Labs 🇨🇮**

## Installation

TermChat est installé dans Termux.

Pour lancer l'application :

    termchat

## Dossiers

Téléchargements :

    ~/termchat_downloads/

Certificats TLS :

    ~/.termchat_tls/

Documentation :

    ~/termchat_docs/

## Commandes

Les commandes disponibles dépendent de la version du client.

Commande de lancement :

    termchat

Commande de signalement :

    /signaler

La commande `/signaler` doit être utilisée à l'intérieur de TermChat,
et non directement dans le terminal Bash.

## Politique de confiance

L'installateur télécharge le client depuis le dépôt GitHub officiel
indiqué pendant l'installation.

L'installation crée :

- le client TermChat ;
- le lanceur `termchat` ;
- le dossier des téléchargements ;
- le dossier TLS ;
- cette documentation.

L'installateur ne demande pas de mot de passe personnel,
de code bancaire ou de code PIN de paiement.

## Sécurité

Vérifiez toujours la source du script avant de l'exécuter.

Ne partagez jamais vos mots de passe, codes de paiement ou clés
de sécurité avec une autre personne.

## Désinstallation

Pour supprimer le lanceur et le client installés :

    rm -f "$PREFIX/bin/termchat"
    rm -f "$PREFIX/bin/termchat.py"

Les dossiers personnels suivants peuvent être supprimés séparément
si vous n'en avez plus besoin :

    rm -rf ~/termchat_downloads
    rm -rf ~/.termchat_tls
    rm -rf ~/termchat_docs

DOC

# ============================================================
# RÉSUMÉ FINAL
# ============================================================

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║        ✅ INSTALLATION TERMINÉE             ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "💬 TermChat v$VERSION est installé avec succès !"
echo ""
echo "🚀 Pour lancer :"
echo "   termchat"
echo ""
echo "📁 Fichiers reçus :"
echo "   ~/termchat_downloads/"
echo ""
echo "🔐 Certificats TLS :"
echo "   ~/.termchat_tls/"
echo ""
echo "📚 Documentation :"
echo "   ~/termchat_docs/DOCUMENTATION.md"
echo ""
echo "🆕 Nouveautés v$VERSION :"
echo "   • Connexion directe (sans 2FA)"
echo "   • /signaler pour alerter l'administration"
echo "   • Surveillance et modération renforcées"
echo "   • Politique de confiance"
echo "   • Documentation intégrée"
echo ""
echo "🙏 Merci d'utiliser TermChat."
echo ""
