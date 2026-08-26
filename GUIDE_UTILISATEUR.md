# 💬 Guide d'utilisation — TermChat v6.3
# by Aboudev Labs 🇨🇮 @github.dev.d.a.j
#💬 TERMCHAT v6.1 Installation DEV.D.A.J

___                                               ___
                  TERMCHAT° 26/08/2026
___                      00H00                    ___

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
| Pays | Oui | Choisis dans la liste affichée (11 pays disponibles) |

**Pays disponibles :** Côte d'Ivoire 🇨🇮, Sénégal 🇸🇳, Guinée 🇬🇳, Burkina
Faso 🇧🇫, Ghana 🇬🇭, Mali 🇲🇱, Togo 🇹🇬, Bénin 🇧🇯, Niger 🇳🇪, Nigeria 🇳🇬,
Cameroun 🇨🇲.

> ℹ️ TermChat vérifie automatiquement que le pays choisi correspond
> raisonnablement à ta localisation réseau. Cette vérification est
> tolérante : en cas de doute (VPN, réseau mobile particulier), elle
> ne bloque jamais un compte légitime par erreur.

À la fin, TermChat t'attribue un **numéro unique** (ton identifiant
principal, ex: `+225XXXXXXXXXX`). **Note-le précieusement** — avec ton
pseudo, c'est ce qui permet aux autres de te trouver.

---

## 🔑 3. Se connecter

Deux façons de se connecter, au choix :

- **2 — Se connecter (numéro + mot de passe)** : ta méthode principale,
  avec le numéro unique attribué à la création du compte
- **3 — Se connecter par email** : uniquement si tu as renseigné un
  email à l'inscription

