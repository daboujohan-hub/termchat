# 🛡️ TermChat Server — Notes de patch (audit sécurité)

Corrections appliquées suite à un audit manuel complet de `server.py`
(1990 lignes) et vérification croisée avec `termchat.py` (client).

## 🔴 Critique

### Comptes désactivés reconnectables
**Problème :** `supprimer_compte` enregistrait `desactive: True`, mais ce
flag n'était jamais vérifié à la connexion. Un compte "supprimé" pouvait
se reconnecter et utiliser l'app normalement.
**Fix :** vérification `user.get("desactive")` dans `connecter_numero` et
`connecter_email`, avec refus de connexion + entrée dans le journal d'audit.

## 🟠 Moyen — failles d'autorisation

### Réaction sans vérification du destinataire/message
**Problème :** l'action `reaction` acceptait n'importe quel `dest`/`msg_id`
sans vérifier que le destinataire existe ni que le message appartient
réellement à la conversation.
**Fix :** ajout de `fs_message_existe()`, vérification de l'existence du
destinataire, et limitation du champ `emoji` à 8 caractères.

### `ajouter_favori` sans vérification d'existence
**Problème :** un numéro inexistant pouvait être ajouté aux favoris.
**Fix :** vérification que le numéro correspond à un compte réel, et
blocage de l'auto-ajout.

### `expire_secondes` sans bornes
**Problème :** valeurs négatives, nulles ou excessives acceptées telles
quelles pour les messages temporaires.
**Fix :** bornage entre 10 secondes et 7 jours (`EXPIRE_SECONDES_MIN/MAX`).

### Groupes sans limites de taille
**Problème :** pas de limite sur la longueur du nom de groupe, le nombre
de membres (même en illimité premium) ni la taille du message épinglé.
**Fix :** nom de groupe limité à 100 caractères, plafond dur de 500
membres, message épinglé limité à 1000 caractères.

### `reply_to` non validé dans les messages de groupe
**Problème :** le champ pouvait contenir n'importe quel type de donnée
(objet, liste, texte énorme), relayé tel quel à tous les membres.
**Fix :** conversion forcée en texte, tronqué à 64 caractères.

### Type d'abonnement non validé côté admin
**Problème :** `admin_activer_premium` et `admin_confirmer_paiement`
acceptaient n'importe quelle valeur pour `type`, alors que ce champ est
utilisé dans la logique métier (statut fondateur, priorité support).
**Fix :** validation contre `("mensuel", "annuel", "fondateur")`.

## 🟡 Faible — robustesse (bonus)

### Crash sur paquet JSON non-objet
**Problème :** `p.get("action")` était appelé avant de vérifier que `p`
est bien un dictionnaire ; un JSON valide mais non-objet (ex. `[1,2,3]`)
provoquait une exception non gérée qui coupait la connexion du client.
**Fix :** vérification du type avant utilisation.

### Vérification de la taille du buffer réseau
**Problème :** la taille du buffer était vérifiée après l'ajout du
dernier paquet reçu (dépassement borné à 8 Ko, sans réel impact).
**Fix :** vérification déplacée avant l'ajout, par prudence.

### Compteur de connexions actives
**Problème :** `threading.active_count()` comptait tous les threads du
processus, pas seulement les connexions clients actives.
**Fix :** compteur dédié `connexions_count`, incrémenté/décrémenté
explicitement à l'entrée/sortie de `gerer_client`, protégé par son
propre verrou.

## Points examinés et jugés non prioritaires

- **Chiffrement E2E** : déjà correctement implémenté côté client
  (`termchat.py`) via X25519 + HKDF + Fernet, avec protection anti-MITM
  et empreinte de vérification manuelle. Le serveur ne voit jamais le
  texte en clair entre deux comptes à jour ; le champ `chiffre` n'est
  qu'un indicateur d'affichage.
- **Géo-vérification IP en HTTP** (`ip-api.com`) : fonctionnalité
  désactivée par défaut (`ALLOW_INSECURE_GEOIP_CHECK=0`), non exploitable
  en configuration standard.
- **Lecture-modification-écriture sans transaction** (favoris, blocage,
  membres de groupe) : risque de perte de mise à jour en cas de requêtes
  quasi simultanées du même compte, sans impact sécurité direct.
- **Paiement fourni par le client** (`code_transaction`, `montant`) :
  activation nécessite toujours une validation manuelle par un admin ;
  pas une vulnérabilité en soi, dépend de la rigueur du contrôle humain.

