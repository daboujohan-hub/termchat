#!/bin/bash
# ══════════════════════════════════════════════════════════
#  TermChat v6.3 — Build paquet .deb pour Termux
#  by Aboudev Labs 🇨🇮
#  Usage: bash build_deb.sh
# ══════════════════════════════════════════════════════════

set -e

VERSION="6.3"
PKGNAME="termchat"
ARCH="all"
MAINTAINER="Aboudev Labs <contact@aboudev.ci>"
DESCRIPTION="Messagerie terminal chiffree pour developpeurs"

# Répertoires de build
BUILD_DIR="build_deb"
PKG_DIR="${BUILD_DIR}/data/data/com.termux/files/usr"
DEBIAN_DIR="${BUILD_DIR}/DEBIAN"

echo "🔨 Construction du paquet ${PKGNAME}_${VERSION}-1_${ARCH}.deb..."

# ── Nettoyage ──
rm -rf "$BUILD_DIR"
mkdir -p "$PKG_DIR/bin"
mkdir -p "$PKG_DIR/lib/${PKGNAME}"
mkdir -p "$PKG_DIR/share/doc/${PKGNAME}"
mkdir -p "$DEBIAN_DIR"
chmod 0755 "$DEBIAN_DIR"

# ── Fichier control ──
cat > "$DEBIAN_DIR/control" << EOF
Package: ${PKGNAME}
Version: ${VERSION}-1
Section: net
Priority: optional
Architecture: ${ARCH}
Depends: python, python-cryptography
Maintainer: ${MAINTAINER}
Description: ${DESCRIPTION}
 TermChat est une messagerie securisee fonctionnant dans le terminal.
 Elle offre le chiffrement de bout en bout, la messagerie de groupe,
 l'envoi de fichiers et une interface admin de surveillance.
EOF

# ── Le client Python ──
if [ -f "termchat.py" ]; then
    cp termchat.py "$PKG_DIR/lib/${PKGNAME}/termchat.py"
elif [ -f "termchat_final.py" ]; then
    cp termchat_final.py "$PKG_DIR/lib/${PKGNAME}/termchat.py"
else
    echo "❌ ERREUR: termchat.py ou termchat_final.py introuvable"
    exit 1
fi

# ── Wrapper exécutable ──
cat > "$PKG_DIR/bin/termchat" << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
exec python3 /data/data/com.termux/files/usr/lib/termchat/termchat.py "$@"
EOF
chmod 0755 "$PKG_DIR/bin/termchat"

# ── Post-installation : créer les dossiers utilisateur ──
cat > "$DEBIAN_DIR/postinst" << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
mkdir -p "$HOME/termchat_downloads"
mkdir -p "$HOME/.termchat_tls"
echo "✅ TermChat v6.3 installé !"
echo "👉 Lance avec: termchat"
EOF
chmod 0755 "$DEBIAN_DIR/postinst"

# ── Pré-removal : nettoyage optionnel ──
cat > "$DEBIAN_DIR/prerm" << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
echo "🗑️  Désinstallation de TermChat..."
EOF
chmod 0755 "$DEBIAN_DIR/prerm"

# ── README doc ──
cat > "$PKG_DIR/share/doc/${PKGNAME}/README" << EOF
TermChat v${VERSION}
===================

Installation:
  pkg install ./${PKGNAME}_${VERSION}-1_${ARCH}.deb

Ou:
  dpkg -i ${PKGNAME}_${VERSION}-1_${ARCH}.deb

Lancement:
  termchat

Désinstallation:
  pkg uninstall termchat
  # ou
  dpkg -r termchat

Documentation:
  https://github.com/daboujohan-hub/termchat
EOF

# ── Build du .deb ──
dpkg-deb --build "$BUILD_DIR" "${PKGNAME}_${VERSION}-1_${ARCH}.deb"

# ── Nettoyage ──
rm -rf "$BUILD_DIR"

echo ""
echo "✅ Paquet construit : ${PKGNAME}_${VERSION}-1_${ARCH}.deb"
echo ""
echo "📦 Pour l'installer sur ton téléphone (Termux):"
echo "   pkg install ./${PKGNAME}_${VERSION}-1_${ARCH}.deb"
echo ""
echo "📦 Ou avec dpkg:"
echo "   dpkg -i ${PKGNAME}_${VERSION}-1_${ARCH}.deb"
echo ""
echo "🚀 Pour l'installer sur un autre téléphone:"
echo "   1. Envoie le fichier .deb sur le téléphone"
echo "   2. Dans Termux: pkg install ./termchat_6.3-1_all.deb"
echo ""
