# 💬 Guide d'utilisation — TermChat v6.0

**Messagerie terminal chiffrée pour développeurs** — by Aboudev Labs 🇨🇮

Ce guide explique comment installer TermChat, créer un compte, et utiliser
chaque fonctionnalité du menu. Il est écrit pour tout le monde, même sans
expérience technique.

---

## 📲 1. Installation (Termux / Android)

Ouvre Termux et tape :

```bash
curl -s https://raw.githubusercontent.com/daboujohan-hub/termchat/main/install.sh | bash
```

Ce script installe automatiquement tout ce dont TermChat a besoin
(y compris le chiffrement), puis place la commande `termchat` sur ton
téléphone.

**Pour lancer l'application ensuite :**
```bash
termchat
```

**Si l'installation échoue** avec une erreur liée à `cryptography` ou
`cffi`, essaie manuellement :
```bash
pkg install -y python-cryptography
pip install --break-system-packages cffi cryptography
```

---

## 🆕 2. Créer un compte

Au premier lancement, choisis **1 — Créer un compte**, puis renseigne :

| Champ | Obligatoire ? | Détails |
|---|---|---|
| Nom | Oui | 2 à 20 caractères, affiché aux autres |
| Pseudo (@handle) | Oui | 3 à 20 caractères, doit commencer par une lettre, unique |
| Email | Non | Optionnel, permet de se connecter aussi par email |
| Mot de passe | Oui | Minimum 4 caractères |
| Pays | Oui | Choisis dans la liste affichée |

À la fin, TermChat t'attribue un **numéro unique** (ton identifiant
principal, ex: `+225XXXXXXXXXX`). **Note-le précieusement** — avec ton
pseudo, c'est ce qui permet aux autres de te trouver.

---

## 🔑 3. Se connecter

Trois façons de se connecter, au choix :

- **2 — Se connecter** : avec ton nom + mot de passe
- **3 — Se connecter par numéro** : avec ton numéro + mot de passe
  (utile si plusieurs comptes partagent le même nom)
- **4 — Se connecter par email** : uniquement si tu as renseigné un
  email à l'inscription

**Astuce anciens comptes** : si tu t'es inscrit avant l'ajout du système
de pseudo, TermChat te proposera automatiquement d'en choisir un à ta
prochaine connexion.

---

## 🧭 4. Le menu principal — chaque bouton expliqué

```
  1 — 💬  Messages           → voir/écrire tes conversations
  2 — 👥  Groupes             → conversations de groupe
  3 — ⭐  Favoris              → tes contacts favoris
  4 — 📎  Envoyer un fichier   → envoyer directement un fichier/document
  6 — 🌐  En ligne             → voir qui est connecté actuellement
  7 — 👤  Mon profil           → nom, pseudo, bio, pays
  8 — 😊  Statut               → disponible / occupé / absent / ne pas déranger
  9 — 🎨  Couleur              → personnaliser la couleur de ton pseudo à l'écran
  s — 🛡️   Sécurité            → mot de passe, blocage, PIN
  q — 🚪  Déconnecter          → quitter la session
```

---

## 💬 5. Démarrer une conversation

Depuis **1 — Messages**, choisis **n — Nouvelle conversation**, puis
entre soit :
- Le **numéro** de ton contact (`+225XXXXXXXXXX`)
- Ou son **pseudo** précédé d'un `@` (`@johan`)

TermChat te propose ensuite d'**activer le chiffrement**. Si tu acceptes,
il te demande une **phrase secrète** — c'est le point le plus important
à comprendre :

> ⚠️ **La phrase secrète doit être transmise à ton contact par un autre
> moyen** (appel téléphonique, en personne, etc.) — **jamais via
> TermChat lui-même**. Les deux personnes doivent taper exactement la
> même phrase pour que les messages soient lisibles des deux côtés.
> Sans elle, personne — pas même le serveur — ne peut lire vos messages.

Dans la conversation, commandes utiles :
| Commande | Effet |
|---|---|
| `/fichier` | envoyer un fichier |
| `/vocal` | envoyer un message vocal |
| `/repondre` | répondre à un message précis |
| `/reaction` | réagir à un message |
| `/rechercher` | chercher dans l'historique |
| `/favori` | ajouter la conversation aux favoris |
| `exit` | quitter la conversation |

---

## 🔒 6. Sécurité — ce qui te protège

- **Mots de passe** chiffrés (bcrypt), jamais stockés en clair
- **Anti-bruteforce** : 5 tentatives de connexion max, puis blocage de 5 minutes
- **TLS** : le trafic tente d'être chiffré automatiquement (repli en
  clair silencieux si le réseau bloque le chiffrement — l'app continue
  de fonctionner normalement dans les deux cas)
- **Pas de recherche libre d'utilisateurs** : personne ne peut fouiller
  les profils au hasard — il faut connaître le numéro ou le pseudo exact

---

## 📂 7. Fichiers reçus

Tous les fichiers et messages vocaux que tu reçois sont automatiquement
enregistrés sur ton téléphone dans :
```
~/termchat_downloads/
```

---

## ❓ 8. Problèmes fréquents

**"TLS indisponible, connexion en clair"** → normal, pas une erreur.
L'app continue de fonctionner ; c'est juste que le chiffrement du
transport n'a pas pu s'établir cette fois. Tes messages restent protégés
si tu as activé le chiffrement par phrase secrète.

**Le fichier `install.sh` échoue sur `cryptography`** → voir la section
Installation ci-dessus, méthode manuelle.

**Un ami ne me trouve pas** → vérifie que tu lui as bien donné ton
numéro exact ou ton `@pseudo` exact (la recherche est stricte, pas de
correspondance partielle).

---

## 🤝 Contribuer au projet

TermChat est open source. Pour proposer une amélioration :
1. Fork le repo : https://github.com/daboujohan-hub/termchat
2. Crée une branche (`git checkout -b ma-fonctionnalite`)
3. Fais tes modifications
4. Ouvre une Pull Request en expliquant ce que tu as changé

**Créateur du projet** : [Diomandé Abou Johan (Aboudev)](https://github.com/daboujohan-hub) — Aboudev Labs, Côte d'Ivoire 🇨🇮
