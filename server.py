#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TermChat v6.0 — Serveur — by Aboudev Labs CI
Optimisations v6:
  - DB en mémoire RAM (plus de charger() partout)
  - Index rapide numero → uid
  - Sauvegarde GitHub en batch (toutes les 30s)
  - Plus de système premium — tout le monde accède à tout
  - Anti-brute force (5 tentatives max)
  - Nouvelles fonctions: modifier msg, supprimer msg, quitter groupe,
    renommer groupe, historique groupe, bannir user, transfert message
"""

import socket, threading, json, os, random, hashlib
import datetime, time, base64, signal, sys
import urllib.request, urllib.error

PORT         = int(os.environ.get("PORT", 9999))
WS_PORT      = int(os.environ.get("WS_PORT", 8765))
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
GITHUB_REPO  = os.environ.get("GITHUB_REPO", "daboujohan-hub/termchat").strip()
GITHUB_FILE  = "data/db.json"
ADMIN_CODE   = os.environ.get("ADMIN_CODE", "aboudev2025")
GITHUB_BATCH = 30   # secondes entre chaque push GitHub
LIMITE_FICHIER = 50 * 1024 * 1024

DATA_DIR  = os.path.join(os.path.expanduser("~"), ".termchat_data")
DATA_FILE = os.path.join(DATA_DIR, "db.json")
FILES_DIR = os.path.join(DATA_DIR, "files")

PAYS = {
    "1": ("Cote d'Ivoire", "+225"),
    "2": ("Senegal",       "+221"),
    "3": ("Guinee",        "+224"),
    "4": ("Burkina Faso",  "+226"),
    "5": ("Ghana",         "+233"),
}
STATUTS = ["disponible", "occupe", "ne_pas_deranger", "absent"]

# ─── BASE DE DONNÉES EN MÉMOIRE ───────────────────────────────────────────────
DB           = {}
INDEX_NUMERO = {}   # numero → uid  (recherche O(1))
github_sha   = None
db_modifiee  = False
tentatives_login = {}  # ip → {count, locked_until}

def db_vide():
    return {
        "users": {}, "historique": {}, "groupes": {}, "canaux": {},
        "stats": {"messages_total": 0, "fichiers_total": 0, "inscriptions_total": 0},
        "bannis": []
    }

def reconstruire_index():
    global INDEX_NUMERO
    INDEX_NUMERO = {u["numero"]: uid for uid, u in DB["users"].items()}

def marquer_modifiee():
    global db_modifiee
    db_modifiee = True

# ─── UTILITAIRES ──────────────────────────────────────────────────────────────
def hacher(s):    return hashlib.sha256(s.encode()).hexdigest()
def horodatage(): return datetime.datetime.now().isoformat()
def heure():      return datetime.datetime.now().strftime("%H:%M")

def trouver_user(numero):
    uid = INDEX_NUMERO.get(numero)
    return DB["users"].get(uid) if uid else None

def trouver_uid(numero):
    return INDEX_NUMERO.get(numero)

def gen_numero(prefixe):
    nums = set(INDEX_NUMERO.keys())
    while True:
        n = prefixe + str(random.randint(1000000000, 9999999999))
        if n not in nums: return n

def est_banni(ip):
    return ip in DB.get("bannis", [])

# ─── ANTI BRUTE FORCE ─────────────────────────────────────────────────────────
def verifier_tentatives(ip):
    """Retourne True si l'IP est autorisée à tenter une connexion."""
    info = tentatives_login.get(ip, {"count": 0, "locked_until": 0})
    if info["locked_until"] > time.time():
        return False
    return True

def enregistrer_echec(ip):
    info = tentatives_login.get(ip, {"count": 0, "locked_until": 0})
    info["count"] += 1
    if info["count"] >= 5:
        info["locked_until"] = time.time() + 300  # bloqué 5 minutes
        info["count"] = 0
        print(f"[SECURITE] IP {ip} bloquée 5 min (trop de tentatives)")
    tentatives_login[ip] = info

def reinitialiser_tentatives(ip):
    tentatives_login.pop(ip, None)

# ─── GITHUB ───────────────────────────────────────────────────────────────────
def github_requete(methode, url, body=None):
    headers = {"Authorization": f"token {GITHUB_TOKEN}",
               "Accept": "application/vnd.github.v3+json",
               "Content-Type": "application/json", "User-Agent": "TermChat"}
    data = json.dumps(body).encode() if body else None
    req  = urllib.request.Request(url, data=data, headers=headers, method=methode)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"GitHub erreur ({methode}): {e}"); return None

def telecharger_depuis_github():
    global github_sha
    if not GITHUB_TOKEN: print("Pas de GITHUB_TOKEN - mode local"); return False
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE}"
    rep = github_requete("GET", url)
    if rep and "content" in rep:
        github_sha = rep.get("sha")
        try:
            contenu = base64.b64decode(rep["content"]).decode("utf-8")
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(DATA_FILE, "w", encoding="utf-8") as f: f.write(contenu)
            print("Données chargées depuis GitHub"); return True
        except Exception as e: print(f"Erreur décodage: {e}"); return False
    print("Base vide — premier démarrage"); return False

def pousser_sur_github():
    global github_sha, db_modifiee
    if not GITHUB_TOKEN: return
    try:
        b64 = base64.b64encode(json.dumps(DB, ensure_ascii=False, indent=2).encode()).decode()
        url  = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE}"
        body = {"message": "TermChat v6 save", "content": b64}
        if github_sha: body["sha"] = github_sha
        rep = github_requete("PUT", url, body)
        if rep and "content" in rep:
            github_sha = rep["content"].get("sha")
            db_modifiee = False
            print(f"[{heure()}] GitHub sauvegardé.")
    except Exception as e: print(f"GitHub save erreur: {e}")

def sauver_local():
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(DB, f, ensure_ascii=False, indent=2)

def boucle_sauvegarde():
    """Thread de sauvegarde batch GitHub."""
    while True:
        time.sleep(GITHUB_BATCH)
        if db_modifiee:
            sauver_local()
            if GITHUB_TOKEN:
                threading.Thread(target=pousser_sur_github, daemon=True).start()

