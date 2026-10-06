#!/usr/bin/env python3
"""Supprime le 1er bloc 'admin_reinitialiser_mdp' (doublon) dans server.py.
Garde la 2e version (mot de passe temporaire + e-mail + session coupée).
Usage : python corriger_doublon_mdp.py [chemin/server.py]
"""
import sys, shutil, py_compile, time

chemin = sys.argv[1] if len(sys.argv) > 1 else "server.py"
marque = 'elif act == "admin_reinitialiser_mdp":'
fin = 'elif act == "admin_reinitialiser_cle":'

lignes = open(chemin, encoding="utf-8").read().split("\n")
debuts = [i for i, l in enumerate(lignes) if l.strip() == marque]
if len(debuts) != 2:
    sys.exit(f"STOP : {len(debuts)} occurrence(s) trouvée(s), 2 attendues. Rien modifié.")

d = debuts[0]
f = next((i for i in range(d + 1, len(lignes)) if lignes[i].strip() == fin), None)
if f is None or f > debuts[1]:
    sys.exit("STOP : structure inattendue. Rien modifié.")

sauvegarde = f"{chemin}.backup_mdp_doublon_{time.strftime('%Y%m%d_%H%M%S')}"
shutil.copy2(chemin, sauvegarde)
nouveau = lignes[:d] + lignes[f:]
open(chemin, "w", encoding="utf-8").write("\n".join(nouveau))

try:
    py_compile.compile(chemin, doraise=True)
except Exception as e:
    shutil.copy2(sauvegarde, chemin)
    sys.exit(f"ERREUR de compilation, fichier restauré : {e}")

print(f"OK : {f - d} lignes supprimées (lignes {d+1} à {f}).")
print(f"Sauvegarde : {sauvegarde}")

