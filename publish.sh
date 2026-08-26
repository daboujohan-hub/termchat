#!/bin/bash
# ══════════════════════════════════════════════════════════
#  TermChat v6.3 — Script de publication (pour le développeur)
#  by Aboudev Labs 🇨🇮
#  Usage: bash publish.sh
# ══════════════════════════════════════════════════════════

set -e

VERSION="6.3"
PKGNAME="termchat"
ARCH="all"
DEB_FILE="${PKGNAME}_${VERSION}-1_${ARCH}.deb"

echo "🚀 Publication TermChat v${VERSION}..."

# ── 1. Build le .deb ──
if [ -f "build_deb.sh" ]; then
    echo "🔨 Build du paquet..."
    bash build_deb.sh
else
    echo "❌ build_deb.sh introuvable. Place-le dans ce dossier."
    exit 1
fi

# ── 2. Vérifier que le .deb existe ──
if [ ! -f "$DEB_FILE" ]; then
    echo "❌ ${DEB_FILE} introuvable. Le build a échoué ?"
    exit 1
fi

# ── 3. Générer le fichier Packages pour le repo ──
echo "📦 Génération de l'index Packages..."

SIZE=$(stat -c%s "${DEB_FILE}" 2>/dev/null || stat -f%z "${DEB_FILE}")
MD5=$(md5sum "${DEB_FILE}" | cut -d' ' -f1)
SHA1=$(sha1sum "${DEB_FILE}" | cut -d' ' -f1)
SHA256=$(sha256sum "${DEB_FILE}" | cut -d' ' -f1)

cat > Packages << EOF
Package: ${PKGNAME}
Version: ${VERSION}-1
Architecture: ${ARCH}
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

echo ""
echo "✅ Build terminé !"
echo ""
echo "📁 Fichiers générés :"
echo "   ${DEB_FILE}"
echo "   Packages"
echo "   Packages.gz"
echo ""
echo "📤 Prochaines étapes :"
echo "   1. Crée une release v${VERSION} sur GitHub"
echo "   2. Upload ${DEB_FILE} dans la release"
echo "   3. Upload aussi Packages et Packages.gz (optionnel)"
echo ""
echo "🔗 URL de la release (à créer) :"
echo "   https://github.com/daboujohan-hub/termchat/releases/new?tag=v${VERSION}"
echo ""
echo "📱 Commande pour tes utilisateurs :"
echo "   curl -sL https://raw.githubusercontent.com/daboujohan-hub/termchat/main/setup-repo.sh | bash"
echo "   pkg install termchat"
echo ""
