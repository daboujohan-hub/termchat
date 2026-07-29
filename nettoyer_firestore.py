#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de nettoyage Firestore pour TermChat.
Supprime TOUS les comptes utilisateurs, conversations, groupes et feedbacks
de test avant le lancement en production.

⚠️  ATTENTION : ce script supprime des donnees de facon DEFINITIVE.
    Verifie bien que FIREBASE_CREDS pointe vers le bon projet avant de lancer.

Usage :
    python3 nettoyer_firestore.py            -> mode "dry run" (affiche sans supprimer)
    python3 nettoyer_firestore.py --confirmer -> supprime pour de vrai
"""

import sys
import json
import os

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
except ImportError:
    print("❌ Le package firebase-admin n'est pas installe.")
    print("   Lance : pip install firebase-admin")
    sys.exit(1)

# ── Configuration ────────────────────────────────────────────────
# Le script cherche les identifiants dans cet ordre :
#   1) variable d'environnement FIREBASE_CREDS (JSON en une ligne)
#   2) fichier local firebase-credentials.json
CHEMIN_FICHIER_LOCAL = "firebase-credentials.json"


def charger_credentials():
    creds_env = os.environ.get("FIREBASE_CREDS", "")
    if creds_env:
        return json.loads(creds_env)
    if os.path.exists(CHEMIN_FICHIER_LOCAL):
        with open(CHEMIN_FICHIER_LOCAL, "r", encoding="utf-8") as f:
            return json.load(f)
    print(f"❌ Aucun identifiant trouve (ni FIREBASE_CREDS, ni {CHEMIN_FICHIER_LOCAL}).")
    sys.exit(1)


def supprimer_collection(db, nom_collection, dry_run=True, sous_collections=None):
    """Supprime tous les documents d'une collection (et leurs sous-collections)."""
    docs = list(db.collection(nom_collection).stream())
    print(f"\n📂 Collection '{nom_collection}' : {len(docs)} document(s) trouve(s)")

    for doc in docs:
        # Supprime les sous-collections d'abord (ex: historique/{id}/messages)
        if sous_collections:
            for sous_nom in sous_collections:
                sous_docs = list(doc.reference.collection(sous_nom).stream())
                if sous_docs:
                    print(f"   ↳ {doc.id}/{sous_nom} : {len(sous_docs)} document(s)")
                    if not dry_run:
                        for sd in sous_docs:
                            sd.reference.delete()

        if dry_run:
            print(f"   [DRY RUN] Supprimerait : {doc.id}")
        else:
            doc.reference.delete()
            print(f"   ✅ Supprime : {doc.id}")

    return len(docs)


def main():
    dry_run = "--confirmer" not in sys.argv

    print("╔══════════════════════════════════════════════╗")
    print("║   🧹  NETTOYAGE FIRESTORE — TermChat         ║")
    print("╚══════════════════════════════════════════════╝")

    if dry_run:
        print("\n⚠️  MODE SIMULATION (rien ne sera supprime).")
        print("   Relance avec --confirmer pour supprimer pour de vrai.\n")
    else:
        print("\n🔴 MODE REEL — les donnees vont etre supprimees definitivement !")
        reponse = input("   Tape 'OUI' en majuscules pour continuer : ")
        if reponse != "OUI":
            print("Annule.")
            sys.exit(0)

    creds_dict = charger_credentials()
    cred = credentials.Certificate(creds_dict)
    firebase_admin.initialize_app(cred)
    db = firestore.client()

    print(f"\n📍 Projet Firebase : {creds_dict.get('project_id')}")

    total = 0
    total += supprimer_collection(db, "users", dry_run)
    total += supprimer_collection(db, "historique", dry_run, sous_collections=["messages"])
    total += supprimer_collection(db, "groupes", dry_run, sous_collections=["messages"])
    total += supprimer_collection(db, "feedback", dry_run)

    print(f"\n{'📋 [SIMULATION]' if dry_run else '✅'} Total : {total} document(s) "
          f"{'seraient supprimes' if dry_run else 'supprimes'}.")


if __name__ == "__main__":
    main()

