# 💬 TermChat v6.3
**Messagerie terminal chiffrée pour développeurs** — by Aboudev Labs 🇨🇮

📖 **Nouveau sur TermChat ?** Lis le [Guide d'utilisation complet](GUIDE_UTILISATEUR.md)
pour tout comprendre : installation, création de compte, chiffrement, menu, premium.

---

## 📝 Mot du développeur

TermChat est un projet solo, développé et maintenu entièrement depuis
Termux sur Android par Aboudev Labs, Côte d'Ivoire 🇨🇮. C'est un
laboratoire d'apprentissage autant qu'une vraie messagerie : chaque
mise à jour vise à rapprocher le projet des standards de sécurité d'une
vraie application de messagerie, tout en gardant l'esprit terminal qui
fait son originalité.

Le projet évolue par itérations rapides — si tu trouves un bug ou une
faille, ouvre une issue sur GitHub, ou contribue directement (voir plus
bas).

---

## 🆕 Journal des mises à jour

### v6.3 (actuelle)
- 🛡️ **Surveillance admin complète** : connexions actives (IP, pays, heure),
  alertes sécurité auto-détectées (bruteforce, anomalies), lecture
  conversations pour modération, fichiers uploadés, traitement des
  signalements utilisateurs
- 🚩 **Signalement utilisateur** : commande `/signaler` dans le chat
  pour alerter l'administration (harcelement, fraude, menace)
- 🔒 **Limite de sessions** : 3 connexions simultanées max par compte,
  kick auto de l'ancienne session
- 📜 **Audit log étendu** : 14 points de log (connexions, échecs login,
  changement mdp, blocage, suppression, signalements, session kick)
- 📢 **Rate limit admin broadcast** : 5 broadcasts max / 5 minutes
- ❌ **2FA retiré** : connexion directe numéro/mdp ou email/mdp
  (Resend/Gmail non fiable en production locale)
- 🌍 **11 pays supportés** : Côte d'Ivoire, Sénégal, Guinée, Burkina Faso,
  Ghana, Mali, Togo, Bénin, Niger, Nigeria, Cameroun
- ⭐ **Système premium à 4 niveaux** : Gratuit, Mensuel (500 FCFA),
  Annuel (8000 FCFA), Fondateur (accès à vie pour les bêta-testeurs)
- 🏷️ **Badges visuels** selon le niveau : ✨ Mensuel, 💎 Annuel, 🏆 Fondateur
- 💰 **Paiement intégré** : commande `/payer <code_transaction> <montant>`
  directement dans l'app
- 📎 **Fichiers réservés au premium** (gratuit : messagerie texte uniquement,
  150 caractères max par message)
- 🎨 **Interface adaptée au profil**
- ✅ **Bug TLS en production résolu**

### v6.1
- 🔒 Vérification du pays par géolocalisation IP à l'inscription
- 🛡️ Durcissement sécurité : comparaison temps-constant admin,
  limite de tentatives, protection anti-DoS
- 🐛 Corrections groupes, statut, favoris, blocage, couleur, bio

### v6.0
- 🔐 Mots de passe chiffrés avec **bcrypt** (migration automatique des anciens comptes)
- 🔐 Chiffrement des messages de bout en bout (**ECDH X25519 + AES**),
  activé automatiquement — repli par phrase secrète partagée si besoin
- 🔐 **TLS** sur la connexion
- 🛡️ Protection **anti-bruteforce** (5 tentatives max, blocage 5 min) sur login/PIN/admin
- 🏷️ **Pseudo unique** (@handle) pour retrouver facilement un contact
- 📧 **Connexion par email** en plus du numéro
- 🔍 Recherche stricte par numéro ou pseudo exact (protection de la vie privée)

### Versions antérieures
- Base de données Firebase Firestore (données permanentes)
- Accès libre, sans système de paiement
- Interface messages avec liste des conversations
- 5 pays disponibles initialement (CI, SN, GN, BF, GH)

---

## 📲 Installation

```bash
curl -s https://raw.githubusercontent.com/daboujohan-hub/termchat/main/install.sh | bash
termchat
```

Détails complets, création de compte et utilisation : voir le
[Guide d'utilisation](GUIDE_UTILISATEUR.md).

## ⚙️ Variables d'environnement Railway (pour héberger ton propre serveur)

| Variable | Description |
|---|---|
| `FIREBASE_CREDS` | Contenu JSON complet des identifiants Firebase |
| `ADMIN_CODE` | Code d'accès admin (minimum 12 caractères, aléatoire) |
| `PRODUCTION_MODE` | `0` ou `1` — active les vérifications strictes de production |
| `REQUIRE_EXISTING_TLS_CERT` | `0` ou `1` — `0` recommandé pour laisser le serveur générer son certificat automatiquement |
| `FILE_ENCRYPTION_KEY` | Clé Fernet (optionnel) pour chiffrer les fichiers au repos |
| `ADMIN_ALLOWED_IPS` | Liste d'IP autorisées pour l'admin (ex: `192.168.1.0/24,10.0.0.1`) |
| `PORT` | Port d'écoute (fourni automatiquement par Railway) |

---

## 🤝 Contribuer

TermChat est un projet open source et toute contribution est la
bienvenue ! Pas besoin d'expérience énorme — c'est un bon projet pour
apprendre Python, Firebase, la cryptographie appliquée et les outils CLI.

**Comment contribuer :**
1. Fork le repo
2. Crée une branche (`git checkout -b fix-mon-probleme`)
3. Fais tes modifications
4. Ouvre une Pull Request en expliquant ce que tu as changé

### Contributeurs
- [Diomandé Abou Johan (Aboudev)](https://github.com/daboujohan-hub) — créateur du projet

---

## 💌 Donner ton avis / signaler un problème

Deux façons de faire remonter une remarque, un bug ou une idée :

1. **Depuis l'app directement** : menu principal → `f — Feedback au développeur`.
   Ton message est transmis en direct, sans avoir besoin de GitHub.
2. **Via GitHub Issues** : https://github.com/daboujohan-hub/termchat/issues/new
   — utile si tu veux suivre l'avancement de ta demande publiquement.

---

## 🐛 Tâches ouvertes (Good First Issues)

1. **Ajouter la possibilité de modifier l'email** depuis "Mon profil"
   pour les comptes existants.
2. **Tests automatisés** pour les actions serveur principales
   (inscription, connexion, envoi de message).
3. **Documentation des actions du protocole** (`inscrire`, `connecter_numero`,
   `connecter_email`, `message`, etc.) dans un fichier `PROTOCOL.md`.
4. **Vérification d'empreinte de clé publique** entre contacts (comme les
   "numéros de sécurité" de Signal).
5. **Suppression d'un message précis** (aujourd'hui, seule la suppression
   de tout un historique existe).
6. **Export PDF des signalements** pour transmission à la police.

Si une tâche t'intéresse, ouvre une issue GitHub en précisant laquelle
tu prends, pour éviter que deux personnes travaillent dessus en même
temps.