> La connexion par nom a été retirée : plusieurs personnes peuvent
> avoir le même nom affiché, ce qui la rendait ambiguë et peu sûre.
> Le numéro (ou l'email) reste toujours unique.

**Astuce anciens comptes** : si tu t'es inscrit avant l'ajout du système
de pseudo, TermChat te proposera automatiquement d'en choisir un à ta
prochaine connexion.

---

## 🧭 4. Le menu principal — chaque bouton expliqué

Le menu s'adapte à ton niveau de compte (voir section 7). Voici le menu
complet, tel qu'il apparaît pour un compte premium :

```
  1 — 💬  Messages           → voir/écrire tes conversations
  2 — 👥  Groupes             → conversations de groupe
  3 — ⭐  Favoris              → tes contacts favoris
  4 — 📎  Envoyer un fichier   → envoyer directement un fichier/document (premium)
  6 — 🌐  En ligne             → voir qui est connecté actuellement
  7 — 👤  Mon profil           → nom, pseudo, bio, pays
  8 — 😊  Statut               → disponible / occupé / absent / ne pas déranger
  9 — 🎨  Couleur              → personnaliser la couleur de ton pseudo à l'écran
  s — 🛡️   Sécurité            → mot de passe, blocage, PIN, abonnement
  q — 🚪  Déconnecter          → quitter la session
```

> En compte **gratuit**, l'option `4 — Envoyer un fichier` n'apparaît
> pas dans le menu (fonctionnalité réservée au premium).

---

## 💬 5. Démarrer une conversation

Depuis **1 — Messages**, choisis **n — Nouvelle conversation**, puis
entre soit :
- Le **numéro** de ton contact (`+225XXXXXXXXXX`)
- Ou son **pseudo** précédé d'un `@` (`@johan`)

Le **chiffrement de bout en bout s'active automatiquement** dès que la
conversation s'ouvre — TermChat calcule une clé secrète partagée avec
ton contact (via ECDH X25519), sans que tu aies rien à faire. Le serveur
ne voit jamais le contenu de tes messages.

Dans la conversation, commandes utiles :
| Commande | Effet |
|---|---|
| `/fichier` | envoyer un fichier (premium uniquement) |
| `/vocal` | envoyer un message vocal |
| `/payer <code> <montant>` | soumettre un paiement pour activer le premium |
| `/repondre` | répondre à un message précis |
| `/reaction` | réagir à un message |
| `/rechercher` | chercher dans l'historique |
| `/favori` | ajouter la conversation aux favoris |
| `/signaler` | signaler un utilisateur abusif à l'administration |
| `exit` | quitter la conversation |

> ⚠️ **Compte gratuit** : les messages sont limités à **150 caractères**.
> Au-delà, TermChat te propose de passer premium.

---

## 🔒 6. Sécurité — ce qui te protège

- **Chiffrement de bout en bout réel** (ECDH X25519 + AES) : même en cas
  d'accès à la base de données du serveur, le contenu de tes messages
  reste illisible
- **Mots de passe** chiffrés (bcrypt), jamais stockés en clair
- **Anti-bruteforce** : 5 tentatives de connexion max, puis blocage de 5 minutes
- **TLS** sur toute la connexion réseau
- **Limite de sessions** : 3 connexions simultanées max par compte
- **Audit log** : toutes les actions sensibles sont enregistrées
  (connexions, échecs, modifications, signalements)
- **Pas de recherche libre d'utilisateurs** : personne ne peut fouiller
  les profils au hasard — il faut connaître le numéro ou le pseudo exact,
  et cette recherche est elle-même limitée en fréquence
- **Protection anti-abus** sur les connexions simultanées et la taille
  des messages, pour la stabilité du serveur
- **Signalement** : tu peux signaler un utilisateur abusif avec `/signaler`
  dans une conversation — l'administration reçoit l'alerte et peut agir

---

## ⭐ 7. Abonnement Premium

TermChat propose **4 niveaux de compte** :

| | 🔘 Gratuit | ✨ Mensuel | 💎 Annuel | 🏆 Fondateur |
|---|---|---|---|---|
| Prix | 0 FCFA | 500 FCFA / mois | 8000 FCFA / an | Offert aux bêta-testeurs |
| Contacts | 5 max | Illimité | Illimité | Illimité |
| Membres par groupe | 5 max | Illimité | Illimité | Illimité |
| Longueur de message | 150 caractères | Illimité | Illimité | Illimité |
| Fichiers | ❌ | ✅ (50 Mo max) | ✅ (50 Mo max) | ✅ (50 Mo max) |
| Support prioritaire | ❌ | ❌ | ✅ | ✅ |
| Durée | — | 30 jours | 365 jours | À vie |

**Comment passer premium :**
1. Envoie ton paiement via **Wave** ou **Moov** au numéro **+2250170404109**
2. Note le code de transaction fourni par ton opérateur
3. Dans TermChat, tape dans une conversation :
   ```
   /payer <code_transaction> <montant>
   ```
4. Le développeur vérifie manuellement le paiement et active ton compte
   — tu reçois une notification automatique dès que c'est fait, avec
   ton nouveau badge (✨, 💎 ou 🏆)

**Vérifier ton statut :** menu **Sécurité → 6 — Mon abonnement**

---

## 🎨 8. Interface selon ton profil

L'apparence de TermChat s'adapte à ton niveau de compte : couleur de la
bannière, badge affiché à côté de ton pseudo dans les messages, et
options visibles dans le menu. Un compte Fondateur, par exemple, a
également accès à des outils réservés (voir rapports de bugs, logs,
gestion des utilisateurs).

---

## 📂 9. Fichiers reçus

Tous les fichiers et messages vocaux que tu reçois sont automatiquement
enregistrés sur ton téléphone dans :
```
~/termchat_downloads/
```

---

## ❓ 10. Problèmes fréquents

**Le fichier `install.sh` échoue sur `cryptography`** → voir la section
Installation ci-dessus, méthode manuelle.

**Un ami ne me trouve pas** → vérifie que tu lui as bien donné ton
numéro exact ou ton `@pseudo` exact (la recherche est stricte, pas de
correspondance partielle).

**"Message trop long" en gratuit** → la limite de 150 caractères est
volontaire pour les comptes gratuits ; passe premium pour l'illimité
(voir section 7).

**Je ne peux pas envoyer de fichier** → l'envoi de fichiers est réservé
aux comptes premium (voir section 7).

**Mon paiement n'est pas encore activé** → l'activation est manuelle,
laisse un peu de temps au développeur pour vérifier la transaction.

---

## 🛡️ 11. Panel Admin (réservé)

Si ton compte a le flag administrateur, le menu affiche **0 — Panel Admin**.

Fonctionnalités de surveillance disponibles :

| Option | Description |
|---|---|
| `1` | Statistiques globales |
| `2` | Liste de tous les utilisateurs (en ligne/hors ligne) |
| `3` | Broadcast message à tous |
| `4` | Kick (déconnecter) un utilisateur |
| `5` | Feedback reçus |
| `6` | Activer/désactiver le premium |
| `7` | Envoyer un message à un utilisateur |
| `8` | Paiements en attente |
| `9` | Journal d'audit (logs immuables) |
| `s` | **Surveillance connexions** : IP, pays, heure de chaque connecté |
| `a` | **Alertes sécurité** : bruteforce, pays incohérent, sessions multiples |
| `c` | **Voir conversation** : modération légale entre 2 numéros |
| `f` | **Fichiers uploadés** : liste complète avec taille et date |
| `g` | **Signalements** : traiter les alertes utilisateurs |

> ⚠️ **Accès réservé** : la lecture des conversations et fichiers est
> strictement réservée à la modération et aux signalements légaux.
> Toute consultation est loguée dans l'audit.

## 🤝 Contribuer au projet

TermChat est open source. Pour proposer une amélioration :
1. Fork le repo : https://github.com/daboujohan-hub/termchat
2. Crée une branche (`git checkout -b ma-fonctionnalite`)
3. Fais tes modifications
4. Ouvre une Pull Request en expliquant ce que tu as changé

**Créateur du projet** : [Diomandé Abou Johan (Aboudev)](https://github.com/daboujohan-hub) — Aboudev Labs, Côte d'Ivoire 🇨🇮

**Transparence sur l'IA** : une partie du code de TermChat a été écrite
avec l'aide d'assistants IA. La conception, les décisions de sécurité,
et les tests restent de mon ressort — l'IA m'aide à écrire et sécuriser
le code plus vite.
