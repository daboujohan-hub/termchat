#!/usr/bin/env python3
"""V1 : bloque envoyer_fichier côté serveur sauf si ALLOW_FILE_SEND=1 (les vocaux ne sont pas touchés).
Usage : python desactiver_fichiers_serveur.py [chemin/server.py]
"""
import sys, shutil, py_compile, time

chemin = sys.argv[1] if len(sys.argv) > 1 else "server.py"
src = open(chemin, encoding="utf-8").read()

a1 = 'ALLOW_INLINE_MEDIA = os.environ.get("ALLOW_INLINE_MEDIA", "0") == "1"\n'
n1 = a1 + 'ALLOW_FILE_SEND = os.environ.get("ALLOW_FILE_SEND", "0") == "1"  # V1 : envoi de fichiers désactivé\n'
a2 = ('                        if not ALLOW_INLINE_MEDIA:\n'
      '                            envoyer_srv(conn, {"ok":False,"msg":"Envoi inline de fichiers désactivé en production Internet."})\n')
n2 = ('                        if not ALLOW_INLINE_MEDIA or not ALLOW_FILE_SEND:\n'
      '                            envoyer_srv(conn, {"ok":False,"msg":"Envoi de fichiers bientôt disponible."})\n')

for a in (a1, a2):
    if src.count(a) != 1:
        sys.exit(f"STOP : motif introuvable ou multiple ({src.count(a)}) : {a[:70]!r}. Rien modifié.")

sauv = f"{chemin}.backup_fichiers_off_{time.strftime('%Y%m%d_%H%M%S')}"
shutil.copy2(chemin, sauv)
open(chemin, "w", encoding="utf-8").write(src.replace(a1, n1).replace(a2, n2))
try:
    py_compile.compile(chemin, doraise=True)
except Exception as e:
    shutil.copy2(sauv, chemin)
    sys.exit(f"ERREUR de compilation, fichier restauré : {e}")
print("OK : envoyer_fichier bloqué (sauf ALLOW_FILE_SEND=1).")
print(f"Sauvegarde : {sauv}")

