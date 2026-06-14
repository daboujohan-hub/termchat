#!/bin/bash
# TermChat v4.0 — Installation automatique by Aboudev Labs 🇨🇮

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  💬  TERMCHAT v4.0 — Installation           ║"
echo "║  by Aboudev Labs 🇨🇮                         ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# Télécharger le client
curl -s https://raw.githubusercontent.com/daboujohan-hub/termchat/main/termchat.py -o $PREFIX/bin/termchat

# Configurer l'adresse du serveur
sed -i 's/127.0.0.1/junction.proxy.rlwy.net/g' $PREFIX/bin/termchat
sed -i 's/else 9999/else 35030/g' $PREFIX/bin/termchat

# Rendre exécutable
chmod +x $PREFIX/bin/termchat

echo "✅ TermChat installé !"
echo ""
echo "Lance avec : termchat"
echo ""

# Lancer directement
termchat
