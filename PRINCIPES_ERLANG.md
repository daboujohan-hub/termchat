# TermChat — Principes « Style Erlang »
Aboudev Labs 🇨🇮 — à relire avant chaque modification du serveur.

Origine (v5.0) : « Chaque client = un processus isolé qui ne peut pas
faire planter les autres. »

## Les 10 règles

1. **Un client = une connexion isolée.** Toute erreur reste dans
   `gerer_client`. Une exception ne doit jamais faire tomber le serveur.
2. **Nettoyage toujours dans `finally`.** Retirer le client de `clients`,
   prévenir ses contacts, fermer la connexion, décrémenter le compteur.
3. **Ne jamais bloquer le verrou global `lock`.** Pas d'envoi réseau, pas
   d'appel Firestore ou Redis pendant qu'on le tient. Ne jamais le reprendre
   à l'intérieur (blocage garanti).
4. **On envoie seulement par `envoyer_srv` ou `livrer`.** Jamais `sock.send`
   directement : ils gèrent le verrou par connexion et les erreurs.
5. **Une action reçue = une réponse envoyée**, même en cas d'erreur
   (`{"ok": false, "msg": ...}`).
6. **Des limites partout.** Nombre de connexions (`MAX_CONNEXIONS`), taille
   des messages et fichiers, fréquence des actions (`limite_depassee`),
   délai d'inactivité (`TIMEOUT`).
7. **Une panne d'un service annexe ne tue pas le serveur.** Redis, Storage
   ou push indisponibles : on continue en mode local et on le journalise.
8. **Les options risquées sont éteintes par défaut** (variables
   d'environnement) : `TERMCHAT_GEVENT`, `REDIS_URL`, `PHOTOS_STORAGE`,
   `PUSH_ACTIF`. On en active une seule à la fois, puis on observe.
9. **Un superviseur relance le serveur** : `lancer_serveur.sh` ou systemd.
   Le serveur peut « laisser planter » parce que quelqu'un le relève.
10. **L'application se reconnecte toute seule.** Sans ça, la règle 9 ne sert à rien.

## Avant chaque mise à jour
- Copier `server.py` dans `~/@5788/` sous un nom daté.
- `python3 -m py_compile server.py`
- Démarrer, tester : connexion, message, une écriture, l'admin.
- Surveiller la ligne `📊` du journal (connexions, mémoire, Redis).
- Une seule modification à la fois.

## Limites connues (à traiter plus tard, avec tests)
- Pas de boîte aux lettres par client : un téléphone qui ne lit plus ses
  messages peut retenir l'expéditeur jusqu'à 30 minutes.
- Une erreur imprévue dans une action coupe la connexion de ce client.
- La déconnexion d'une ancienne session (limite de sessions) se fait
  encore en tenant le verrou global.
- Avec plusieurs serveurs, la limite de sessions et l'écran de surveillance
  admin restent propres à chaque serveur.
