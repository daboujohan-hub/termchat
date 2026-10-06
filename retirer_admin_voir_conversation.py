#!/usr/bin/env python3
"""Retire l'action admin 'admin_voir_conversation' (lecture des conversations privées) de server.py.
Usage : python retirer_admin_voir_conversation.py [chemin/server.py]
"""
import sys, shutil, py_compile, time

chemin = sys.argv[1] if len(sys.argv) > 1 else "server.py"
debut = 'elif act == "admin_voir_conversation":'
fin = 'elif act == "admin_voir_fichiers":'

lignes = open(chemin, encoding="utf-8").read().split("\n")
d = [i for i, l in enumerate(lignes) if l.strip() == debut]
if len(d) != 1:
    sys.exit(f"STOP : {len(d)} occurrence(s) trouvée(s), 1 attendue. Rien modifié.")
d = d[0]
f = next((i for i in range(d + 1, len(lignes)) if lignes[i].strip() == fin), None)
if f is None or f - d > 60:
    sys.exit("STOP : structure inattendue. Rien modifié.")

sauvegarde = f"{chemin}.backup_voir_conversation_{time.strftime('%Y%m%d_%H%M%S')}"
shutil.copy2(chemin, sauvegarde)
open(chemin, "w", encoding="utf-8").write("\n".join(lignes[:d] + lignes[f:]))

try:
    py_compile.compile(chemin, doraise=True)
except Exception as e:
    shutil.copy2(sauvegarde, chemin)
    sys.exit(f"ERREUR de compilation, fichier restauré : {e}")

print(f"OK : {f - d} lignes supprimées (lignes {d+1} à {f}).")
print(f"Sauvegarde : {sauvegarde}")

