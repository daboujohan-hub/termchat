#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sauvegarde complète de Firestore (toutes les collections et sous-collections)
by Aboudev Labs CI

Usage (dans ~/termchat) :
    python3 sauvegarde_firestore.py

Réglages facultatifs (variables d'environnement) :
    BACKUP_DIR       dossier des sauvegardes   (défaut : ~/sauvegardes_termchat)
    BACKUP_GARDER    nombre de sauvegardes gardées (défaut : 14)
    BACKUP_EXCLURE   collections à ne pas sauvegarder, séparées par des virgules
                     (défaut : push_tokens)
Identifiants : FIREBASE_CREDS (JSON) ou le fichier firebase-credentials.json
"""
import os, sys, json, gzip, base64, shutil, datetime

DOSSIER = os.environ.get("BACKUP_DIR", os.path.join(os.path.expanduser("~"), "sauvegardes_termchat"))
GARDER = int(os.environ.get("BACKUP_GARDER", "14"))
EXCLURE = {c.strip() for c in os.environ.get("BACKUP_EXCLURE", "push_tokens").split(",") if c.strip()}


def en_json(o):
    """Convertit les types Firestore que JSON ne connaît pas."""
    if isinstance(o, (datetime.datetime, datetime.date)): return o.isoformat()
    if isinstance(o, (bytes, bytearray)): return {"__bytes_b64__": base64.b64encode(bytes(o)).decode("ascii")}
    if hasattr(o, "path"): return {"__ref__": o.path}                      # référence de document
    if hasattr(o, "latitude") and hasattr(o, "longitude"):                 # point GPS
        return {"__geo__": [o.latitude, o.longitude]}
    return str(o)


def lire_document(doc):
    """Un document avec ses sous-collections, récursivement."""
    sous = {}
    for col in doc.reference.collections():
        sous[col.id] = [lire_document(d) for d in col.stream()]
    res = {"id": doc.id, "data": doc.to_dict() or {}}
    if sous: res["sous_collections"] = sous
    return res


def sauvegarder(db, dossier_sortie):
    """Écrit un fichier .json.gz par collection. Renvoie {collection: nombre_de_documents}."""
    os.makedirs(dossier_sortie, exist_ok=True)
    bilan = {}
    for col in db.collections():
        if col.id in EXCLURE: continue
        docs = [lire_document(d) for d in col.stream()]
        chemin = os.path.join(dossier_sortie, f"{col.id}.json.gz")
        with gzip.open(chemin, "wt", encoding="utf-8") as f:
            json.dump(docs, f, default=en_json, ensure_ascii=False)
        bilan[col.id] = len(docs)
    return bilan


def nettoyer_anciennes(racine, garder):
    dossiers = sorted(d for d in os.listdir(racine) if os.path.isdir(os.path.join(racine, d)) and d.startswith("20"))
    for ancien in dossiers[:-garder] if garder > 0 else []:
        shutil.rmtree(os.path.join(racine, ancien), ignore_errors=True)
        print(f"🗑️  Ancienne sauvegarde supprimée : {ancien}")


def ouvrir_firestore():
    import firebase_admin
    from firebase_admin import credentials, firestore
    creds = os.environ.get("FIREBASE_CREDS", "")
    if creds:
        cred = credentials.Certificate(json.loads(creds))
    elif os.path.exists("firebase-credentials.json"):
        cred = credentials.Certificate("firebase-credentials.json")
    else:
        print("❌ Identifiants introuvables (FIREBASE_CREDS ou firebase-credentials.json)."); sys.exit(1)
    firebase_admin.initialize_app(cred)
    return firestore.client()


def main():
    db = ouvrir_firestore()
    os.makedirs(DOSSIER, mode=0o700, exist_ok=True)
    os.chmod(DOSSIER, 0o700)                    # ces données sont sensibles : lisibles par toi seul
    horodatage = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    sortie = os.path.join(DOSSIER, horodatage)
    print(f"💾 Sauvegarde vers {sortie} ...")
    try:
        bilan = sauvegarder(db, sortie)
    except Exception as e:
        shutil.rmtree(sortie, ignore_errors=True)   # pas de sauvegarde à moitié écrite
        print(f"❌ Échec de la sauvegarde : {e}"); sys.exit(1)
    for nom, n in sorted(bilan.items()): print(f"   {nom}: {n} document(s)")
    total = sum(bilan.values())
    if total == 0:
        shutil.rmtree(sortie, ignore_errors=True)
        print("❌ Base vide ou inaccessible : sauvegarde annulée."); sys.exit(1)
    os.chmod(sortie, 0o700)
    nettoyer_anciennes(DOSSIER, GARDER)
    print(f"✅ Sauvegarde terminée ({total} documents, {len(bilan)} collections).")


if __name__ == "__main__":
    main()
