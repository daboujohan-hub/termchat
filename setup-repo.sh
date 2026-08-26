#!/bin/bash
# ══════════════════════════════════════════════════════════
#  TermChat v6.3 — Setup Repository (à lancer UNE SEULE FOIS)
#  by Aboudev Labs 🇨🇮
#  Après ça: pkg install termchat  fonctionne normalement
# ══════════════════════════════════════════════════════════

set -e

REPO_URL="https://github.com/daboujohan-hub/termchat/releases/download/v6.3"
DEB_FILE="termchat_6.3-1_all.deb"
REPO_DIR="$PREFIX/var/lib/termchat-repo"
LIST_FILE="$PREFIX/etc/apt/sources.list.d/termchat.list"

echo "🔧 Configuration du dépôt TermChat..."

# ── Créer le dossier repo ──
mkdir -p "$REPO_DIR"
cd "$REPO_DIR"

# ── Télécharger le .deb ──
echo "⬇️  Téléchargement de ${DEB_FILE}..."
curl -sL "${REPO_URL}/${DEB_FILE}" -o "${DEB_FILE}"

if [ ! -s "${DEB_FILE}" ]; then
    echo "❌ ERREUR: téléchargement échoué."
    echo "   Vérifie ta connexion et que la release v6.3 existe sur GitHub."
    exit 1
fi

# ── Générer le fichier Packages (index apt) ──
echo "📦 Génération de l'index..."

SIZE=$(stat -c%s "${DEB_FILE}" 2>/dev/null || stat -f%z "${DEB_FILE}")
MD5=$(md5sum "${DEB_FILE}" | cut -d' ' -f1)
SHA1=$(sha1sum "${DEB_FILE}" | cut -d' ' -f1)
SHA256=$(sha256sum "${DEB_FILE}" | cut -d' ' -f1)

cat > Packages << EOF
Package: termchat
Version: 6.3-1
Architecture: all
Maintainer: Aboudev Labs <contact@aboudev.ci>
Depends: python, python-cryptography
Filename: ./${DEB_FILE}
Size: ${SIZE}
MD5sum: ${MD5}
SHA1: ${SHA1}
SHA256: ${SHA256}
Description: Messagerie terminal chiffree pour developpeurs
 TermChat offre le chiffrement de bout en bout, messagerie de groupe,
 envoi de fichiers et surveillance admin.
EOF

gzip -c Packages > Packages.gz

# ── Ajouter la source à apt ──
echo "deb [trusted=yes] file://${REPO_DIR} ./" > "$LIST_FILE"

# ── Mettre à jour apt ──
echo "🔄 Mise à jour des sources..."
pkg update

echo ""
echo "✅ Dépôt TermChat configuré !"
echo ""
echo "🚀 Tu peux maintenant installer avec :"
echo "   pkg install termchat"
echo ""
echo "🗑️  Pour désinstaller :"
echo "   pkg uninstall termchat"
echo ""
