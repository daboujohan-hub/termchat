# 💬 TermChat v4.0
**Messagerie Mondiale pour Développeurs**  
*by Aboudev Labs 🇨🇮*

---

## 🚀 Présentation

TermChat est la première messagerie instantanée conçue pour les développeurs africains qui vivent dans leur terminal.  
Fonctionne dans **Termux**, Linux, ou n'importe quel terminal avec Python.

---

## ✨ Fonctionnalités

- 👤 **Compte avec numéro par pays** — `+225XXXXXXXXXX` pour la Côte d'Ivoire, etc.
- 💬 **Messages privés** en temps réel
- 👥 **Groupes** — créer, rejoindre, discuter
- 📎 **Envoi de fichiers** (max 10 MB)
- 🔍 **Recherche** d'utilisateurs par numéro
- 🌐 **Utilisateurs en ligne** — voir qui est connecté
- 🔐 **Mots de passe hashés** (SHA-256)
- ✓ / ✗ **Statut du numéro** — vérifié ou inexistant
- 📜 **Historique** des conversations (500 messages)
- 🌍 **Mondial** — déployable sur Render, accessible partout

---

## 📦 Installation (Termux)

```bash
bash install.sh
```

---

## ▶️ Lancement

**Se connecter au serveur Render :**
```bash
python termchat.py <host-render> <port>
```

**Serveur local (test) :**
```bash
# Terminal 1 — lancer le serveur
python server.py

# Terminal 2 — lancer le client
python termchat.py
```

---

## 🌍 Déploiement sur Render

1. Upload le projet sur GitHub
2. Créer un **Background Worker** sur Render
3. Build command : `pip install -r requirements.txt`
4. Start command : `python server.py`
5. Variable : `PORT=9999`

---

## 🗂️ Structure

```
termchat/
├── server.py       → Serveur TCP (déployer sur Render)
├── termchat.py     → Client terminal (Termux/Linux)
├── install.sh      → Installation automatique
├── render.yaml     → Config Render
└── README.md       → Documentation
```

---

## 🌍 Pays supportés

Côte d'Ivoire (+225), Sénégal (+221), Mali (+223), Burkina Faso (+226),  
Guinée (+224), Togo (+228), Bénin (+229), Niger (+227), Cameroun (+237),  
Congo (+242), Gabon (+241), Ghana (+233), Nigeria (+234),  
France (+33), Belgique (+32), Canada/USA (+1), Maroc (+212), Algérie (+213), Tunisie (+216)

---

## 👨‍💻 Auteur

**Diomandé — Aboudev Labs 🇨🇮**  
Abidjan, Côte d'Ivoire

---

*TermChat — Chatte comme un dev, partout dans le monde.* 🌍