def charger_db():
    global DB
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(FILES_DIR, exist_ok=True)
    telecharger_depuis_github()
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            DB = json.load(f)
        for cle, val in db_vide().items():
            DB.setdefault(cle, val)
    else:
        DB = db_vide()
        sauver_local()
    reconstruire_index()
    print(f"DB: {len(DB['users'])} utilisateurs, {len(DB['historique'])} conversations.")

# ─── MESSAGES ─────────────────────────────────────────────────────────────────
def sauver_msg(de, vers, texte, type_msg="texte", nom_fich=None,
               chiffre=False, reply_to=None, expire_secondes=None):
    cle = "_".join(sorted([de, vers]))
    DB["historique"].setdefault(cle, [])
    msg_id = f"{int(time.time())}_{random.randint(1000,9999)}"
    msg = {"id": msg_id, "de": de, "vers": vers, "texte": texte,
           "type": type_msg, "heure": horodatage(), "lu": False,
           "chiffre": chiffre, "reply_to": reply_to, "modifie": False}
    if expire_secondes: msg["expire_a"] = time.time() + int(expire_secondes)
    if nom_fich: msg["fichier"] = nom_fich
    DB["historique"][cle].append(msg)
    DB["historique"][cle] = DB["historique"][cle][-500:]
    DB["stats"]["messages_total"] = DB["stats"].get("messages_total", 0) + 1
    marquer_modifiee()
    return msg_id

def get_hist(n1, n2, limite=50):
    cle  = "_".join(sorted([n1, n2]))
    hist = DB["historique"].get(cle, [])
    now  = time.time()
    return [m for m in hist if not m.get("expire_a") or m["expire_a"] > now][-limite:]

def marquer_lus(dest, exp):
    cle  = "_".join(sorted([dest, exp]))
    hist = DB["historique"].get(cle, [])
    changed = False
    for m in hist:
        if m.get("vers") == dest and not m.get("lu"):
            m["lu"] = True; changed = True
    if changed: marquer_modifiee()

def compter_non_lus(numero):
    return sum(1 for msgs in DB["historique"].values()
               for m in msgs if m.get("vers") == numero and not m.get("lu"))

def get_conversations(numero):
    convs = []; now = time.time()
    noms  = {u["numero"]: u["nom"] for u in DB["users"].values()}
    for cle, msgs in DB["historique"].items():
        nums = cle.split("_")
        if len(nums) != 2 or numero not in nums: continue
        autre = next((n for n in nums if n != numero), None)
        if not autre: continue
        msgs_ok = [m for m in msgs if not m.get("expire_a") or m["expire_a"] > now]
        if not msgs_ok: continue
        dernier  = msgs_ok[-1]
        non_lus  = sum(1 for m in msgs_ok if m.get("vers") == numero and not m.get("lu"))
        convs.append({"numero": autre, "nom": noms.get(autre, autre),
                      "dernier_msg": dernier.get("texte", "")[:40],
                      "heure": dernier.get("heure", "")[:16].replace("T", " "),
                      "non_lus": non_lus})
    convs.sort(key=lambda x: x["heure"], reverse=True)
    return convs

# ─── CLIENTS ──────────────────────────────────────────────────────────────────
clients          = {}
admins_connectes = set()
lock             = threading.Lock()
TIMEOUT          = 1800

def envoyer_srv(sock, paquet):
    try: sock.sendall((json.dumps(paquet, ensure_ascii=False) + "\n").encode())
    except Exception: pass

def livrer(numero, paquet):
    with lock: s = clients.get(numero)
    if s: envoyer_srv(s, paquet); return True
    return False

def notifier_statut(numero, en_ligne):
    user = trouver_user(numero)
    if not user: return
    paquet = {"type": "statut", "numero": numero, "nom": user["nom"], "en_ligne": en_ligne}
    with lock: cibles = list(clients.items())
    for num, sock in cibles:
        if num != numero: envoyer_srv(sock, paquet)

