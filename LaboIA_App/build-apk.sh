#!/data/data/com.termux/files/usr/bin/sh
# ══════════════════════════════════════════════════════════
# BUILD AUTOMATIQUE — LABO IA & TERMUX ACADEMY
# Génère l'APK directement dans Termux sur Android
# ══════════════════════════════════════════════════════════

set -e

GREEN='\033[0;32m'
ORANGE='\033[0;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

echo "${ORANGE}╔═══════════════════════════════════════════╗${NC}"
echo "${ORANGE}║   LABO IA & TERMUX ACADEMY — BUILD APK    ║${NC}"
echo "${ORANGE}╚═══════════════════════════════════════════╝${NC}"
echo ""

# ── 1. Vérifier les outils requis ──
echo "${CYAN}[1/6]${NC} Vérification de l'environnement..."

if ! command -v java >/dev/null 2>&1; then
    echo "${RED}❌ Java non trouvé.${NC} Installation..."
    pkg install -y openjdk-21
fi
JAVA_VER=$(java -version 2>&1 | head -1)
echo "   ✅ $JAVA_VER"

# Définit JAVA_HOME explicitement si absent, pour que Gradle (sous-processus)
# le voie de façon fiable, même sur les installations Termux où 'which' est cassé.
if [ -z "$JAVA_HOME" ]; then
    for candidate in \
        "${PREFIX:-/data/data/com.termux/files/usr}/lib/jvm/java-21-openjdk" \
        "${PREFIX:-/data/data/com.termux/files/usr}/lib/jvm/java-17-openjdk" \
        "/usr/lib/jvm/java-21-openjdk-amd64" \
        "/usr/lib/jvm/default-java"
    do
        if [ -x "$candidate/bin/java" ]; then
            export JAVA_HOME="$candidate"
            echo "   ✅ JAVA_HOME défini automatiquement : $JAVA_HOME"
            break
        fi
    done
fi

if ! command -v unzip >/dev/null 2>&1; then
    pkg install -y unzip
fi

# Android SDK / aapt requis pour compiler — via le paquet 'aapt' de Termux,
# ou en utilisant Gradle qui télécharge ses propres outils si une connexion existe.
if ! command -v sdkmanager >/dev/null 2>&1 && [ -z "$ANDROID_HOME" ]; then
    echo "${ORANGE}⚠️  ANDROID_HOME non configuré.${NC}"
    echo "   Installez le SDK Android minimal avec :"
    echo "   pkg install -y android-tools"
    echo "   Ou utilisez Android Studio sur un PC pour cette étape."
fi

# ── 2. Copier le site web dans les assets ──
echo ""
echo "${CYAN}[2/6]${NC} Copie du site web (index.html) dans les assets Android..."
mkdir -p app/src/main/assets
if [ -f "../index.html" ]; then
    cp ../index.html app/src/main/assets/index.html
    echo "   ✅ index.html copié depuis le dossier parent"
elif [ -f "index.html" ]; then
    cp index.html app/src/main/assets/index.html
    echo "   ✅ index.html copié depuis le dossier courant"
elif [ -f "app/src/main/assets/index.html" ]; then
    echo "   ✅ index.html déjà présent dans assets/"
else
    echo "${RED}   ❌ index.html introuvable !${NC}"
    echo "   Placez votre fichier index.html à la racine du projet et relancez."
    exit 1
fi

# ── 3. Vérifier/générer le keystore ──
echo ""
echo "${CYAN}[3/6]${NC} Vérification du keystore de signature..."
if [ ! -f "laboia-release.keystore" ]; then
    echo "   ⚠️  Aucun keystore trouvé. Génération automatique..."
    sh generate-keystore.sh
else
    echo "   ✅ Keystore existant trouvé."
fi

# ── 4. Rendre gradlew exécutable ──
echo ""
echo "${CYAN}[4/6]${NC} Préparation de Gradle..."
chmod +x gradlew
echo "   ✅ gradlew prêt"

# ── 5. Build de l'APK ──
echo ""
echo "${CYAN}[5/6]${NC} Compilation de l'APK (cela peut prendre plusieurs minutes)..."
echo ""

MODE="${1:-debug}"

if [ "$MODE" = "release" ]; then
    echo "   🔨 Mode RELEASE (signé, optimisé)"
    ./gradlew assembleRelease --no-daemon
    APK_PATH="app/build/outputs/apk/release/app-release.apk"
else
    echo "   🔨 Mode DEBUG (rapide, pour tests)"
    ./gradlew assembleDebug --no-daemon
    APK_PATH="app/build/outputs/apk/debug/app-debug.apk"
fi

# ── 6. Résultat ──
echo ""
echo "${CYAN}[6/6]${NC} Vérification du résultat..."

if [ -f "$APK_PATH" ]; then
    SIZE=$(du -h "$APK_PATH" | cut -f1)
    echo ""
    echo "${GREEN}╔═══════════════════════════════════════════╗${NC}"
    echo "${GREEN}║          ✅ APK GÉNÉRÉ AVEC SUCCÈS !       ║${NC}"
    echo "${GREEN}╚═══════════════════════════════════════════╝${NC}"
    echo ""
    echo "   📦 Fichier  : $APK_PATH"
    echo "   📏 Taille   : $SIZE"
    echo "   📱 Pour installer : transférez-le et appuyez dessus sur Android"
    echo ""
    echo "   💡 Copier vers le stockage partagé :"
    echo "      cp $APK_PATH /sdcard/Download/LaboIA-Academy.apk"
else
    echo "${RED}❌ La compilation a échoué — l'APK n'a pas été généré.${NC}"
    echo "   Consultez les messages d'erreur ci-dessus."
    exit 1
fi
