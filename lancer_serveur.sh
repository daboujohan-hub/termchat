#!/bin/bash
# Relance automatiquement le serveur TermChat s'il s'arrête.
# Usage : bash lancer_serveur.sh      (Ctrl+C pour arrêter pour de bon)
cd "$(dirname "$0")" || exit 1
[ -f env_serveur.sh ] && source ./env_serveur.sh   # tes variables (ADMIN_CODE, FIREBASE_CREDS, ...)

DELAI=5
while true; do
    DEBUT=$SECONDS
    echo "[$(date '+%F %T')] Démarrage du serveur..."
    python3 -u server.py
    CODE=$?
    # 130 = Ctrl+C, 143 = arrêt demandé : on s'arrête vraiment
    if [ $CODE -eq 130 ] || [ $CODE -eq 143 ]; then
        echo "[$(date '+%F %T')] Arrêt demandé. Fin."
        exit 0
    fi
    # S'il plante tout de suite (erreur de configuration), on attend de plus en plus
    if [ $((SECONDS - DEBUT)) -lt 20 ]; then
        DELAI=$((DELAI * 2)); [ $DELAI -gt 60 ] && DELAI=60
    else
        DELAI=5
    fi
    echo "[$(date '+%F %T')] Serveur arrêté (code $CODE). Redémarrage dans ${DELAI}s..."
    sleep $DELAI
done
