#!/bin/sh
# ══════════════════════════════════════════════════════════
# Génération du keystore de signature — LABO IA Academy
# À exécuter UNE SEULE FOIS avant la première compilation release
# ══════════════════════════════════════════════════════════

KEYSTORE_FILE="laboia-release.keystore"
ALIAS="laboia"
PASSWORD="${KEYSTORE_PASS:-LaboIA2026!}"
VALIDITY=10950   # 30 ans

echo "🔐 Génération du keystore de signature LABO IA..."
echo ""

if [ -f "$KEYSTORE_FILE" ]; then
    echo "⚠️  Le fichier $KEYSTORE_FILE existe déjà."
    printf "Voulez-vous le remplacer ? (o/N) : "
    read -r reponse
    if [ "$reponse" != "o" ] && [ "$reponse" != "O" ]; then
        echo "❌ Annulé. Le keystore existant est conservé."
        exit 0
    fi
    rm -f "$KEYSTORE_FILE"
fi

keytool -genkeypair \
    -v \
    -keystore "$KEYSTORE_FILE" \
    -alias "$ALIAS" \
    -keyalg RSA \
    -keysize 2048 \
    -validity $VALIDITY \
    -storepass "$PASSWORD" \
    -keypass "$PASSWORD" \
    -dname "CN=AbouDev Labs, OU=LABO IA Academy, O=Dev Community Africa, L=Abidjan, ST=Abidjan, C=CI"

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Keystore créé avec succès : $KEYSTORE_FILE"
    echo "🔑 Alias       : $ALIAS"
    echo "🔑 Mot de passe : $PASSWORD"
    echo ""
    echo "⚠️  IMPORTANT : Conservez ce fichier et ce mot de passe en lieu sûr !"
    echo "   Sans eux, vous ne pourrez plus publier de mises à jour de l'app."
    echo ""
    echo "💡 Pour changer le mot de passe, définissez la variable :"
    echo "   export KEYSTORE_PASS=\"VotreMotDePasse\""
    echo "   puis relancez ce script."
else
    echo "❌ Erreur lors de la génération du keystore."
    exit 1
fi
