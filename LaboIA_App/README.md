# 📱 LABO IA & TERMUX ACADEMY — App Android v7.0

Application Android native (WebView) qui embarque le site **LABO IA & TERMUX ACADEMY** complet, 100% hors-ligne, avec carte développeur, classes CP1→CM3, exercices, Prof IA, Snake, Termux et le langage INFINI.

---

## 📦 Contenu du projet

```
LaboIA_App/
├── app/
│   ├── build.gradle                  ← config de build de l'app
│   ├── proguard-rules.pro            ← règles de minification
│   └── src/main/
│       ├── AndroidManifest.xml       ← permissions + activités
│       ├── assets/
│       │   └── index.html            ← TOUT le site web (autonome)
│       ├── java/ci/laboia/academy/
│       │   ├── MainActivity.java     ← WebView + Bridge JS↔Android
│       │   └── SplashActivity.java   ← écran de démarrage
│       └── res/
│           ├── layout/                (écrans)
│           ├── values/                (couleurs, styles, textes)
│           ├── xml/                   (config réseau)
│           └── mipmap-*/              (icônes de l'app, déjà générées)
├── build.gradle                       ← config racine
├── settings.gradle
├── gradle.properties
├── gradlew                            ← script de build (Linux/Termux)
├── gradle/wrapper/gradle-wrapper.properties
├── generate-keystore.sh               ← génère la clé de signature
├── build-apk.sh                       ← script tout-en-un (build automatique)
└── README.md                          ← ce fichier
```

---

## ✅ Permissions intégrées

| Permission | Usage |
|---|---|
| `INTERNET` | Liens externes (Web, partage) |
| `RECORD_AUDIO` | Micro pour le Prof IA (reconnaissance vocale) |
| `CAMERA` | Photo de profil sur la carte développeur |
| `READ/WRITE_EXTERNAL_STORAGE` | Photos, fichiers |
| `VIBRATE` | Retour tactile (toasts, badges) |
| `WAKE_LOCK` | Anti-veille pendant les sessions |

---

## 🚀 Compiler l'APK — 3 méthodes

### Méthode 1 — Sur votre téléphone avec Termux (recommandé, vous travaillez déjà ainsi)

```bash
# 1. Décompressez le ZIP dans Termux
unzip LaboIA_App.zip
cd LaboIA_App

# 2. Installez les paquets nécessaires (une seule fois)
pkg update && pkg upgrade -y
pkg install -y openjdk-21 gradle unzip

# 3. Rendez les scripts exécutables (déjà fait, mais au cas où)
chmod +x gradlew build-apk.sh generate-keystore.sh

# 4. Lancez le build automatique (debug, rapide pour tester)
sh build-apk.sh debug

# OU pour une version signée prête à publier :
sh build-apk.sh release
```

⚠️ **Important sur Termux** : compiler un projet Android complet nécessite le **SDK Android** (aapt2, d8, etc.), que Gradle télécharge normalement automatiquement — **mais cela nécessite une connexion Internet** lors du premier build (téléchargement de ~150-300 Mo d'outils). Si vous n'avez pas de connexion stable, utilisez la Méthode 2.

### Méthode 2 — Sur un PC avec Android Studio (la plus fiable, zéro configuration)

1. Téléchargez et installez **Android Studio** : https://developer.android.com/studio
2. Décompressez `LaboIA_App.zip`
3. Ouvrez Android Studio → **Open** → sélectionnez le dossier `LaboIA_App`
4. Attendez la synchronisation Gradle (automatique, télécharge le SDK)
5. Menu **Build → Build Bundle(s)/APK(s) → Build APK(s)**
6. L'APK signé apparaît dans `app/build/outputs/apk/debug/` ou `/release/`

### Méthode 3 — Build manuel avec Gradle CLI (PC Linux/Mac/Windows)

```bash
cd LaboIA_App
./gradlew assembleDebug      # version test
./gradlew assembleRelease    # version signée finale
```

---

## 🔐 Signature de l'application

Avant de générer une version **release** (celle que vous distribuez), une clé de signature est nécessaire.

```bash
sh generate-keystore.sh
```

Cela crée `laboia-release.keystore` avec :
- **Alias** : `laboia`
- **Mot de passe par défaut** : `LaboIA2026!`

⚠️ **Conservez ce fichier et ce mot de passe précieusement.** Sans eux, impossible de publier une mise à jour de la même application — vous devriez forcer une désinstallation/réinstallation chez tous vos utilisateurs.

Pour changer le mot de passe :
```bash
export KEYSTORE_PASS="VotreMotDePasseSecurise"
export KEY_PASS="VotreMotDePasseSecurise"
sh generate-keystore.sh
```

---

## 📤 Installer l'APK sur un téléphone Android

1. Copiez le fichier `.apk` généré (`app-debug.apk` ou `app-release.apk`) sur le téléphone
   - Via câble USB, Bluetooth, ou un lien de partage (Google Drive, WhatsApp...)
2. Sur le téléphone : **Paramètres → Sécurité → Autoriser les sources inconnues** (ou cela sera demandé automatiquement à l'installation)
3. Appuyez sur le fichier `.apk` → **Installer**
4. L'application **LABO IA Academy** apparaît dans le launcher avec son icône

---

## 🔄 Synchronisation App ↔ Site Web

L'application charge `index.html` directement depuis ses assets internes — **c'est exactement le même fichier que le site web**. Toute donnée (XP, classes complétées, cartes créées, notes) est sauvegardée en **`localStorage`**, donc **locale à chaque appareil/navigateur**.

### Pour garder le site web et l'app synchronisés à l'avenir :
- Modifiez **uniquement** `app/src/main/assets/index.html`
- Copiez ce même fichier vers votre hébergement web (Render/Railway)
- Recompilez l'APK avec `sh build-apk.sh release`

> 💡 Le pont `AndroidBridge` (dans `MainActivity.java`) expose des fonctions natives au JavaScript (`vibrate()`, `shareText()`, `showToast()`) que le site web utilise automatiquement **uniquement quand il tourne dans l'app** — sur navigateur web classique, ces fonctions sont ignorées sans erreur.

---

## 🛠️ Dépannage

| Problème | Solution |
|---|---|
| `gradlew: Permission denied` | `chmod +x gradlew` |
| `SDK location not found` | Définissez `ANDROID_HOME` ou créez `local.properties` avec `sdk.dir=/chemin/vers/sdk` |
| Build très lent dans Termux | Normal au premier build (téléchargement SDK). Patientez avec une bonne connexion Wi-Fi |
| L'app crash au démarrage | Vérifiez `app/src/main/assets/index.html` n'est pas corrompu (doit être un seul fichier HTML valide) |
| Micro/Caméra ne fonctionnent pas | Vérifiez que les permissions sont acceptées dans **Paramètres → Apps → LABO IA Academy → Permissions** |

---

## 📋 Prochaines étapes suggérées

- [ ] Personnaliser l'icône (remplacer les PNG dans `mipmap-*/` par votre propre design)
- [ ] Ajouter un vrai système de compte (actuellement les données sont locales par appareil)
- [ ] Publier sur un store alternatif (APKPure, F-Droid via un dépôt personnalisé) ou Google Play
- [ ] Configurer une mise à jour automatique de contenu (vérification de version au démarrage)

---

**LABO IA & TERMUX ACADEMY** · v7.0 · AbouDev Labs · Côte d'Ivoire 🇨🇮
