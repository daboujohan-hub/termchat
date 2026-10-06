# Journal de stabilisation — TermChat
Aboudev Labs 🇨🇮 — chaque modification du serveur est notée ici.

## 2026-10-06 — Lot 1 (corrections sûres)
- Fuite mémoire corrigée : `connexions_en_attente_totp` est vidé quand la connexion se ferme.
- Journal « ECHEC ENVOI » : affiche seulement le type du paquet (plus de messages ni de photos).
- Bannière du serveur passée de v6.1 à v6.3.
- Sauvegarde avant ce lot : server.py.avant_stabilisation_1
