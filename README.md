# 💬 TermChat v6.0
**Messagerie terminal chiffrée pour développeurs** — by Aboudev Labs 🇨🇮

📖 **Nouveau sur TermChat ?** Lis le [Guide d'utilisation complet](GUIDE_UTILISATEUR.md)
pour tout comprendre : installation, création de compte, chiffrement, menu.

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

### v6.0 (actuelle)
- 🔐 Mots de passe chiffrés avec **bcrypt** (migration automatique des anciens comptes)
- 🔐 Chiffrement des messages **Fernet/AES** avec phrase secrète partagée (remplace l'ancien XOR)
- 🔐 **TLS** sur la connexion (certificat auto-signé, avec repli en clair si indisponible)
- 🛡️ Protection **anti-bruteforce** (5 tentatives max, blocage 5 min) sur login/PIN/admin
- 🏷️ **Pseudo unique** (@handle) pour retrouver facilement un contact
- 📧 **Connexion par email** en plus du nom et du numéro
- 📎 Correction : les fichiers et messages vocaux apparaissent maintenant bien dans l'historique
- 🔍 Suppression de la recherche libre d'utilisateurs (protection de la vie privée) — remplacée par une recherche stricte par numéro ou pseudo exact
- ⚙️ Serveur rendu plus robuste (le handshake TLS ne bloque plus les autres connexions)

### Versions antérieures
- Base de données Firebase Firestore (données permanentes)
- Accès libre, sans système de paiement
- Interface messages avec liste des conversations
- 5 pays disponibles : CI, SN, GN, BF, GH

---

## 📲 Installation

```bash
curl -s https://raw.githubusercontent.com/daboujohan-hub/termchat/main/install.sh | bash
termchat
```

Détails complets, création de compte et utilisation : voir le
[Guide d'utilisation](GUIDE_UTILISATEUR.md).

## ⚙️ Variable d'environnement Railway (pour héberger ton propre serveur)

| Variable | Description |
|---|---|
| `FIREBASE_CREDS` | Contenu JSON complet des identifiants Firebase |
| `ADMIN_CODE` | Code d'accès admin (sinon valeur par défaut peu sûre) |
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

---

## 💌 Donner ton avis / signaler un problème

Deux façons de faire remonter une remarque, un bug ou une idée :

1. **Depuis l'app directement** : menu principal → `f — Feedback au développeur`.
   Ton message est transmis en direct, sans avoir besoin de GitHub.
2. **Via GitHub Issues** : https://github.com/daboujohan-hub/termchat/issues/new
   — utile si tu veux suivre l'avancement de ta demande publiquement.

---

## 🐛 Tâches ouvertes (Good First Issues)

1. **Diagnostiquer l'échec systématique du handshake TLS** sur le proxy
   Railway (le repli en clair fonctionne, mais le TLS échoue toujours —
   piste à creuser côté configuration proxy).
2. **Ajouter la possibilité de modifier l'email** depuis "Mon profil"
   pour les comptes existants (actuellement modifiable seulement à
   l'inscription).
3. **Tests automatisés** pour les actions serveur principales
   (inscription, connexion, envoi de message).
4. **Documentation des actions du protocole** (`inscrire`, `connecter_numero`,
   `connecter_email`, `message`, etc.) dans un fichier `PROTOCOL.md`.
5. **Support d'un 6ème pays** avec son indicatif et sa validation.

Si une tâche t'intéresse, ouvre une issue GitHub en précisant laquelle
tu prends, pour éviter que deux personnes travaillent dessus en même
temps.
