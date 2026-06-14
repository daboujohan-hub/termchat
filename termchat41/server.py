#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════╗
║         TERMCHAT v4.1  — SERVEUR                        ║
║         by Aboudev Labs 🇨🇮                              ║
║  Nouveautés : Indicateurs, Sécurité, Admin, Notifs      ║
╚══════════════════════════════════════════════════════════╝
"""

import socket, threading, json, os, random, hashlib
import datetime, time, base64, signal, sys

# ══════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════
PORT       = int(os.environ.get("PORT", 9999))
DATA_DIR   = os.path.join(os.path.expanduser("~"), ".termchat_data")
DATA_FILE  = os.path.join(DATA_DIR, "db.json")
FILES_DIR  = os.path.join(DATA_DIR, "files")
ADMIN_CODE = os.environ.get("ADMIN_CODE", "aboudev2025")  # code admin secret

# ══════════════════════════════════════════════════════════
#  PAYS
# ══════════════════════════════════════════════════════════
PAYS = {
    "1":  ("Côte d'Ivoire", "+225"), "2":  ("Sénégal",      "+221"),
    "3":  ("Mali",          "+223"), "4":  ("Burkina Faso",  "+226"),
    "5":  ("Guinée",        "+224"), "6":  ("Togo",          "+228"),
    "7":  ("Bénin",         "+229"), "8":  ("Niger",         "+227"),
    "9":  ("Cameroun",      "+237"), "10": ("Congo",         "+242"),
    "11": ("Gabon",         "+241"), "12": ("Ghana",         "+233"),
    "13": ("Nigeria",       "+234"), "14": ("France",        "+33"),
    "15": ("Belgique",      "+32"),  "16": ("Canada",        "+1"),
    "17": ("USA",           "+1"),   "18": ("Maroc",         "+212"),
    "19": ("Algérie",       "+213"), "20": ("Tunisie",       "+216"),
}

# ══════════════════════════════════════════════════════════
#  UTILITAIRES
# ══════════════════════════════════════════════════════════
def hacher(mdp):    return hashlib.sha256(mdp.encode()).hexdigest()
def horodatage():   return datetime.datetime.now().isoformat()
def heure():        return datetime.datetime.now().strftime("%H:%M")
def fmt(o):
    if o < 1024:      return f"{o} o"
    elif o < 1024**2: return f"{o//1024} Ko"
    else:             return f"{o//1024//1024} Mo"

# ── Chiffrement XOR simple ────────────────────────────────
def generer_cle(n1, n2):
    """Génère une clé partagée entre deux numéros."""
    base = "".join(sorted([n1, n2]))
    return hashlib.sha256(base.encode()).hexdigest()

def chiffrer(texte, cle):
    """Chiffre/déchiffre un texte avec XOR."""
    try:
        octets = texte.encode("utf-8")
        cle_b  = (cle * ((len(octets) // len(cle)) + 1)).encode("utf-8")
        xored  = bytes(a ^ b for a, b in zip(octets, cle_b))
        return base64.b64encode(xored).decode("utf-8")
    except:
        return texte

def dechiffrer(texte_b64, cle):
    """Déchiffre un texte XOR encodé en base64."""
    try:
        octets = base64.b64decode(texte_b64.encode("utf-8"))
        cle_b  = (cle * ((len(octets) // len(cle)) + 1)).encode("utf-8")
        xored  = bytes(a ^ b for a, b in zip(octets, cle_b))
        return xored.decode("utf-8")
    except:
        return texte_b64

# ══════════════════════════════════════════════════════════
#  BASE DE DONNÉES
# ══════════════════════════════════════════════════════════
def charger():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(FILES_DIR, exist_ok=True)
    if not os.path.exists(DATA_FILE):
        sauver({"users": {}, "historique": {}, "groupes": {}, "stats": {
            "messages_total": 0, "fichiers_total": 0, "inscriptions_total": 0
        }})
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def sauver(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def gen_numero(prefixe):
    data = charger()
    nums = {u["numero"] for u in data["users"].values()}
    while True:
        n = prefixe + str(random.randint(1000000000, 9999999999))
        if n not in nums: return n

def sauver_msg(de, vers, texte, type_msg="texte", nom_fich=None, chiffre=False):
    data = charger()
    cle  = "_".join(sorted([de, vers]))
    hist = data.get("historique", {})
    hist.setdefault(cle, [])
    msg = {"de": de, "vers": vers, "texte": texte,
           "type": type_msg, "heure": horodatage(), "lu": False, "chiffre": chiffre}
    if nom_fich: msg["fichier"] = nom_fich
    hist[cle].append(msg)
    hist[cle] = hist[cle][-500:]
    data["historique"] = hist
    data.setdefault("stats", {})
    data["stats"]["messages_total"] = data["stats"].get("messages_total", 0) + 1
    sauver(data)

def get_hist(n1, n2, limite=50):
    data = charger()
    cle  = "_".join(sorted([n1, n2]))
    return data.get("historique", {}).get(cle, [])[-limite:]

def marquer_lus(destinataire, expediteur):
    data = charger()
    cle  = "_".join(sorted([destinataire, expediteur]))
    hist = data.get("historique", {}).get(cle, [])
    changed = False
    for msg in hist:
        if msg.get("vers") == destinataire and not msg.get("lu"):
            msg["lu"] = True
            changed = True
    if changed:
        data["historique"][cle] = hist
        sauver(data)

def compter_non_lus(numero):
    """Compte les messages non lus pour un utilisateur."""
    data = charger()
    total = 0
    for cle, msgs in data.get("historique", {}).items():
        for msg in msgs:
            if msg.get("vers") == numero and not msg.get("lu"):
                total += 1
    return total

# ══════════════════════════════════════════════════════════
#  CLIENTS CONNECTÉS
# ══════════════════════════════════════════════════════════
clients      = {}   # numero → socket
clients_info = {}   # numero → {nom, derniere_activite}
lock         = threading.Lock()
TIMEOUT_INACTIVITE = 1800  # 30 minutes

def envoyer_srv(sock, paquet):
    try: sock.sendall((json.dumps(paquet, ensure_ascii=False) + "\n").encode())
    except: pass

def livrer(numero, paquet):
    with lock: s = clients.get(numero)
    if s: envoyer_srv(s, paquet); return True
    return False

def maj_activite(numero):
    with lock:
        if numero in clients_info:
            clients_info[numero]["derniere_activite"] = time.time()

# ══════════════════════════════════════════════════════════
#  GESTION CLIENT
# ══════════════════════════════════════════════════════════
def gerer_client(conn, addr):
    num_co = None
    buf    = ""
    est_admin = False

    try:
        while True:
            conn.settimeout(TIMEOUT_INACTIVITE)
            try:
                chunk = conn.recv(8192).decode("utf-8", errors="replace")
            except socket.timeout:
                if num_co:
                    envoyer_srv(conn, {"type": "timeout", "msg": "Déconnecté pour inactivité."})
                break
            if not chunk: break
            buf += chunk

            while "\n" in buf:
                ligne, buf = buf.split("\n", 1)
                ligne = ligne.strip()
                if not ligne: continue
                try:    p = json.loads(ligne)
                except: continue

                act = p.get("action", "")
                if num_co: maj_activite(num_co)

                # ── INSCRIPTION ───────────────────────────
                if act == "inscrire":
                    nom     = p.get("nom", "").strip()
                    mdp     = p.get("mdp", "").strip()
                    prefixe = p.get("prefixe", "+225").strip()
                    couleur = p.get("couleur", "cyan")

                    if not nom or not mdp:
                        envoyer_srv(conn, {"ok": False, "msg": "Nom et mot de passe requis."}); continue
                    if len(nom) < 2 or len(nom) > 20:
                        envoyer_srv(conn, {"ok": False, "msg": "Nom : 2 à 20 caractères."}); continue
                    if len(mdp) < 4:
                        envoyer_srv(conn, {"ok": False, "msg": "Mot de passe : min 4 caractères."}); continue

                    data = charger()
                    for u in data["users"].values():
                        if u["nom"].lower() == nom.lower():
                            envoyer_srv(conn, {"ok": False, "msg": f"Nom '{nom}' déjà utilisé."}); break
                    else:
                        numero = gen_numero(prefixe)
                        pays   = next((v[0] for v in PAYS.values() if v[1] == prefixe), "Inconnu")
                        data["users"][nom.lower()] = {
                            "nom": nom, "numero": numero, "mdp": hacher(mdp),
                            "pays": pays, "prefixe": prefixe, "bio": "",
                            "couleur": couleur, "inscription": horodatage(),
                            "est_admin": False, "bloque": []
                        }
                        data.setdefault("stats", {})
                        data["stats"]["inscriptions_total"] = data["stats"].get("inscriptions_total", 0) + 1
                        sauver(data)
                        envoyer_srv(conn, {"ok": True, "numero": numero, "nom": nom, "pays": pays})

                # ── CONNEXION ─────────────────────────────
                elif act == "connecter":
                    nom  = p.get("nom", "").strip().lower()
                    mdp  = p.get("mdp", "").strip()
                    data = charger()
                    user = data["users"].get(nom)

                    if not user:
                        envoyer_srv(conn, {"ok": False, "msg": "Compte introuvable."})
                    elif user["mdp"] != hacher(mdp):
                        envoyer_srv(conn, {"ok": False, "msg": "Mot de passe incorrect."})
                    else:
                        num_co    = user["numero"]
                        est_admin = user.get("est_admin", False)
                        with lock:
                            clients[num_co] = conn
                            clients_info[num_co] = {"nom": user["nom"], "derniere_activite": time.time()}
                        non_lus = compter_non_lus(num_co)
                        envoyer_srv(conn, {
                            "ok": True, "nom": user["nom"], "numero": num_co,
                            "pays": user.get("pays",""), "bio": user.get("bio",""),
                            "couleur": user.get("couleur","cyan"),
                            "est_admin": est_admin, "non_lus": non_lus
                        })
                        _notifier_statut(num_co, True, data)

                # ── EN TRAIN D'ÉCRIRE ──────────────────────
                elif act == "typing":
                    if not num_co: continue
                    dest = p.get("dest", "").strip()
                    data = charger()
                    exp  = next((u for u in data["users"].values() if u["numero"] == num_co), None)
                    if exp:
                        livrer(dest, {
                            "type": "typing",
                            "de":   exp["nom"],
                            "numero": num_co,
                            "actif": p.get("actif", True)
                        })

                # ── DÉCONNECTER ────────────────────────────
                elif act == "deconnecter": break

                # ── CHERCHER ──────────────────────────────
                elif act == "chercher":
                    numero = p.get("numero", "").strip()
                    data   = charger()
                    trouve = next((u for u in data["users"].values() if u["numero"] == numero), None)
                    if trouve:
                        # Vérifier si bloqué
                        bloque_par = num_co and num_co in trouve.get("bloque", [])
                        envoyer_srv(conn, {"ok": True, "user": {
                            "nom": trouve["nom"], "numero": trouve["numero"],
                            "pays": trouve.get("pays",""), "bio": trouve.get("bio",""),
                            "en_ligne": numero in clients, "bloque": bloque_par
                        }})
                    else:
                        envoyer_srv(conn, {"ok": False, "msg": "Utilisateur introuvable."})

                # ── MESSAGE ────────────────────────────────
                elif act == "message":
                    if not num_co: envoyer_srv(conn, {"ok": False, "msg": "Non connecté."}); continue
                    dest       = p.get("dest", "").strip()
                    texte      = p.get("texte", "").strip()
                    est_chiffre = p.get("chiffre", False)

                    if not texte or not dest: continue
                    data = charger()
                    exp  = next((u for u in data["users"].values() if u["numero"] == num_co), None)

                    dest_user = next((u for u in data["users"].values() if u["numero"] == dest), None)
                    if not dest_user: envoyer_srv(conn, {"ok": False, "msg": "Destinataire introuvable."}); continue

                    # Vérifier si bloqué
                    if num_co in dest_user.get("bloque", []):
                        envoyer_srv(conn, {"ok": False, "msg": "Tu es bloqué par cet utilisateur."}); continue

                    sauver_msg(num_co, dest, texte, chiffre=est_chiffre)
                    livre = livrer(dest, {
                        "type": "message", "de": exp["nom"],
                        "numero": num_co, "texte": texte,
                        "heure": heure(), "chiffre": est_chiffre
                    })
                    envoyer_srv(conn, {"ok": True, "livre": livre})

                    # Notification de livraison
                    if livre:
                        livrer(num_co, {"type": "livre", "dest": dest})

                # ── MARQUER LU ────────────────────────────
                elif act == "marquer_lu":
                    if not num_co: continue
                    avec = p.get("avec", "").strip()
                    marquer_lus(num_co, avec)
                    # Notifier l'expéditeur que messages lus
                    livrer(avec, {"type": "lu", "par": num_co})

                # ── ENVOYER FICHIER ────────────────────────
                elif act == "envoyer_fichier":
                    if not num_co: envoyer_srv(conn, {"ok": False, "msg": "Non connecté."}); continue
                    dest     = p.get("dest", "").strip()
                    nom_fich = p.get("nom_fichier", "fichier")
                    c64      = p.get("contenu", "")
                    taille   = p.get("taille", 0)

                    if taille > 10*1024*1024: envoyer_srv(conn, {"ok": False, "msg": "Max 10 MB."}); continue
                    data = charger()
                    exp  = next((u for u in data["users"].values() if u["numero"] == num_co), None)
                    if not any(u["numero"] == dest for u in data["users"].values()):
                        envoyer_srv(conn, {"ok": False, "msg": "Destinataire introuvable."}); continue

                    safe   = "".join(c for c in nom_fich if c.isalnum() or c in "._-")
                    chemin = os.path.join(FILES_DIR, f"{int(time.time())}_{safe}")
                    try:
                        with open(chemin, "wb") as f: f.write(base64.b64decode(c64))
                    except Exception as e:
                        envoyer_srv(conn, {"ok": False, "msg": f"Erreur : {e}"}); continue

                    sauver_msg(num_co, dest, f"[Fichier] {nom_fich}", "fichier", nom_fich)
                    data2 = charger()
                    data2.setdefault("stats", {})
                    data2["stats"]["fichiers_total"] = data2["stats"].get("fichiers_total", 0) + 1
                    sauver(data2)

                    livre = livrer(dest, {
                        "type": "fichier", "de": exp["nom"], "numero": num_co,
                        "nom_fichier": nom_fich, "contenu": c64,
                        "taille": taille, "heure": heure()
                    })
                    envoyer_srv(conn, {"ok": True, "livre": livre, "msg": f"'{nom_fich}' envoyé."})

                # ── EFFACER HISTORIQUE ─────────────────────
                elif act == "effacer_historique":
                    if not num_co: continue
                    avec = p.get("avec", "").strip()
                    data = charger()
                    cle  = "_".join(sorted([num_co, avec]))
                    if cle in data.get("historique", {}):
                        data["historique"][cle] = []
                        sauver(data)
                    envoyer_srv(conn, {"ok": True, "msg": "Historique effacé."})

                # ── BLOQUER ────────────────────────────────
                elif act == "bloquer":
                    if not num_co: continue
                    cible  = p.get("numero", "").strip()
                    action = p.get("bloquer", True)
                    data   = charger()
                    for cle, u in data["users"].items():
                        if u["numero"] == num_co:
                            bloque = u.get("bloque", [])
                            if action and cible not in bloque:
                                bloque.append(cible)
                            elif not action and cible in bloque:
                                bloque.remove(cible)
                            data["users"][cle]["bloque"] = bloque
                            sauver(data)
                            msg = "Utilisateur bloqué." if action else "Utilisateur débloqué."
                            envoyer_srv(conn, {"ok": True, "msg": msg}); break

                # ── CHANGER COULEUR ────────────────────────
                elif act == "changer_couleur":
                    if not num_co: continue
                    couleur = p.get("couleur", "cyan").strip()
                    data    = charger()
                    for cle, u in data["users"].items():
                        if u["numero"] == num_co:
                            data["users"][cle]["couleur"] = couleur
                            sauver(data)
                            envoyer_srv(conn, {"ok": True, "msg": f"Couleur changée !", "couleur": couleur}); break

                # ── HISTORIQUE ─────────────────────────────
                elif act == "historique":
                    if not num_co: continue
                    avec  = p.get("avec", "").strip()
                    hist  = get_hist(num_co, avec, p.get("limite", 50))
                    data  = charger()
                    noms  = {u["numero"]: u["nom"] for u in data["users"].values()}
                    for m in hist: m["nom_de"] = noms.get(m["de"], m["de"])
                    marquer_lus(num_co, avec)
                    livrer(avec, {"type": "lu", "par": num_co})
                    envoyer_srv(conn, {"ok": True, "historique": hist})

                # ── GROUPES ────────────────────────────────
                elif act == "creer_groupe":
                    if not num_co: continue
                    nom_g = p.get("nom", "").strip()
                    if not nom_g or len(nom_g) < 2: envoyer_srv(conn, {"ok": False, "msg": "Nom invalide."}); continue
                    data  = charger()
                    id_g  = f"grp_{int(time.time())}_{random.randint(1000,9999)}"
                    data.setdefault("groupes", {})[id_g] = {
                        "nom": nom_g, "createur": num_co,
                        "membres": [num_co], "creation": horodatage(), "historique": []
                    }
                    sauver(data)
                    envoyer_srv(conn, {"ok": True, "id_groupe": id_g, "nom": nom_g})

                elif act == "ajouter_groupe":
                    if not num_co: continue
                    id_g   = p.get("id_groupe", "").strip()
                    cible  = p.get("numero", "").strip()
                    data   = charger()
                    groupe = data.get("groupes", {}).get(id_g)
                    if not groupe: envoyer_srv(conn, {"ok": False, "msg": "Groupe introuvable."}); continue
                    if groupe["createur"] != num_co: envoyer_srv(conn, {"ok": False, "msg": "Accès refusé."}); continue
                    if not any(u["numero"] == cible for u in data["users"].values()):
                        envoyer_srv(conn, {"ok": False, "msg": "Utilisateur introuvable."}); continue
                    if cible in groupe["membres"]: envoyer_srv(conn, {"ok": False, "msg": "Déjà membre."}); continue
                    data["groupes"][id_g]["membres"].append(cible)
                    sauver(data)
                    livrer(cible, {"type": "invitation_groupe", "groupe": groupe["nom"], "id_groupe": id_g, "heure": heure()})
                    envoyer_srv(conn, {"ok": True, "msg": f"Membre ajouté au groupe '{groupe['nom']}'"})

                elif act == "msg_groupe":
                    if not num_co: continue
                    id_g   = p.get("id_groupe", "").strip()
                    texte  = p.get("texte", "").strip()
                    data   = charger()
                    groupe = data.get("groupes", {}).get(id_g)
                    if not groupe: continue
                    if num_co not in groupe.get("membres", []): continue
                    exp = next((u for u in data["users"].values() if u["numero"] == num_co), None)
                    for membre in groupe["membres"]:
                        if membre != num_co:
                            livrer(membre, {
                                "type": "msg_groupe", "groupe": groupe["nom"],
                                "id_groupe": id_g, "de": exp["nom"],
                                "numero": num_co, "texte": texte, "heure": heure()
                            })
                    data["groupes"][id_g].setdefault("historique", []).append({
                        "de": num_co, "nom": exp["nom"], "texte": texte, "heure": horodatage()
                    })
                    data["groupes"][id_g]["historique"] = data["groupes"][id_g]["historique"][-500:]
                    sauver(data)
                    envoyer_srv(conn, {"ok": True})

                elif act == "mes_groupes":
                    if not num_co: continue
                    data    = charger()
                    groupes = [{"id": gid, "nom": g["nom"], "membres": len(g["membres"]), "createur": g["createur"] == num_co}
                               for gid, g in data.get("groupes", {}).items() if num_co in g.get("membres", [])]
                    envoyer_srv(conn, {"ok": True, "groupes": groupes})

                # ── EN LIGNE ───────────────────────────────
                elif act == "en_ligne":
                    with lock: liste = list(clients.keys())
                    data = charger()
                    noms = {u["numero"]: u["nom"] for u in data["users"].values()}
                    envoyer_srv(conn, {"ok": True, "users": [
                        {"numero": n, "nom": noms.get(n, "?")} for n in liste if n != num_co
                    ]})

                # ── PROFIL ─────────────────────────────────
                elif act == "modifier_bio":
                    if not num_co: continue
                    bio  = p.get("bio", "").strip()[:150]
                    data = charger()
                    for cle, u in data["users"].items():
                        if u["numero"] == num_co:
                            data["users"][cle]["bio"] = bio; sauver(data)
                            envoyer_srv(conn, {"ok": True, "msg": "Bio mise à jour !"}); break

                elif act == "changer_mdp":
                    if not num_co: continue
                    ancien  = p.get("ancien", "").strip()
                    nouveau = p.get("nouveau", "").strip()
                    if len(nouveau) < 4: envoyer_srv(conn, {"ok": False, "msg": "Min 4 caractères."}); continue
                    data = charger()
                    for cle, u in data["users"].items():
                        if u["numero"] == num_co:
                            if u["mdp"] != hacher(ancien): envoyer_srv(conn, {"ok": False, "msg": "Ancien mdp incorrect."}); break
                            data["users"][cle]["mdp"] = hacher(nouveau); sauver(data)
                            envoyer_srv(conn, {"ok": True, "msg": "Mot de passe changé !"}); break

                elif act == "supprimer_compte":
                    if not num_co: continue
                    mdp  = p.get("mdp", "").strip()
                    data = charger()
                    for cle, u in data["users"].items():
                        if u["numero"] == num_co:
                            if u["mdp"] != hacher(mdp): envoyer_srv(conn, {"ok": False, "msg": "Mdp incorrect."}); break
                            del data["users"][cle]; sauver(data)
                            envoyer_srv(conn, {"ok": True, "msg": "Compte supprimé."})
                            num_co = None; break

                # ── ADMIN ──────────────────────────────────
                elif act == "admin_login":
                    code = p.get("code", "").strip()
                    if code == ADMIN_CODE:
                        est_admin = True
                        envoyer_srv(conn, {"ok": True, "msg": "✅ Accès admin accordé."})
                    else:
                        envoyer_srv(conn, {"ok": False, "msg": "Code incorrect."})

                elif act == "admin_stats":
                    if not est_admin: envoyer_srv(conn, {"ok": False, "msg": "Accès refusé."}); continue
                    data = charger()
                    with lock: en_ligne = len(clients)
                    stats = data.get("stats", {})
                    envoyer_srv(conn, {"ok": True, "stats": {
                        "utilisateurs":      len(data["users"]),
                        "en_ligne":          en_ligne,
                        "messages_total":    stats.get("messages_total", 0),
                        "fichiers_total":    stats.get("fichiers_total", 0),
                        "inscriptions_total":stats.get("inscriptions_total", 0),
                        "groupes":           len(data.get("groupes", {})),
                        "conversations":     len(data.get("historique", {}))
                    }})

                elif act == "admin_broadcast":
                    if not est_admin: envoyer_srv(conn, {"ok": False, "msg": "Accès refusé."}); continue
                    msg = p.get("msg", "").strip()
                    if not msg: continue
                    with lock: tous = list(clients.values())
                    for s in tous:
                        envoyer_srv(s, {"type": "annonce", "msg": msg, "heure": heure()})
                    envoyer_srv(conn, {"ok": True, "msg": f"Message envoyé à {len(tous)} utilisateurs."})

                elif act == "admin_users":
                    if not est_admin: envoyer_srv(conn, {"ok": False, "msg": "Accès refusé."}); continue
                    data  = charger()
                    with lock: en_ligne_set = set(clients.keys())
                    users = [{"nom": u["nom"], "numero": u["numero"], "pays": u.get("pays",""),
                              "inscription": u.get("inscription","")[:10],
                              "en_ligne": u["numero"] in en_ligne_set}
                             for u in data["users"].values()]
                    envoyer_srv(conn, {"ok": True, "users": users})

                elif act == "admin_kick":
                    if not est_admin: envoyer_srv(conn, {"ok": False, "msg": "Accès refusé."}); continue
                    cible = p.get("numero", "").strip()
                    with lock: s = clients.get(cible)
                    if s:
                        envoyer_srv(s, {"type": "kick", "msg": "Tu as été déconnecté par l'administrateur."})
                        try: s.close()
                        except: pass
                        envoyer_srv(conn, {"ok": True, "msg": "Utilisateur déconnecté."})
                    else:
                        envoyer_srv(conn, {"ok": False, "msg": "Utilisateur hors ligne."})

    except Exception as e:
        pass
    finally:
        if num_co:
            with lock:
                clients.pop(num_co, None)
                clients_info.pop(num_co, None)
            try:
                data = charger()
                _notifier_statut(num_co, False, data)
            except: pass
        try: conn.close()
        except: pass

def _notifier_statut(numero, en_ligne, data):
    user = next((u for u in data["users"].values() if u["numero"] == numero), None)
    if not user: return
    with lock:
        for num, sock in list(clients.items()):
            if num != numero:
                envoyer_srv(sock, {"type": "statut", "numero": numero,
                                   "nom": user["nom"], "en_ligne": en_ligne})

# ══════════════════════════════════════════════════════════
#  DÉMARRAGE
# ══════════════════════════════════════════════════════════
def main():
    charger()
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", PORT))
    srv.listen(200)
    print(f"╔══════════════════════════════════════════╗")
    print(f"║  💬  TERMCHAT v4.1 — SERVEUR ACTIF      ║")
    print(f"║  by Aboudev Labs 🇨🇮                     ║")
    print(f"╚══════════════════════════════════════════╝")
    print(f"✅ Port {PORT} | Données : {DATA_DIR}")

    def quitter(sig, frame):
        srv.close(); sys.exit(0)
    signal.signal(signal.SIGINT, quitter)
    signal.signal(signal.SIGTERM, quitter)

    while True:
        try:
            conn, addr = srv.accept()
            threading.Thread(target=gerer_client, args=(conn, addr), daemon=True).start()
        except: break

if __name__ == "__main__":
    main()
