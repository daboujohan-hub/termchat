#!/bin/bash
# ╔══════════════════════════════════════════════════════════╗
# ║   TERMCHAT v4.0 — Script d'installation                 ║
# ║   by Aboudev Labs 🇨🇮                                   ║
# ╚══════════════════════════════════════════════════════════╝

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  💬  TERMCHAT v4.0 — Installation           ║"
echo "║  by Aboudev Labs 🇨🇮                         ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# Vérifier Python
if ! command -v python3 &> /dev/null; then
    echo "📦 Installation de Python..."
    pkg install python -y
fi

echo "✅ Python détecté : $(python3 --version)"

# Créer le dossier de téléchargements
mkdir -p ~/termchat_downloads
echo "✅ Dossier ~/termchat_downloads créé"

# Copier le client dans usr/bin pour accès global
cp termchat.py $PREFIX/bin/termchat 2>/dev/null || cp termchat.py ~/termchat
chmod +x $PREFIX/bin/termchat 2>/dev/null || chmod +x ~/termchat

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  ✅  Installation terminée !                 ║"
echo "╠══════════════════════════════════════════════╣"
echo "║                                              ║"
echo "║  Pour lancer TermChat :                      ║"
echo "║                                              ║"
echo "║  → Serveur local :                           ║"
echo "║    python termchat.py                        ║"
echo "║                                              ║"
echo "║  → Serveur Render :                          ║"
echo "║    python termchat.py <host> <port>          ║"
echo "║                                              ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
