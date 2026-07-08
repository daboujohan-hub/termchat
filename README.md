# 💬 TermChat v6.0
**Messagerie Mondiale pour Developpeurs** — by Aboudev Labs 🇨🇮

## Nouveautés v6.0
- Base de données Firebase Firestore (données permanentes)
- Pas de système de paiement — accès libre
- Interface messages avec liste des conversations
- 5 pays : CI, SN, GN, BF, GH

## Installation
```bash
curl -s https://raw.githubusercontent.com/daboujohan-hub/termchat/main/install.sh | bash
```

## Variable d'environnement Railway
Ajouter sur Railway : FIREBASE_CREDS = (contenu du fichier JSON Firebase)

## 🤝 Contribuer

TermChat est un projet open source et toute contribution est la bienvenue !
Pas besoin d'expérience énorme — c'est un bon projet pour apprendre Node.js, Firebase et les outils CLI.

**Comment contribuer :**
1. Fork le repo
2. Crée une branche (`git checkout -b fix-mon-probleme`)
3. Fais tes modifications
4. Ouvre une Pull Request en expliquant ce que tu as changé

Tous les contributeurs seront mentionnés ci-dessous 👇

### Contributeurs
- [Diomandé Abou Johan (Aboudev)](https://github.com/daboujohan-hub) — créateur du projet

---

## 🐛 Tâches ouvertes (Good First Issues)

Voici des tâches concrètes si tu veux contribuer :

1. **Gestion des erreurs réseau dans `install.sh`**
   Le script d'installation doit afficher un message clair si la connexion échoue ou si `curl` n'est pas installé, au lieu de planter silencieusement.

2. **Validation des numéros TC-XXXXXXXXX**
   Ajouter une vérification côté serveur pour s'assurer que le format du numéro virtuel est correct avant de créer une conversation.

3. **Tests automatisés basiques**
   Écrire quelques tests simples (avec Jest ou Node `assert`) pour vérifier que l'API répond correctement aux routes principales.

4. **Documentation des routes API**
   Lister et décrire les endpoints existants (ex: `/messages`, `/register`) dans un fichier `API.md`.

5. **Support d'un 6ème pays**
   Ajouter un pays supplémentaire à la liste actuelle (CI, SN, GN, BF, GH) avec son indicatif et sa validation.

Si une de ces tâches t'intéresse, ouvre une issue GitHub en précisant laquelle tu prends, pour éviter que deux personnes travaillent dessus en même temps.