# ─── GESTIONNAIRE CLIENT ──────────────────────────────────────────────────────
def gerer_client(conn, addr):
    ip        = addr[0]
    num_co    = None
    buf       = ""
    est_admin = False

    if est_banni(ip):
        envoyer_srv(conn, {"ok": False, "msg": "Accès refusé."})
        conn.close(); return

    try:
        while True:
            conn.settimeout(TIMEOUT)
            try: chunk = conn.recv(8192).decode("utf-8", errors="replace")
            except socket.timeout:
                if num_co: envoyer_srv(conn, {"type": "timeout", "msg": "Déconnecté pour inactivité."})
                break
            if not chunk: break
            buf += chunk

            while "\n" in buf:
                ligne, buf = buf.split("\n", 1); ligne = ligne.strip()
                if not ligne: continue
                try: p = json.loads(ligne)
                except Exception: continue
                act = p.get("action", "")

                # ── INSCRIPTION ──────────────────────────────────────────────
                if act == "inscrire":
                    nom     = p.get("nom","").strip()
                    mdp     = p.get("mdp","").strip()
                    prefixe = p.get("prefixe","+225").strip()
                    couleur = p.get("couleur","cyan")
                    if not nom or not mdp:
                        envoyer_srv(conn, {"ok": False, "msg": "Nom et mot de passe requis."})
                    elif len(nom) < 2 or len(nom) > 20:
                        envoyer_srv(conn, {"ok": False, "msg": "Nom: 2 à 20 caractères."})
                    elif len(mdp) < 4:
                        envoyer_srv(conn, {"ok": False, "msg": "Mot de passe: minimum 4 caractères."})
                    else:
                        numero = gen_numero(prefixe)
                        pays   = next((v[0] for v in PAYS.values() if v[1] == prefixe), "Inconnu")
                        uid    = f"u_{int(time.time())}_{random.randint(1000,9999)}"
                        DB["users"][uid] = {
                            "nom": nom, "numero": numero, "mdp": hacher(mdp),
                            "pays": pays, "prefixe": prefixe, "bio": "", "couleur": couleur,
                            "avatar": "", "statut": "disponible", "inscription": horodatage(),
                            "derniere_connexion": None, "favoris": [], "bloque": [],
                            "est_admin": False, "pin": None}
                        INDEX_NUMERO[numero] = uid
                        DB["stats"]["inscriptions_total"] = DB["stats"].get("inscriptions_total",0) + 1
                        marquer_modifiee()
                        envoyer_srv(conn, {"ok": True, "numero": numero, "nom": nom, "pays": pays})

                # ── CONNEXION PAR NOM ────────────────────────────────────────
                elif act == "connecter":
                    if not verifier_tentatives(ip):
                        envoyer_srv(conn, {"ok": False, "msg": "Trop de tentatives. Réessaie dans 5 min."})
                        continue
                    nom = p.get("nom","").strip(); mdp = p.get("mdp","").strip()
                    candidats = [(k,u) for k,u in DB["users"].items() if u["nom"].lower()==nom.lower()]
                    match = next(((k,u) for k,u in candidats if u["mdp"]==hacher(mdp)), None)
                    if not match:
                        enregistrer_echec(ip)
                        if len(candidats)>1:
                            envoyer_srv(conn, {"ok": False, "msg": "Plusieurs comptes. Connecte-toi par numéro.", "utiliser_numero": True})
                        else:
                            envoyer_srv(conn, {"ok": False, "msg": "Nom ou mot de passe incorrect."})
                    else:
                        reinitialiser_tentatives(ip)
                        uid, user = match; num_co = user["numero"]
                        est_admin = user.get("est_admin", False)
                        DB["users"][uid]["derniere_connexion"] = horodatage()
                        marquer_modifiee()
                        with lock:
                            clients[num_co] = conn
                            if est_admin: admins_connectes.add(num_co)
                        envoyer_srv(conn, {"ok": True, "nom": user["nom"], "numero": num_co,
                            "pays": user.get("pays",""), "bio": user.get("bio",""),
                            "avatar": user.get("avatar",""),
                            "couleur": user.get("couleur","cyan"),
                            "statut": user.get("statut","disponible"),
                            "est_admin": est_admin, "non_lus": compter_non_lus(num_co),
                            "a_pin": bool(user.get("pin"))})
                        notifier_statut(num_co, True)

                # ── CONNEXION PAR NUMÉRO ─────────────────────────────────────
                elif act == "connecter_numero":
                    if not verifier_tentatives(ip):
                        envoyer_srv(conn, {"ok": False, "msg": "Trop de tentatives. Réessaie dans 5 min."})
                        continue
                    numero = p.get("numero","").strip(); mdp = p.get("mdp","").strip()
                    uid  = trouver_uid(numero); user = DB["users"].get(uid) if uid else None
                    if not user or user["mdp"] != hacher(mdp):
                        enregistrer_echec(ip)
                        envoyer_srv(conn, {"ok": False, "msg": "Numéro ou mot de passe incorrect."})
                    else:
                        reinitialiser_tentatives(ip)
                        num_co = user["numero"]; est_admin = user.get("est_admin", False)
                        DB["users"][uid]["derniere_connexion"] = horodatage()
                        marquer_modifiee()
                        with lock:
                            clients[num_co] = conn
                            if est_admin: admins_connectes.add(num_co)
                        envoyer_srv(conn, {"ok": True, "nom": user["nom"], "numero": num_co,
                            "pays": user.get("pays",""), "bio": user.get("bio",""),
                            "avatar": user.get("avatar",""),
                            "couleur": user.get("couleur","cyan"),
                            "statut": user.get("statut","disponible"),
                            "est_admin": est_admin, "non_lus": compter_non_lus(num_co),
                            "a_pin": bool(user.get("pin"))})
                        notifier_statut(num_co, True)

                elif act == "deconnecter": break

                # ── TYPING ───────────────────────────────────────────────────
                elif act == "typing":
                    if num_co:
                        dest = p.get("dest","").strip()
                        exp  = trouver_user(num_co)
                        if exp: livrer(dest, {"type":"typing","de":exp["nom"],"numero":num_co,"actif":p.get("actif",True)})

                # ── CHERCHER ─────────────────────────────────────────────────
                elif act == "chercher":
                    if not num_co:
                        envoyer_srv(conn, {"ok": False, "msg": "Non connecté."})
                    else:
                        numero = p.get("numero","").strip()
                        trouve = trouver_user(numero)
                        if not trouve:
                            envoyer_srv(conn, {"ok": False, "msg": "Utilisateur introuvable."})
                        else:
                            en_ligne = numero in clients
                            dc = trouve.get("derniere_connexion")
                            if dc: dc = dc[:16].replace("T"," ")
                            envoyer_srv(conn, {"ok": True, "user": {
                                "nom": trouve["nom"], "numero": trouve["numero"],
                                "pays": trouve.get("pays",""), "bio": trouve.get("bio",""),
                                "avatar": trouve.get("avatar",""),
                                "statut": trouve.get("statut","disponible"),
                                "en_ligne": en_ligne,
                                "derniere_connexion": dc if not en_ligne else None}})

                # ── CONVERSATIONS ─────────────────────────────────────────────
                elif act == "mes_conversations":
                    if num_co:
                        envoyer_srv(conn, {"ok": True, "conversations": get_conversations(num_co)})

                # ── MESSAGE ───────────────────────────────────────────────────
                elif act == "message":
                    if not num_co:
                        envoyer_srv(conn, {"ok": False, "msg": "Non connecté."})
                    else:
                        dest     = p.get("dest","").strip()
                        texte    = p.get("texte","").strip()
                        chiffre  = p.get("chiffre", False)
                        reply_to = p.get("reply_to")
                        expire_s = p.get("expire_secondes")
                        if not texte or not dest:
                            envoyer_srv(conn, {"ok": False, "msg": "Message ou destinataire vide."})
                        else:
                            exp       = trouver_user(num_co)
                            dest_user = trouver_user(dest)
                            if not dest_user:
                                envoyer_srv(conn, {"ok": False, "msg": "Destinataire introuvable."})
                            elif num_co in dest_user.get("bloque",[]):
                                envoyer_srv(conn, {"ok": False, "msg": "Tu es bloqué par cet utilisateur."})
                            else:
                                msg_id = sauver_msg(num_co, dest, texte, chiffre=chiffre,
                                                    reply_to=reply_to, expire_secondes=expire_s)
                                livre  = livrer(dest, {"type":"message","de":exp["nom"] if exp else "?",
                                    "numero":num_co,"texte":texte,"heure":heure(),
                                    "chiffre":chiffre,"reply_to":reply_to,"msg_id":msg_id})
                                envoyer_srv(conn, {"ok": True, "livre": livre, "msg_id": msg_id})
                                if livre: livrer(num_co, {"type":"livre","dest":dest,"msg_id":msg_id})

                # ── MODIFIER MESSAGE ──────────────────────────────────────────
                elif act == "modifier_msg":
                    if num_co:
                        msg_id    = p.get("msg_id","")
                        nouveau   = p.get("texte","").strip()
                        avec      = p.get("avec","").strip()
                        cle       = "_".join(sorted([num_co, avec]))
                        hist      = DB["historique"].get(cle, [])
                        for m in hist:
                            if m["id"] == msg_id and m["de"] == num_co:
                                m["texte"] = nouveau; m["modifie"] = True; marquer_modifiee()
                                livrer(avec, {"type":"msg_modifie","msg_id":msg_id,"texte":nouveau})
                                envoyer_srv(conn, {"ok": True, "msg": "Message modifié."})
                                break
                        else:
                            envoyer_srv(conn, {"ok": False, "msg": "Message introuvable."})

                # ── SUPPRIMER MESSAGE ─────────────────────────────────────────
                elif act == "supprimer_msg":
                    if num_co:
                        msg_id = p.get("msg_id","")
                        avec   = p.get("avec","").strip()
                        cle    = "_".join(sorted([num_co, avec]))
                        hist   = DB["historique"].get(cle, [])
                        for i, m in enumerate(hist):
                            if m["id"] == msg_id and m["de"] == num_co:
                                hist[i]["texte"] = "[Message supprimé]"
                                hist[i]["supprime"] = True; marquer_modifiee()
                                livrer(avec, {"type":"msg_supprime","msg_id":msg_id})
                                envoyer_srv(conn, {"ok": True})
                                break
                        else:
                            envoyer_srv(conn, {"ok": False, "msg": "Message introuvable."})

                # ── TRANSFÉRER MESSAGE ────────────────────────────────────────
                elif act == "transferer_msg":
                    if num_co:
                        texte = p.get("texte","").strip()
                        dest  = p.get("dest","").strip()
                        exp   = trouver_user(num_co)
                        if texte and dest and trouver_user(dest):
                            msg_id = sauver_msg(num_co, dest, f"↪ {texte}")
                            livre  = livrer(dest, {"type":"message","de":exp["nom"] if exp else "?",
                                "numero":num_co,"texte":f"↪ {texte}","heure":heure(),"msg_id":msg_id})
                            envoyer_srv(conn, {"ok": True, "livre": livre})
                        else:
                            envoyer_srv(conn, {"ok": False, "msg": "Erreur de transfert."})

                # ── RÉACTION ──────────────────────────────────────────────────
                elif act == "reaction":
                    if num_co:
                        dest   = p.get("dest","").strip()
                        msg_id = p.get("msg_id","")
                        emoji  = p.get("emoji","👍")
                        exp    = trouver_user(num_co)
                        livrer(dest, {"type":"reaction","de":exp["nom"] if exp else "?",
                            "numero":num_co,"msg_id":msg_id,"emoji":emoji,"heure":heure()})
                        envoyer_srv(conn, {"ok": True})

                # ── MARQUER LU ────────────────────────────────────────────────
                elif act == "marquer_lu":
                    if num_co:
                        avec = p.get("avec","").strip()
                        marquer_lus(num_co, avec)
                        livrer(avec, {"type":"lu","par":num_co})

                # ── FICHIER ───────────────────────────────────────────────────
                elif act == "envoyer_fichier":
                    if not num_co:
                        envoyer_srv(conn, {"ok": False, "msg": "Non connecté."})
                    else:
                        dest     = p.get("dest","").strip()
                        nom_fich = p.get("nom_fichier","fichier")
                        c64      = p.get("contenu","")
                        taille   = p.get("taille",0)
                        exp      = trouver_user(num_co)
                        if taille > LIMITE_FICHIER:
                            envoyer_srv(conn, {"ok": False, "msg": "Fichier trop volumineux (max 50 MB)."})
                        elif not trouver_user(dest):
                            envoyer_srv(conn, {"ok": False, "msg": "Destinataire introuvable."})
                        else:
                            safe   = "".join(c for c in nom_fich if c.isalnum() or c in "._-") or "fichier"
                            chemin = os.path.join(FILES_DIR, f"{int(time.time())}_{safe}")
                            try:
                                with open(chemin,"wb") as f: f.write(base64.b64decode(c64))
                                sauver_msg(num_co, dest, f"[Fichier] {nom_fich}", "fichier", nom_fich)
                                DB["stats"]["fichiers_total"] = DB["stats"].get("fichiers_total",0)+1
                                marquer_modifiee()
                                livre = livrer(dest, {"type":"fichier","de":exp["nom"] if exp else "?",
                                    "numero":num_co,"nom_fichier":nom_fich,"contenu":c64,"taille":taille,"heure":heure()})
                                envoyer_srv(conn, {"ok": True, "livre": livre, "msg": f"'{nom_fich}' envoyé."})
                            except Exception as e:
                                envoyer_srv(conn, {"ok": False, "msg": f"Erreur: {e}"})

                # ── VOCAL ─────────────────────────────────────────────────────
                elif act == "envoyer_vocal":
                    if not num_co:
                        envoyer_srv(conn, {"ok": False, "msg": "Non connecté."})
                    else:
                        dest   = p.get("dest","").strip()
                        c64    = p.get("contenu","")
                        taille = p.get("taille",0)
                        duree  = p.get("duree",0)
                        exp    = trouver_user(num_co)
                        if taille > LIMITE_FICHIER:
                            envoyer_srv(conn, {"ok": False, "msg": "Max 50 MB."})
                        elif not trouver_user(dest):
                            envoyer_srv(conn, {"ok": False, "msg": "Destinataire introuvable."})
                        else:
                            nom_fich = f"vocal_{int(time.time())}.ogg"
                            chemin   = os.path.join(FILES_DIR, nom_fich)
                            try:
                                with open(chemin,"wb") as f: f.write(base64.b64decode(c64))
                                sauver_msg(num_co, dest, f"[Vocal] {duree}s", "vocal", nom_fich)
                                livre = livrer(dest, {"type":"vocal","de":exp["nom"] if exp else "?",
                                    "numero":num_co,"nom_fichier":nom_fich,"contenu":c64,"duree":duree,"taille":taille,"heure":heure()})
                                envoyer_srv(conn, {"ok": True, "livre": livre, "msg": "Vocal envoyé!"})
                            except Exception as e:
                                envoyer_srv(conn, {"ok": False, "msg": f"Erreur: {e}"})

                # ── HISTORIQUE ────────────────────────────────────────────────
                elif act == "historique":
                    if num_co:
                        avec = p.get("avec","").strip()
                        hist = get_hist(num_co, avec, p.get("limite",50))
                        noms = {u["numero"]:u["nom"] for u in DB["users"].values()}
                        for m in hist: m["nom_de"] = noms.get(m["de"], m["de"])
                        marquer_lus(num_co, avec)
                        livrer(avec, {"type":"lu","par":num_co})
                        envoyer_srv(conn, {"ok": True, "historique": hist})

                elif act == "rechercher_msg":
                    if num_co:
                        mot  = p.get("mot","").strip().lower()
                        avec = p.get("avec","").strip()
                        hist = get_hist(num_co, avec, 500)
                        res  = [m for m in hist if mot in m.get("texte","").lower()][-20:]
                        envoyer_srv(conn, {"ok": True, "resultats": res})

                elif act == "effacer_historique":
                    if num_co:
                        avec = p.get("avec","").strip()
                        cle  = "_".join(sorted([num_co, avec]))
                        if cle in DB["historique"]: DB["historique"][cle]=[]; marquer_modifiee()
                        envoyer_srv(conn, {"ok": True, "msg": "Historique effacé."})

                # ── STATUT ────────────────────────────────────────────────────
                elif act == "changer_statut":
                    if num_co:
                        statut = p.get("statut","disponible")
                        if statut not in STATUTS: statut="disponible"
                        uid = trouver_uid(num_co)
                        if uid:
                            DB["users"][uid]["statut"] = statut; marquer_modifiee()
                            nom_u = DB["users"][uid]["nom"]
                            with lock: cibles = list(clients.items())
                            for num, sock in cibles:
                                if num!=num_co:
                                    envoyer_srv(sock, {"type":"statut_change","numero":num_co,"nom":nom_u,"statut":statut})
                            envoyer_srv(conn, {"ok": True, "msg": f"Statut: {statut}"})

                # ── FAVORIS ───────────────────────────────────────────────────
                elif act == "ajouter_favori":
                    if num_co:
                        cible = p.get("numero","").strip()
                        uid   = trouver_uid(num_co)
                        if uid:
                            favoris = DB["users"][uid].get("favoris",[])
                            if cible not in favoris: favoris.append(cible)
                            DB["users"][uid]["favoris"] = favoris; marquer_modifiee()
                            envoyer_srv(conn, {"ok": True, "msg": "Ajouté aux favoris!"})

                elif act == "mes_favoris":
                    if num_co:
                        user    = trouver_user(num_co)
                        favoris = user.get("favoris",[]) if user else []
                        with lock: ens = set(clients.keys())
                        result  = [{"nom":trouver_user(n)["nom"],"numero":n,
                            "statut":trouver_user(n).get("statut","disponible"),
                            "avatar":trouver_user(n).get("avatar",""),
                            "en_ligne":n in ens}
                            for n in favoris if trouver_user(n)]
                        envoyer_srv(conn, {"ok": True, "favoris": result})

                # ── BLOCAGE ───────────────────────────────────────────────────
                elif act == "bloquer":
                    if num_co:
                        cible  = p.get("numero","").strip()
                        action = p.get("bloquer",True)
                        uid    = trouver_uid(num_co)
                        if uid:
                            bloque = DB["users"][uid].get("bloque",[])
                            if action and cible not in bloque: bloque.append(cible)
                            elif not action and cible in bloque: bloque.remove(cible)
                            DB["users"][uid]["bloque"] = bloque; marquer_modifiee()
                            envoyer_srv(conn, {"ok": True, "msg": "Bloqué." if action else "Débloqué."})

                # ── PROFIL ────────────────────────────────────────────────────
                elif act == "changer_couleur":
                    if num_co:
                        uid = trouver_uid(num_co)
                        if uid:
                            DB["users"][uid]["couleur"] = p.get("couleur","cyan"); marquer_modifiee()
                            envoyer_srv(conn, {"ok":True,"msg":"Couleur changée!"})

                elif act == "modifier_bio":
                    if num_co:
                        uid = trouver_uid(num_co)
                        if uid:
                            DB["users"][uid]["bio"] = p.get("bio","").strip()[:150]; marquer_modifiee()
                            envoyer_srv(conn, {"ok":True,"msg":"Bio mise à jour!"})

                elif act == "modifier_avatar":
                    if num_co:
                        uid = trouver_uid(num_co)
                        if uid:
                            DB["users"][uid]["avatar"] = p.get("avatar","").strip()[:2]; marquer_modifiee()
                            envoyer_srv(conn, {"ok":True,"msg":"Avatar mis à jour!"})

                elif act == "changer_mdp":
                    if not num_co:
                        envoyer_srv(conn, {"ok":False,"msg":"Non connecté."})
                    else:
                        ancien = p.get("ancien","").strip()
                        nouveau= p.get("nouveau","").strip()
                        uid    = trouver_uid(num_co)
                        if len(nouveau)<4:
                            envoyer_srv(conn, {"ok":False,"msg":"Min 4 caractères."})
                        elif not uid or DB["users"][uid]["mdp"]!=hacher(ancien):
                            envoyer_srv(conn, {"ok":False,"msg":"Ancien mot de passe incorrect."})
                        else:
                            DB["users"][uid]["mdp"]=hacher(nouveau); marquer_modifiee()
                            envoyer_srv(conn, {"ok":True,"msg":"Mot de passe changé!"})

                elif act == "supprimer_compte":
                    if not num_co:
                        envoyer_srv(conn, {"ok":False,"msg":"Non connecté."})
                    else:
                        mdp = p.get("mdp","").strip()
                        uid = trouver_uid(num_co)
                        if not uid or DB["users"][uid]["mdp"]!=hacher(mdp):
                            envoyer_srv(conn, {"ok":False,"msg":"Mot de passe incorrect."})
                        else:
                            del DB["users"][uid]; del INDEX_NUMERO[num_co]; marquer_modifiee()
                            envoyer_srv(conn, {"ok":True,"msg":"Compte supprimé."}); num_co=None

                elif act == "deconnecter_partout":
                    if num_co:
                        # Déconnecter tous les clients avec ce numéro
                        with lock:
                            for k, s in list(clients.items()):
                                if k == num_co and s != conn:
                                    envoyer_srv(s, {"type":"kick","msg":"Déconnecté depuis un autre appareil."})
                                    try: s.close()
                                    except: pass
                        envoyer_srv(conn, {"ok":True,"msg":"Autres sessions déconnectées."})

                # ── PIN ───────────────────────────────────────────────────────
                elif act == "definir_pin":
                    if num_co:
                        pin = p.get("pin","").strip()
                        if len(pin)!=4 or not pin.isdigit():
                            envoyer_srv(conn, {"ok":False,"msg":"Le PIN doit être 4 chiffres."})
                        else:
                            uid = trouver_uid(num_co)
                            if uid: DB["users"][uid]["pin"]=hacher(pin); marquer_modifiee()
                            envoyer_srv(conn, {"ok":True,"msg":"Code PIN activé!"})

                elif act == "supprimer_pin":
                    if num_co:
                        uid = trouver_uid(num_co)
                        if uid: DB["users"][uid]["pin"]=None; marquer_modifiee()
                        envoyer_srv(conn, {"ok":True,"msg":"Code PIN désactivé."})

                elif act == "verifier_pin":
                    if num_co:
                        pin  = p.get("pin","").strip()
                        user = trouver_user(num_co)
                        if not user or not user.get("pin"):
                            envoyer_srv(conn, {"ok":True,"msg":"Pas de PIN défini."})
                        elif user["pin"]==hacher(pin):
                            envoyer_srv(conn, {"ok":True,"msg":"PIN correct."})
                        else:
                            envoyer_srv(conn, {"ok":False,"msg":"PIN incorrect."})

                # ── GROUPES ───────────────────────────────────────────────────
                elif act == "creer_groupe":
                    if num_co:
                        nom_g = p.get("nom","").strip()
                        if nom_g:
                            id_g  = f"grp_{int(time.time())}_{random.randint(1000,9999)}"
                            DB["groupes"][id_g] = {"nom":nom_g,"createur":num_co,
                                "membres":[num_co],"creation":horodatage(),
                                "historique":[],"epingle":None}
                            marquer_modifiee()
                            envoyer_srv(conn, {"ok":True,"id_groupe":id_g,"nom":nom_g})

                elif act == "renommer_groupe":
                    if num_co:
                        id_g   = p.get("id_groupe","").strip()
                        nom_g  = p.get("nom","").strip()
                        groupe = DB["groupes"].get(id_g)
                        if not groupe:
                            envoyer_srv(conn, {"ok":False,"msg":"Groupe introuvable."})
                        elif groupe["createur"] != num_co:
                            envoyer_srv(conn, {"ok":False,"msg":"Seul le créateur peut renommer."})
                        else:
                            groupe["nom"] = nom_g; marquer_modifiee()
                            for m in groupe["membres"]:
                                livrer(m, {"type":"groupe_renomme","id_groupe":id_g,"nom":nom_g})
                            envoyer_srv(conn, {"ok":True,"msg":f"Groupe renommé: {nom_g}"})

                elif act == "quitter_groupe":
                    if num_co:
                        id_g   = p.get("id_groupe","").strip()
                        groupe = DB["groupes"].get(id_g)
                        if groupe and num_co in groupe.get("membres",[]):
                            groupe["membres"].remove(num_co); marquer_modifiee()
                            exp = trouver_user(num_co)
                            for m in groupe["membres"]:
                                livrer(m, {"type":"membre_quitte","groupe":groupe["nom"],
                                    "nom":exp["nom"] if exp else "?","numero":num_co})
                            envoyer_srv(conn, {"ok":True,"msg":"Vous avez quitté le groupe."})
                        else:
                            envoyer_srv(conn, {"ok":False,"msg":"Groupe introuvable."})

                elif act == "ajouter_groupe":
                    if num_co:
                        id_g   = p.get("id_groupe","").strip()
                        cible  = p.get("numero","").strip()
                        groupe = DB["groupes"].get(id_g)
                        if not groupe:
                            envoyer_srv(conn, {"ok":False,"msg":"Groupe introuvable."})
                        elif groupe["createur"]!=num_co:
                            envoyer_srv(conn, {"ok":False,"msg":"Seul le créateur peut ajouter."})
                        elif not trouver_user(cible):
                            envoyer_srv(conn, {"ok":False,"msg":"Utilisateur introuvable."})
                        elif cible in groupe["membres"]:
                            envoyer_srv(conn, {"ok":False,"msg":"Déjà membre."})
                        else:
                            groupe["membres"].append(cible); marquer_modifiee()
                            livrer(cible, {"type":"invitation_groupe","groupe":groupe["nom"],"id_groupe":id_g,"heure":heure()})
                            envoyer_srv(conn, {"ok":True,"msg":"Membre ajouté!"})

                elif act == "epingler_groupe":
                    if num_co:
                        id_g   = p.get("id_groupe","").strip()
                        texte  = p.get("texte","").strip()
                        groupe = DB["groupes"].get(id_g)
                        if not groupe:
                            envoyer_srv(conn, {"ok":False,"msg":"Groupe introuvable."})
                        elif groupe["createur"]!=num_co:
                            envoyer_srv(conn, {"ok":False,"msg":"Accès refusé."})
                        else:
                            groupe["epingle"]=texte; marquer_modifiee()
                            for m in groupe["membres"]:
                                livrer(m, {"type":"epingle","groupe":groupe["nom"],"texte":texte,"heure":heure()})
                            envoyer_srv(conn, {"ok":True,"msg":"Message épinglé!"})

                elif act == "msg_groupe":
                    if num_co:
                        id_g   = p.get("id_groupe","").strip()
                        texte  = p.get("texte","").strip()
                        reply  = p.get("reply_to")
                        groupe = DB["groupes"].get(id_g)
                        if groupe and num_co in groupe.get("membres",[]) and texte:
                            exp = trouver_user(num_co)
                            for m in groupe["membres"]:
                                if m!=num_co:
                                    livrer(m, {"type":"msg_groupe","groupe":groupe["nom"],
                                        "id_groupe":id_g,"de":exp["nom"] if exp else "?",
                                        "numero":num_co,"texte":texte,"heure":heure(),"reply_to":reply})
                            groupe.setdefault("historique",[]).append({
                                "de":num_co,"nom":exp["nom"] if exp else "?",
                                "texte":texte,"heure":horodatage(),"reply_to":reply})
                            groupe["historique"]=groupe["historique"][-500:]
                            marquer_modifiee()
                            envoyer_srv(conn, {"ok":True})
                        else:
                            envoyer_srv(conn, {"ok":False,"msg":"Groupe introuvable ou non membre."})

                elif act == "hist_groupe":
                    if num_co:
                        id_g   = p.get("id_groupe","").strip()
                        groupe = DB["groupes"].get(id_g)
                        if not groupe or num_co not in groupe.get("membres",[]):
                            envoyer_srv(conn, {"ok":False,"msg":"Groupe introuvable."})
                        else:
                            envoyer_srv(conn, {"ok":True,
                                "historique":groupe.get("historique",[])[-50:],
                                "nom":groupe["nom"]})

                elif act == "mes_groupes":
                    if num_co:
                        groupes = [{"id":gid,"nom":g["nom"],"membres":len(g["membres"]),
                            "createur":g["createur"]==num_co,"epingle":g.get("epingle")}
                            for gid,g in DB["groupes"].items() if num_co in g.get("membres",[])]
                        envoyer_srv(conn, {"ok":True,"groupes":groupes})

                # ── CANAUX ────────────────────────────────────────────────────
                elif act == "creer_canal":
                    if num_co:
                        nom_c = p.get("nom","").strip()
                        desc  = p.get("description","").strip()[:150]
                        if nom_c and len(nom_c)>=2:
                            id_c  = f"canal_{int(time.time())}_{random.randint(1000,9999)}"
                            exp   = trouver_user(num_co)
                            DB["canaux"][id_c] = {"nom":nom_c,"description":desc,
                                "createur":num_co,"createur_nom":exp["nom"] if exp else "?",
                                "membres":[num_co],"creation":horodatage(),"historique":[]}
                            marquer_modifiee()
                            envoyer_srv(conn, {"ok":True,"id_canal":id_c,"nom":nom_c})

                elif act == "lister_canaux":
                    canaux = [{"id":cid,"nom":c["nom"],"description":c.get("description",""),
                        "membres":len(c["membres"]),"createur":c.get("createur_nom","?")}
                        for cid,c in DB["canaux"].items()]
                    envoyer_srv(conn, {"ok":True,"canaux":canaux})

                elif act == "rejoindre_canal":
                    if num_co:
                        id_c  = p.get("id_canal","").strip()
                        canal = DB["canaux"].get(id_c)
                        if not canal:
                            envoyer_srv(conn, {"ok":False,"msg":"Canal introuvable."})
                        else:
                            if num_co not in canal["membres"]: canal["membres"].append(num_co); marquer_modifiee()
                            envoyer_srv(conn, {"ok":True,"nom":canal["nom"]})

                elif act == "msg_canal":
                    if num_co:
                        id_c  = p.get("id_canal","").strip()
                        texte = p.get("texte","").strip()
                        canal = DB["canaux"].get(id_c)
                        if canal and num_co in canal.get("membres",[]) and texte:
                            exp = trouver_user(num_co)
                            for m in canal["membres"]:
                                if m!=num_co:
                                    livrer(m, {"type":"msg_canal","canal":canal["nom"],
                                        "id_canal":id_c,"de":exp["nom"] if exp else "?",
                                        "numero":num_co,"texte":texte,"heure":heure()})
                            canal.setdefault("historique",[]).append({
                                "de":num_co,"nom":exp["nom"] if exp else "?",
                                "texte":texte,"heure":horodatage()})
                            canal["historique"]=canal["historique"][-200:]
                            marquer_modifiee()
                            envoyer_srv(conn, {"ok":True})
                        else:
                            envoyer_srv(conn, {"ok":False,"msg":"Canal introuvable ou non membre."})

                elif act == "hist_canal":
                    if num_co:
                        id_c  = p.get("id_canal","").strip()
                        canal = DB["canaux"].get(id_c)
                        if not canal:
                            envoyer_srv(conn, {"ok":False,"msg":"Canal introuvable."})
                        else:
                            envoyer_srv(conn, {"ok":True,"historique":canal.get("historique",[])[-30:],"nom":canal["nom"]})

                # ── EN LIGNE ──────────────────────────────────────────────────
                elif act == "en_ligne":
                    noms    = {u["numero"]:u["nom"] for u in DB["users"].values()}
                    statuts = {u["numero"]:u.get("statut","disponible") for u in DB["users"].values()}
                    avatars = {u["numero"]:u.get("avatar","") for u in DB["users"].values()}
                    with lock: liste = list(clients.keys())
                    envoyer_srv(conn, {"ok":True,"users":[
                        {"numero":n,"nom":noms.get(n,"?"),"statut":statuts.get(n,"disponible"),"avatar":avatars.get(n,"")}
                        for n in liste if n!=num_co]})

                # ── ADMIN ─────────────────────────────────────────────────────
                elif act == "admin_login":
                    if p.get("code","") == ADMIN_CODE:
                        est_admin=True
                        if num_co:
                            uid = trouver_uid(num_co)
                            if uid: DB["users"][uid]["est_admin"]=True; marquer_modifiee()
                            with lock: admins_connectes.add(num_co)
                        envoyer_srv(conn, {"ok":True,"msg":"Accès admin accordé."})
                    else:
                        envoyer_srv(conn, {"ok":False,"msg":"Code incorrect."})

                elif act == "admin_stats":
                    if not est_admin:
                        envoyer_srv(conn, {"ok":False,"msg":"Accès refusé."})
                    else:
                        stats = DB.get("stats",{})
                        with lock: en_ligne = len(clients)
                        envoyer_srv(conn, {"ok":True,"stats":{
                            "utilisateurs":len(DB["users"]),
                            "en_ligne":en_ligne,
                            "messages_total":stats.get("messages_total",0),
                            "fichiers_total":stats.get("fichiers_total",0),
                            "inscriptions_total":stats.get("inscriptions_total",0),
                            "groupes":len(DB["groupes"]),
                            "canaux":len(DB["canaux"]),
                            "conversations":len(DB["historique"]),
                            "bannis":len(DB.get("bannis",[]))}})

                elif act == "admin_broadcast":
                    if not est_admin:
                        envoyer_srv(conn, {"ok":False,"msg":"Accès refusé."})
                    else:
                        msg = p.get("msg","").strip()
                        with lock: tous = list(clients.values())
                        for s in tous: envoyer_srv(s, {"type":"annonce","msg":msg,"heure":heure()})
                        envoyer_srv(conn, {"ok":True,"msg":f"Envoyé à {len(tous)} utilisateurs."})

                elif act == "admin_users":
                    if not est_admin:
                        envoyer_srv(conn, {"ok":False,"msg":"Accès refusé."})
                    else:
                        with lock: ens = set(clients.keys())
                        users = [{"nom":u["nom"],"numero":u["numero"],"pays":u.get("pays",""),
                            "inscription":(u.get("inscription") or "")[:10],
                            "derniere_connexion":(u.get("derniere_connexion") or "—")[:16],
                            "statut":u.get("statut","disponible"),"en_ligne":u["numero"] in ens,
                            "avatar":u.get("avatar","")}
                            for u in DB["users"].values()]
                        envoyer_srv(conn, {"ok":True,"users":users})

                elif act == "admin_kick":
                    if not est_admin:
                        envoyer_srv(conn, {"ok":False,"msg":"Accès refusé."})
                    else:
                        cible = p.get("numero","").strip()
                        with lock: s = clients.get(cible)
                        if s:
                            envoyer_srv(s, {"type":"kick","msg":"Déconnecté par l'administrateur."})
                            try: s.close()
                            except: pass
                            envoyer_srv(conn, {"ok":True,"msg":"Utilisateur déconnecté."})
                        else:
                            envoyer_srv(conn, {"ok":False,"msg":"Utilisateur hors ligne."})

                elif act == "admin_bannir":
                    if not est_admin:
                        envoyer_srv(conn, {"ok":False,"msg":"Accès refusé."})
                    else:
                        cible  = p.get("numero","").strip()
                        action = p.get("bannir", True)
                        bannis = DB.get("bannis",[])
                        if action and cible not in bannis:
                            bannis.append(cible)
                            # Kick si connecté
                            with lock: s = clients.get(cible)
                            if s:
                                envoyer_srv(s, {"type":"kick","msg":"Vous avez été banni."})
                                try: s.close()
                                except: pass
                        elif not action and cible in bannis:
                            bannis.remove(cible)
                        DB["bannis"] = bannis; marquer_modifiee()
                        envoyer_srv(conn, {"ok":True,"msg":"Banni." if action else "Débanni."})

                elif act == "admin_supprimer_user":
                    if not est_admin:
                        envoyer_srv(conn, {"ok":False,"msg":"Accès refusé."})
                    else:
                        cible = p.get("numero","").strip()
                        uid   = trouver_uid(cible)
                        if uid:
                            del DB["users"][uid]; del INDEX_NUMERO[cible]; marquer_modifiee()
                            with lock: s = clients.get(cible)
                            if s:
                                envoyer_srv(s, {"type":"kick","msg":"Compte supprimé par l'admin."})
                                try: s.close()
                                except: pass
                            envoyer_srv(conn, {"ok":True,"msg":"Utilisateur supprimé."})
                        else:
                            envoyer_srv(conn, {"ok":False,"msg":"Introuvable."})

                else:
                    envoyer_srv(conn, {"ok":False,"msg":f"Action inconnue: {act}"})

    except Exception:
        pass
    finally:
        if num_co:
            with lock:
                clients.pop(num_co, None)
                admins_connectes.discard(num_co)
            try: notifier_statut(num_co, False)
            except: pass
        try: conn.close()
        except: pass

# ─── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    print("╔══════════════════════════════════════╗")
    print("║  TERMCHAT v6.0 — by Aboudev Labs CI  ║")
    print("╚══════════════════════════════════════╝")
    charger_db()
    # Thread sauvegarde batch
    threading.Thread(target=boucle_sauvegarde, daemon=True).start()
    # Serveur TCP
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", PORT))
    srv.listen(500)
    print(f"✅ TCP port {PORT} | GitHub: {GITHUB_REPO} | Batch: {GITHUB_BATCH}s")
    def quitter(sig, frame): sauver_local(); srv.close(); sys.exit(0)
    signal.signal(signal.SIGINT, quitter)
    signal.signal(signal.SIGTERM, quitter)
    while True:
        try:
            conn, addr = srv.accept()
            threading.Thread(target=gerer_client, args=(conn,addr), daemon=True).start()
        except Exception:
            break

if __name__ == "__main__":
    main()
