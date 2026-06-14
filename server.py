#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════╗
║         TERMCHAT v4.2  — SERVEUR                        ║
║         by Aboudev Labs 🇨🇮                              ║
║  Nouveautés : Noms libres, Persistance, Statut,         ║
║               Favoris, Réponses, API REST, Bot API      ║
╚══════════════════════════════════════════════════════════╝
"""

import socket, threading, json, os, random, hashlib
import datetime, time, base64, signal, sys
import urllib.request, urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler

# ══════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════
PORT         = int(os.environ.get("PORT", 9999))
API_PORT     = int(os.environ.get("API_PORT", 8080))
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO  = os.environ.get("GITHUB_REPO", "daboujohan-hub/termchat")
GITHUB_FILE  = "data/db.json"
ADMIN_CODE   = os.environ.get("ADMIN_CODE", "aboudev2025")

DATA_DIR  = os.path.join(os.path.expanduser("~"), ".termchat_data")
DATA_FILE = os.path.join(DATA_DIR, "db.json")
FILES_DIR = os.path.join(DATA_DIR, "files")

github_sha = None

# ══════════════════════════════════════════════════════════
#  PAYS
# ══════════════════════════════════════════════════════════
PAYS = {
    "1":  ("Côte d'Ivoire", "+225"), "2":  ("Sénégal",     "+221"),
    "3":  ("Mali",          "+223"), "4":  ("Burkina Faso", "+226"),
    "5":  ("Guinée",        "+224"), "6":  ("Togo",         "+228"),
    "7":  ("Bénin",         "+229"), "8":  ("Niger",        "+227"),
    "9":  ("Cameroun",      "+237"), "10": ("Congo",        "+242"),
    "11": ("Gabon",         "+241"), "12": ("Ghana",        "+233"),
    "13": ("Nigeria",       "+234"), "14": ("France",       "+33"),
    "15": ("Belgique",      "+32"),  "16": ("Canada",       "+1"),
    "17": ("USA",           "+1"),   "18": ("Maroc",        "+212"),
    "19": ("Algérie",       "+213"), "20": ("Tunisie",      "+216"),
}

STATUTS = ["disponible", "occupe", "ne_pas_deranger", "absent"]

# ══════════════════════════════════════════════════════════
#  UTILITAIRES
# ══════════════════════════════════════════════════════════
def hacher(mdp):   return hashlib.sha256(mdp.encode()).hexdigest()
def horodatage():  return datetime.datetime.now().isoformat()
def heure():       return datetime.datetime.now().strftime("%H:%M")
def gen_token():   return hashlib.sha256(f"{time.time()}{random.random()}".encode()).hexdigest()[:32]

def fmt(o):
    if o < 1024:      return f"{o} o"
    elif o < 1024**2: return f"{o//1024} Ko"
    else:             return f"{o//1024//1024} Mo"

# ══════════════════════════════════════════════════════════
#  GITHUB — PERSISTANCE
# ══════════════════════════════════════════════════════════
def github_requete(methode, url, body=None):
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept":        "application/vnd.github.v3+json",
        "Content-Type":  "application/json",
        "User-Agent":    "TermChat-Server"
    }
    data = json.dumps(body).encode() if body else None
    req  = urllib.request.Request(url, data=data, headers=headers, method=methode)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404: return None
        raise
    except: return None

def telecharger_depuis_github():
    global github_sha
    if not GITHUB_TOKEN:
        print("⚠️  Pas de GITHUB_TOKEN — mode local")
        return False
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE}"
    rep = github_requete("GET", url)
    if rep and "content" in rep:
        github_sha = rep.get("sha")
        contenu    = base64.b64decode(rep["content"]).decode("utf-8")
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            f.write(contenu)
        print(f"✅ Données chargées depuis GitHub")
        return True
    print("📁 Base vide — premier démarrage")
    return False

def pousser_sur_github(data):
    global github_sha
    if not GITHUB_TOKEN: return
    try:
        contenu_b64 = base64.b64encode(
            json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        ).decode("utf-8")
        url  = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE}"
        body = {"message": "TermChat: sauvegarde données", "content": contenu_b64}
        if github_sha: body["sha"] = github_sha
        rep = github_requete("PUT", url, body)
        if rep and "content" in rep:
            github_sha = rep["content"].get("sha")
    except Exception as e:
        print(f"⚠️  GitHub save erreur : {e}")

# ══════════════════════════════════════════════════════════
#  BASE DE DONNÉES
# ══════════════════════════════════════════════════════════
def db_vide():
    return {
        "users": {}, "historique": {}, "groupes": {},
        "bots": {}, "api_tokens": {},
        "stats": {"messages_total": 0, "fichiers_total": 0, "inscriptions_total": 0}
    }

def charger():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(FILES_DIR, exist_ok=True)
    if not os.path.exists(DATA_FILE):
        sauver(db_vide())
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def sauver(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    if GITHUB_TOKEN:
        threading.Thread(target=pousser_sur_github, args=(data,), daemon=True).start()

def initialiser():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(FILES_DIR, exist_ok=True)
    ok = telecharger_depuis_github()
    if not ok and not os.path.exists(DATA_FILE):
        sauver(db_vide())

def gen_numero(prefixe):
    data = charger()
    nums = {u["numero"] for u in data["users"].values()}
    while True:
        n = prefixe + str(random.randint(1000000000, 9999999999))
        if n not in nums: return n

def sauver_msg(de, vers, texte, type_msg="texte", nom_fich=None, chiffre=False, reply_to=None):
    data = charger()
    cle  = "_".join(sorted([de, vers]))
    hist = data.get("historique", {})
    hist.setdefault(cle, [])
    msg_id = f"{int(time.time())}_{random.randint(1000,9999)}"
    msg = {
        "id": msg_id, "de": de, "vers": vers, "texte": texte,
        "type": type_msg, "heure": horodatage(), "lu": False,
        "chiffre": chiffre, "reply_to": reply_to
    }
    if nom_fich: msg["fichier"] = nom_fich
    hist[cle].append(msg)
    hist[cle] = hist[cle][-500:]
    data["historique"] = hist
    data["stats"]["messages_total"] = data["stats"].get("messages_total", 0) + 1
    sauver(data)
    return msg_id

def get_hist(n1, n2, limite=50):
    data = charger()
    cle  = "_".join(sorted([n1, n2]))
    return data.get("historique", {}).get(cle, [])[-limite:]

def marquer_lus(dest, exp):
    data = charger()
    cle  = "_".join(sorted([dest, exp]))
    hist = data.get("historique", {}).get(cle, [])
    for msg in hist:
        if msg.get("vers") == dest and not msg.get("lu"):
            msg["lu"] = True
    data["historique"][cle] = hist
    sauver(data)

def compter_non_lus(numero):
    data  = charger()
    total = 0
    for msgs in data.get("historique", {}).values():
        for msg in msgs:
            if msg.get("vers") == numero and not msg.get("lu"):
                total += 1
    return total

# ══════════════════════════════════════════════════════════
#  CLIENTS CONNECTÉS
# ══════════════════════════════════════════════════════════
clients      = {}
clients_info = {}
lock         = threading.Lock()
TIMEOUT      = 1800

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
#  API REST — SERVEUR HTTP
# ══════════════════════════════════════════════════════════
class TermChatAPI(BaseHTTPRequestHandler):
    def log_message(self, format, *args): pass  # Silence logs

    def repondre(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

    def get_body(self):
        longueur = int(self.headers.get("Content-Length", 0))
        if longueur:
            try: return json.loads(self.rfile.read(longueur).decode())
            except: return {}
        return {}

    def verifier_token(self, token):
        """Vérifie un token API et retourne le numéro."""
        data = charger()
        # Vérifier token utilisateur
        for num, tok in data.get("api_tokens", {}).items():
            if tok == token: return num, "user"
        # Vérifier token bot
        for bot_id, bot in data.get("bots", {}).items():
            if bot.get("token") == token: return bot_id, "bot"
        return None, None

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]
        params = {}
        if "?" in self.path:
            for p in self.path.split("?")[1].split("&"):
                if "=" in p:
                    k, v = p.split("=", 1)
                    params[k] = v

        # ── GET /api ──────────────────────────────────
        if path == "/api":
            self.repondre(200, {
                "name":    "TermChat API",
                "version": "4.2",
                "by":      "Aboudev Labs 🇨🇮",
                "endpoints": [
                    "POST /api/register",
                    "POST /api/login",
                    "POST /api/message",
                    "GET  /api/messages",
                    "GET  /api/users",
                    "GET  /api/me",
                    "POST /api/bot/create",
                    "POST /api/bot/send",
                    "GET  /api/stats"
                ]
            })

        # ── GET /api/users ────────────────────────────
        elif path == "/api/users":
            token = params.get("token") or self.headers.get("Authorization","").replace("Bearer ","")
            num, typ = self.verifier_token(token)
            if not num: self.repondre(401, {"error": "Token invalide"}); return
            data  = charger()
            with lock: en_ligne_set = set(clients.keys())
            users = [{"nom": u["nom"], "numero": u["numero"],
                      "pays": u.get("pays",""), "statut": u.get("statut","disponible"),
                      "en_ligne": u["numero"] in en_ligne_set}
                     for u in data["users"].values()]
            self.repondre(200, {"users": users, "total": len(users)})

        # ── GET /api/messages ─────────────────────────
        elif path == "/api/messages":
            token = params.get("token") or self.headers.get("Authorization","").replace("Bearer ","")
            num, typ = self.verifier_token(token)
            if not num: self.repondre(401, {"error": "Token invalide"}); return
            avec   = params.get("avec","")
            limite = int(params.get("limite", 50))
            hist   = get_hist(num, avec, limite)
            data   = charger()
            noms   = {u["numero"]: u["nom"] for u in data["users"].values()}
            for m in hist: m["nom_de"] = noms.get(m["de"], m["de"])
            self.repondre(200, {"messages": hist, "total": len(hist)})

        # ── GET /api/me ───────────────────────────────
        elif path == "/api/me":
            token = params.get("token") or self.headers.get("Authorization","").replace("Bearer ","")
            num, typ = self.verifier_token(token)
            if not num: self.repondre(401, {"error": "Token invalide"}); return
            data = charger()
            user = next((u for u in data["users"].values() if u["numero"] == num), None)
            if not user: self.repondre(404, {"error": "Utilisateur introuvable"}); return
            self.repondre(200, {
                "nom": user["nom"], "numero": user["numero"],
                "pays": user.get("pays",""), "bio": user.get("bio",""),
                "statut": user.get("statut","disponible"),
                "non_lus": compter_non_lus(num)
            })

        # ── GET /api/stats ────────────────────────────
        elif path == "/api/stats":
            data = charger()
            with lock: en_ligne = len(clients)
            stats = data.get("stats", {})
            self.repondre(200, {
                "utilisateurs":   len(data["users"]),
                "en_ligne":       en_ligne,
                "messages_total": stats.get("messages_total", 0),
                "groupes":        len(data.get("groupes", {})),
                "bots":           len(data.get("bots", {}))
            })

        else:
            self.repondre(404, {"error": "Endpoint introuvable"})

    def do_POST(self):
        path = self.path.split("?")[0]
        body = self.get_body()

        # ── POST /api/register ────────────────────────
        if path == "/api/register":
            nom     = body.get("nom", "").strip()
            mdp     = body.get("mdp", "").strip()
            prefixe = body.get("prefixe", "+225").strip()

            if not nom or not mdp:
                self.repondre(400, {"error": "Nom et mot de passe requis"}); return
            if len(nom) < 2 or len(nom) > 20:
                self.repondre(400, {"error": "Nom : 2 à 20 caractères"}); return
            if len(mdp) < 4:
                self.repondre(400, {"error": "Mot de passe : minimum 4 caractères"}); return

            data   = charger()
            numero = gen_numero(prefixe)
            pays   = next((v[0] for v in PAYS.values() if v[1] == prefixe), "Inconnu")
            uid    = f"u_{int(time.time())}_{random.randint(1000,9999)}"

            data["users"][uid] = {
                "nom": nom, "numero": numero, "mdp": hacher(mdp),
                "pays": pays, "prefixe": prefixe, "bio": "",
                "couleur": "cyan", "statut": "disponible",
                "inscription": horodatage(), "derniere_connexion": None,
                "favoris": [], "bloque": [], "est_admin": False
            }
            data["stats"]["inscriptions_total"] = data["stats"].get("inscriptions_total", 0) + 1
            sauver(data)
            self.repondre(201, {"ok": True, "numero": numero, "nom": nom, "pays": pays})

        # ── POST /api/login ───────────────────────────
        elif path == "/api/login":
            nom = body.get("nom", "").strip().lower()
            mdp = body.get("mdp", "").strip()
            data = charger()

            user = None
            uid  = None
            # Chercher par nom (peut y avoir plusieurs — on prend le premier qui match)
            for k, u in data["users"].items():
                if u["nom"].lower() == nom and u["mdp"] == hacher(mdp):
                    user = u; uid = k; break

            if not user:
                self.repondre(401, {"error": "Nom ou mot de passe incorrect"}); return

            # Générer token API
            token = gen_token()
            data["api_tokens"][user["numero"]] = token
            sauver(data)
            self.repondre(200, {
                "ok": True, "token": token,
                "nom": user["nom"], "numero": user["numero"],
                "pays": user.get("pays","")
            })

        # ── POST /api/message ─────────────────────────
        elif path == "/api/message":
            token = body.get("token") or self.headers.get("Authorization","").replace("Bearer ","")
            num, typ = self.verifier_token(token)
            if not num: self.repondre(401, {"error": "Token invalide"}); return

            dest     = body.get("dest","").strip()
            texte    = body.get("texte","").strip()
            reply_to = body.get("reply_to")

            if not dest or not texte:
                self.repondre(400, {"error": "dest et texte requis"}); return

            data = charger()
            exp  = next((u for u in data["users"].values() if u["numero"] == num), None)
            if not exp and typ == "bot":
                exp = data.get("bots", {}).get(num, {})

            if not any(u["numero"] == dest for u in data["users"].values()):
                self.repondre(404, {"error": "Destinataire introuvable"}); return

            nom_exp = exp.get("nom", "Bot") if exp else "?"
            msg_id  = sauver_msg(num, dest, texte, reply_to=reply_to)
            livre   = livrer(dest, {
                "type": "message", "de": nom_exp,
                "numero": num, "texte": texte,
                "heure": heure(), "reply_to": reply_to,
                "via_api": True
            })
            self.repondre(200, {"ok": True, "msg_id": msg_id, "livre": livre})

        # ── POST /api/bot/create ──────────────────────
        elif path == "/api/bot/create":
            token = body.get("token") or self.headers.get("Authorization","").replace("Bearer ","")
            num, typ = self.verifier_token(token)
            if not num: self.repondre(401, {"error": "Token invalide"}); return

            nom_bot = body.get("nom","").strip()
            if not nom_bot:
                self.repondre(400, {"error": "Nom du bot requis"}); return

            data      = charger()
            bot_token = gen_token()
            bot_id    = f"bot_{int(time.time())}_{random.randint(1000,9999)}"
            prefixe   = "+000"
            bot_num   = prefixe + str(random.randint(1000000000,9999999999))

            data.setdefault("bots", {})[bot_id] = {
                "nom":        nom_bot,
                "numero":     bot_num,
                "token":      bot_token,
                "proprietaire": num,
                "creation":   horodatage(),
                "description": body.get("description","")
            }
            sauver(data)
            self.repondre(201, {
                "ok":       True,
                "bot_id":   bot_id,
                "nom":      nom_bot,
                "numero":   bot_num,
                "token":    bot_token,
                "message":  "Bot créé ! Utilise ce token pour envoyer des messages."
            })

        # ── POST /api/bot/send ────────────────────────
        elif path == "/api/bot/send":
            token = body.get("token") or self.headers.get("Authorization","").replace("Bearer ","")
            num, typ = self.verifier_token(token)
            if not num or typ != "bot":
                self.repondre(401, {"error": "Token bot invalide"}); return

            dest  = body.get("dest","").strip()
            texte = body.get("texte","").strip()
            if not dest or not texte:
                self.repondre(400, {"error": "dest et texte requis"}); return

            data   = charger()
            bot    = data.get("bots",{}).get(num,{})
            msg_id = sauver_msg(num, dest, texte)
            livre  = livrer(dest, {
                "type":    "message",
                "de":      f"🤖 {bot.get('nom','Bot')}",
                "numero":  num,
                "texte":   texte,
                "heure":   heure(),
                "est_bot": True
            })
            self.repondre(200, {"ok": True, "msg_id": msg_id, "livre": livre})

        else:
            self.repondre(404, {"error": "Endpoint introuvable"})

def demarrer_api():
    """Lance le serveur HTTP API REST."""
    try:
        srv = HTTPServer(("0.0.0.0", API_PORT), TermChatAPI)
        print(f"🌐 API REST active sur le port {API_PORT}")
        srv.serve_forever()
    except Exception as e:
        print(f"⚠️  API non disponible : {e}")

# ══════════════════════════════════════════════════════════
#  GESTION CLIENT TCP
# ══════════════════════════════════════════════════════════
def gerer_client(conn, addr):
    num_co    = None
    buf       = ""
    est_admin = False

    try:
        while True:
            conn.settimeout(TIMEOUT)
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
                        envoyer_srv(conn, {"ok": False, "msg": "Minimum 4 caractères."}); continue

                    # ✅ NOMS LIBRES — pas de vérification de doublon sur le nom
                    data   = charger()
                    numero = gen_numero(prefixe)
                    pays   = next((v[0] for v in PAYS.values() if v[1] == prefixe), "Inconnu")
                    uid    = f"u_{int(time.time())}_{random.randint(1000,9999)}"

                    data["users"][uid] = {
                        "nom": nom, "numero": numero, "mdp": hacher(mdp),
                        "pays": pays, "prefixe": prefixe, "bio": "",
                        "couleur": couleur, "statut": "disponible",
                        "inscription": horodatage(), "derniere_connexion": None,
                        "favoris": [], "bloque": [], "est_admin": False
                    }
                    data["stats"]["inscriptions_total"] = data["stats"].get("inscriptions_total", 0) + 1
                    sauver(data)
                    envoyer_srv(conn, {"ok": True, "numero": numero, "nom": nom, "pays": pays})

                # ── CONNEXION ─────────────────────────────
                elif act == "connecter":
                    nom  = p.get("nom", "").strip()
                    mdp  = p.get("mdp", "").strip()
                    data = charger()

                    # Chercher par nom (insensible à la casse)
                    user = None
                    uid  = None
                    for k, u in data["users"].items():
                        if u["nom"].lower() == nom.lower() and u["mdp"] == hacher(mdp):
                            user = u; uid = k; break

                    if not user:
                        # Si plusieurs comptes avec ce nom, demander le numéro
                        doublons = [u for u in data["users"].values() if u["nom"].lower() == nom.lower()]
                        if len(doublons) > 1:
                            envoyer_srv(conn, {
                                "ok": False,
                                "msg": "Plusieurs comptes avec ce nom. Utilise ton numéro pour te connecter.",
                                "utiliser_numero": True
                            })
                        else:
                            envoyer_srv(conn, {"ok": False, "msg": "Nom ou mot de passe incorrect."})
                        continue

                    num_co    = user["numero"]
                    est_admin = user.get("est_admin", False)

                    # Mettre à jour dernière connexion
                    data["users"][uid]["derniere_connexion"] = horodatage()
                    sauver(data)

                    with lock:
                        clients[num_co] = conn
                        clients_info[num_co] = {"nom": user["nom"], "derniere_activite": time.time()}

                    non_lus = compter_non_lus(num_co)
                    envoyer_srv(conn, {
                        "ok": True, "nom": user["nom"], "numero": num_co,
                        "pays": user.get("pays",""), "bio": user.get("bio",""),
                        "couleur": user.get("couleur","cyan"), "statut": user.get("statut","disponible"),
                        "est_admin": est_admin, "non_lus": non_lus
                    })
                    _notifier_statut(num_co, True, data)

                # ── CONNEXION PAR NUMÉRO ──────────────────
                elif act == "connecter_numero":
                    numero = p.get("numero", "").strip()
                    mdp    = p.get("mdp", "").strip()
                    data   = charger()

                    user = None
                    uid  = None
                    for k, u in data["users"].items():
                        if u["numero"] == numero and u["mdp"] == hacher(mdp):
                            user = u; uid = k; break

                    if not user:
                        envoyer_srv(conn, {"ok": False, "msg": "Numéro ou mot de passe incorrect."}); continue

                    num_co    = user["numero"]
                    est_admin = user.get("est_admin", False)
                    data["users"][uid]["derniere_connexion"] = horodatage()
                    sauver(data)

                    with lock:
                        clients[num_co] = conn
                        clients_info[num_co] = {"nom": user["nom"], "derniere_activite": time.time()}

                    non_lus = compter_non_lus(num_co)
                    envoyer_srv(conn, {
                        "ok": True, "nom": user["nom"], "numero": num_co,
                        "pays": user.get("pays",""), "bio": user.get("bio",""),
                        "couleur": user.get("couleur","cyan"), "statut": user.get("statut","disponible"),
                        "est_admin": est_admin, "non_lus": non_lus
                    })
                    _notifier_statut(num_co, True, data)

                # ── TYPING ────────────────────────────────
                elif act == "typing":
                    if not num_co: continue
                    dest = p.get("dest", "").strip()
                    data = charger()
                    exp  = next((u for u in data["users"].values() if u["numero"] == num_co), None)
                    if exp:
                        livrer(dest, {"type": "typing", "de": exp["nom"],
                                      "numero": num_co, "actif": p.get("actif", True)})

                # ── DÉCONNECTER ───────────────────────────
                elif act == "deconnecter": break

                # ── CHERCHER ──────────────────────────────
                elif act == "chercher":
                    numero = p.get("numero", "").strip()
                    data   = charger()
                    trouve = next((u for u in data["users"].values() if u["numero"] == numero), None)
                    if trouve:
                        en_ligne = numero in clients
                        # Dernière connexion
                        dc = trouve.get("derniere_connexion")
                        if dc: dc = dc[:16].replace("T"," ")
                        envoyer_srv(conn, {"ok": True, "user": {
                            "nom": trouve["nom"], "numero": trouve["numero"],
                            "pays": trouve.get("pays",""), "bio": trouve.get("bio",""),
                            "statut": trouve.get("statut","disponible"),
                            "en_ligne": en_ligne,
                            "derniere_connexion": dc if not en_ligne else None
                        }})
                    else:
                        envoyer_srv(conn, {"ok": False, "msg": "Utilisateur introuvable."})

                # ── MESSAGE ───────────────────────────────
                elif act == "message":
                    if not num_co: continue
                    dest       = p.get("dest","").strip()
                    texte      = p.get("texte","").strip()
                    chiffre    = p.get("chiffre", False)
                    reply_to   = p.get("reply_to")
                    reaction   = p.get("reaction")

                    if not texte or not dest: continue
                    data = charger()
                    exp  = next((u for u in data["users"].values() if u["numero"] == num_co), None)
                    if not any(u["numero"] == dest for u in data["users"].values()):
                        envoyer_srv(conn, {"ok": False, "msg": "Destinataire introuvable."}); continue

                    msg_id = sauver_msg(num_co, dest, texte, chiffre=chiffre, reply_to=reply_to)
                    livre  = livrer(dest, {
                        "type": "message", "de": exp["nom"],
                        "numero": num_co, "texte": texte,
                        "heure": heure(), "chiffre": chiffre,
                        "reply_to": reply_to, "msg_id": msg_id
                    })
                    envoyer_srv(conn, {"ok": True, "livre": livre, "msg_id": msg_id})
                    if livre: livrer(num_co, {"type": "livre", "dest": dest, "msg_id": msg_id})

                # ── RÉACTION ──────────────────────────────
                elif act == "reaction":
                    if not num_co: continue
                    dest    = p.get("dest","").strip()
                    msg_id  = p.get("msg_id","").strip()
                    emoji   = p.get("emoji","👍")
                    data    = charger()
                    exp     = next((u for u in data["users"].values() if u["numero"] == num_co), None)
                    livrer(dest, {
                        "type":   "reaction",
                        "de":     exp["nom"] if exp else "?",
                        "numero": num_co,
                        "msg_id": msg_id,
                        "emoji":  emoji,
                        "heure":  heure()
                    })
                    envoyer_srv(conn, {"ok": True})

                # ── MARQUER LU ────────────────────────────
                elif act == "marquer_lu":
                    if not num_co: continue
                    avec = p.get("avec","").strip()
                    marquer_lus(num_co, avec)
                    livrer(avec, {"type": "lu", "par": num_co})

                # ── FICHIER ───────────────────────────────
                elif act == "envoyer_fichier":
                    if not num_co: continue
                    dest     = p.get("dest","").strip()
                    nom_fich = p.get("nom_fichier","fichier")
                    c64      = p.get("contenu","")
                    taille   = p.get("taille",0)
                    if taille > 10*1024*1024:
                        envoyer_srv(conn, {"ok": False, "msg": "Max 10 MB."}); continue
                    data = charger()
                    exp  = next((u for u in data["users"].values() if u["numero"] == num_co), None)
                    if not any(u["numero"] == dest for u in data["users"].values()):
                        envoyer_srv(conn, {"ok": False, "msg": "Introuvable."}); continue
                    safe   = "".join(c for c in nom_fich if c.isalnum() or c in "._-")
                    chemin = os.path.join(FILES_DIR, f"{int(time.time())}_{safe}")
                    try:
                        with open(chemin,"wb") as f: f.write(base64.b64decode(c64))
                    except Exception as e:
                        envoyer_srv(conn, {"ok": False, "msg": str(e)}); continue
                    sauver_msg(num_co, dest, f"[Fichier] {nom_fich}", "fichier", nom_fich)
                    data2 = charger()
                    data2["stats"]["fichiers_total"] = data2["stats"].get("fichiers_total",0) + 1
                    sauver(data2)
                    livre = livrer(dest, {
                        "type": "fichier", "de": exp["nom"], "numero": num_co,
                        "nom_fichier": nom_fich, "contenu": c64, "taille": taille, "heure": heure()
                    })
                    envoyer_srv(conn, {"ok": True, "livre": livre, "msg": f"'{nom_fich}' envoyé."})

                # ── EFFACER HISTORIQUE ─────────────────────
                elif act == "effacer_historique":
                    if not num_co: continue
                    avec = p.get("avec","").strip()
                    data = charger()
                    cle  = "_".join(sorted([num_co, avec]))
                    if cle in data.get("historique",{}):
                        data["historique"][cle] = []
                        sauver(data)
                    envoyer_srv(conn, {"ok": True, "msg": "Historique effacé."})

                # ── STATUT ────────────────────────────────
                elif act == "changer_statut":
                    if not num_co: continue
                    statut = p.get("statut","disponible")
                    if statut not in STATUTS: statut = "disponible"
                    data = charger()
                    for cle, u in data["users"].items():
                        if u["numero"] == num_co:
                            data["users"][cle]["statut"] = statut
                            sauver(data)
                            # Notifier les contacts
                            exp = u
                            with lock:
                                for num, sock in list(clients.items()):
                                    if num != num_co:
                                        envoyer_srv(sock, {
                                            "type":   "statut_change",
                                            "numero": num_co,
                                            "nom":    exp["nom"],
                                            "statut": statut
                                        })
                            envoyer_srv(conn, {"ok": True, "msg": f"Statut : {statut}"}); break

                # ── FAVORIS ───────────────────────────────
                elif act == "ajouter_favori":
                    if not num_co: continue
                    cible = p.get("numero","").strip()
                    data  = charger()
                    for cle, u in data["users"].items():
                        if u["numero"] == num_co:
                            favoris = u.get("favoris",[])
                            if cible not in favoris: favoris.append(cible)
                            data["users"][cle]["favoris"] = favoris
                            sauver(data)
                            envoyer_srv(conn, {"ok": True, "msg": "Ajouté aux favoris !"}); break

                elif act == "mes_favoris":
                    if not num_co: continue
                    data    = charger()
                    user    = next((u for u in data["users"].values() if u["numero"] == num_co), None)
                    favoris = user.get("favoris",[]) if user else []
                    with lock: en_ligne_set = set(clients.keys())
                    result  = []
                    for num_f in favoris:
                        u = next((u for u in data["users"].values() if u["numero"] == num_f), None)
                        if u:
                            result.append({
                                "nom": u["nom"], "numero": u["numero"],
                                "statut": u.get("statut","disponible"),
                                "en_ligne": num_f in en_ligne_set
                            })
                    envoyer_srv(conn, {"ok": True, "favoris": result})

                # ── RECHERCHE HISTORIQUE ──────────────────
                elif act == "rechercher_msg":
                    if not num_co: continue
                    mot  = p.get("mot","").strip().lower()
                    avec = p.get("avec","").strip()
                    hist = get_hist(num_co, avec, 500)
                    res  = [m for m in hist if mot in m.get("texte","").lower()][-20:]
                    envoyer_srv(conn, {"ok": True, "resultats": res, "total": len(res)})

                # ── BLOQUER ───────────────────────────────
                elif act == "bloquer":
                    if not num_co: continue
                    cible  = p.get("numero","").strip()
                    action = p.get("bloquer", True)
                    data   = charger()
                    for cle, u in data["users"].items():
                        if u["numero"] == num_co:
                            bloque = u.get("bloque",[])
                            if action and cible not in bloque: bloque.append(cible)
                            elif not action and cible in bloque: bloque.remove(cible)
                            data["users"][cle]["bloque"] = bloque
                            sauver(data)
                            envoyer_srv(conn, {"ok": True, "msg": "Bloqué." if action else "Débloqué."}); break

                # ── COULEUR ───────────────────────────────
                elif act == "changer_couleur":
                    if not num_co: continue
                    couleur = p.get("couleur","cyan")
                    data    = charger()
                    for cle, u in data["users"].items():
                        if u["numero"] == num_co:
                            data["users"][cle]["couleur"] = couleur
                            sauver(data)
                            envoyer_srv(conn, {"ok": True, "msg": "Couleur changée !", "couleur": couleur}); break

                # ── BIO ───────────────────────────────────
                elif act == "modifier_bio":
                    if not num_co: continue
                    bio  = p.get("bio","").strip()[:150]
                    data = charger()
                    for cle, u in data["users"].items():
                        if u["numero"] == num_co:
                            data["users"][cle]["bio"] = bio
                            sauver(data)
                            envoyer_srv(conn, {"ok": True, "msg": "Bio mise à jour !"}); break

                # ── MOT DE PASSE ──────────────────────────
                elif act == "changer_mdp":
                    if not num_co: continue
                    ancien  = p.get("ancien","").strip()
                    nouveau = p.get("nouveau","").strip()
                    if len(nouveau) < 4:
                        envoyer_srv(conn, {"ok": False, "msg": "Min 4 caractères."}); continue
                    data = charger()
                    for cle, u in data["users"].items():
                        if u["numero"] == num_co:
                            if u["mdp"] != hacher(ancien):
                                envoyer_srv(conn, {"ok": False, "msg": "Ancien mdp incorrect."}); break
                            data["users"][cle]["mdp"] = hacher(nouveau)
                            sauver(data)
                            envoyer_srv(conn, {"ok": True, "msg": "Mot de passe changé !"}); break

                # ── SUPPRIMER ─────────────────────────────
                elif act == "supprimer_compte":
                    if not num_co: continue
                    mdp  = p.get("mdp","").strip()
                    data = charger()
                    for cle, u in data["users"].items():
                        if u["numero"] == num_co:
                            if u["mdp"] != hacher(mdp):
                                envoyer_srv(conn, {"ok": False, "msg": "Mdp incorrect."}); break
                            del data["users"][cle]
                            sauver(data)
                            envoyer_srv(conn, {"ok": True, "msg": "Compte supprimé."})
                            num_co = None; break

                # ── HISTORIQUE ────────────────────────────
                elif act == "historique":
                    if not num_co: continue
                    avec = p.get("avec","").strip()
                    hist = get_hist(num_co, avec, p.get("limite",50))
                    data = charger()
                    noms = {u["numero"]: u["nom"] for u in data["users"].values()}
                    for m in hist: m["nom_de"] = noms.get(m["de"], m["de"])
                    marquer_lus(num_co, avec)
                    livrer(avec, {"type": "lu", "par": num_co})
                    envoyer_srv(conn, {"ok": True, "historique": hist})

                # ── GROUPES ───────────────────────────────
                elif act == "creer_groupe":
                    if not num_co: continue
                    nom_g = p.get("nom","").strip()
                    if not nom_g: continue
                    data  = charger()
                    id_g  = f"grp_{int(time.time())}_{random.randint(1000,9999)}"
                    data.setdefault("groupes",{})[id_g] = {
                        "nom": nom_g, "createur": num_co,
                        "membres": [num_co], "creation": horodatage(),
                        "historique": [], "epingle": None
                    }
                    sauver(data)
                    envoyer_srv(conn, {"ok": True, "id_groupe": id_g, "nom": nom_g})

                elif act == "ajouter_groupe":
                    if not num_co: continue
                    id_g   = p.get("id_groupe","").strip()
                    cible  = p.get("numero","").strip()
                    data   = charger()
                    groupe = data.get("groupes",{}).get(id_g)
                    if not groupe: envoyer_srv(conn, {"ok": False, "msg": "Groupe introuvable."}); continue
                    if groupe["createur"] != num_co: envoyer_srv(conn, {"ok": False, "msg": "Accès refusé."}); continue
                    if not any(u["numero"] == cible for u in data["users"].values()):
                        envoyer_srv(conn, {"ok": False, "msg": "Utilisateur introuvable."}); continue
                    if cible in groupe["membres"]: envoyer_srv(conn, {"ok": False, "msg": "Déjà membre."}); continue
                    data["groupes"][id_g]["membres"].append(cible)
                    sauver(data)
                    livrer(cible, {"type": "invitation_groupe", "groupe": groupe["nom"],
                                   "id_groupe": id_g, "heure": heure()})
                    envoyer_srv(conn, {"ok": True, "msg": "Membre ajouté !"})

                elif act == "epingler_groupe":
                    if not num_co: continue
                    id_g  = p.get("id_groupe","").strip()
                    texte = p.get("texte","").strip()
                    data  = charger()
                    groupe = data.get("groupes",{}).get(id_g)
                    if not groupe: continue
                    if groupe["createur"] != num_co: envoyer_srv(conn, {"ok": False, "msg": "Accès refusé."}); continue
                    data["groupes"][id_g]["epingle"] = texte
                    sauver(data)
                    for membre in groupe["membres"]:
                        livrer(membre, {"type": "epingle", "groupe": groupe["nom"],
                                        "texte": texte, "heure": heure()})
                    envoyer_srv(conn, {"ok": True, "msg": "Message épinglé !"})

                elif act == "msg_groupe":
                    if not num_co: continue
                    id_g   = p.get("id_groupe","").strip()
                    texte  = p.get("texte","").strip()
                    reply  = p.get("reply_to")
                    data   = charger()
                    groupe = data.get("groupes",{}).get(id_g)
                    if not groupe or num_co not in groupe.get("membres",[]): continue
                    exp = next((u for u in data["users"].values() if u["numero"] == num_co), None)
                    for membre in groupe["membres"]:
                        if membre != num_co:
                            livrer(membre, {
                                "type": "msg_groupe", "groupe": groupe["nom"],
                                "id_groupe": id_g, "de": exp["nom"],
                                "numero": num_co, "texte": texte,
                                "heure": heure(), "reply_to": reply
                            })
                    data["groupes"][id_g].setdefault("historique",[]).append({
                        "de": num_co, "nom": exp["nom"],
                        "texte": texte, "heure": horodatage(), "reply_to": reply
                    })
                    data["groupes"][id_g]["historique"] = data["groupes"][id_g]["historique"][-500:]
                    sauver(data)
                    envoyer_srv(conn, {"ok": True})

                elif act == "mes_groupes":
                    if not num_co: continue
                    data    = charger()
                    groupes = [{"id": gid, "nom": g["nom"], "membres": len(g["membres"]),
                                "createur": g["createur"] == num_co,
                                "epingle": g.get("epingle")}
                               for gid, g in data.get("groupes",{}).items()
                               if num_co in g.get("membres",[])]
                    envoyer_srv(conn, {"ok": True, "groupes": groupes})

                # ── EN LIGNE ──────────────────────────────
                elif act == "en_ligne":
                    with lock: liste = list(clients.keys())
                    data = charger()
                    noms = {u["numero"]: u["nom"] for u in data["users"].values()}
                    statuts = {u["numero"]: u.get("statut","disponible") for u in data["users"].values()}
                    envoyer_srv(conn, {"ok": True, "users": [
                        {"numero": n, "nom": noms.get(n,"?"), "statut": statuts.get(n,"disponible")}
                        for n in liste if n != num_co
                    ]})

                # ── TOKEN API ─────────────────────────────
                elif act == "get_api_token":
                    if not num_co: continue
                    data  = charger()
                    token = gen_token()
                    data.setdefault("api_tokens",{})[num_co] = token
                    sauver(data)
                    envoyer_srv(conn, {"ok": True, "token": token,
                                       "api_url": f"http://junction.proxy.rlwy.net:{API_PORT}/api"})

                # ── ADMIN ─────────────────────────────────
                elif act == "admin_login":
                    if p.get("code","") == ADMIN_CODE:
                        est_admin = True
                        envoyer_srv(conn, {"ok": True, "msg": "✅ Accès admin accordé."})
                    else:
                        envoyer_srv(conn, {"ok": False, "msg": "Code incorrect."})

                elif act == "admin_stats":
                    if not est_admin: envoyer_srv(conn, {"ok": False, "msg": "Accès refusé."}); continue
                    data = charger()
                    with lock: en_ligne = len(clients)
                    stats = data.get("stats",{})
                    envoyer_srv(conn, {"ok": True, "stats": {
                        "utilisateurs":       len(data["users"]),
                        "en_ligne":           en_ligne,
                        "messages_total":     stats.get("messages_total",0),
                        "fichiers_total":     stats.get("fichiers_total",0),
                        "inscriptions_total": stats.get("inscriptions_total",0),
                        "groupes":            len(data.get("groupes",{})),
                        "bots":               len(data.get("bots",{})),
                        "conversations":      len(data.get("historique",{}))
                    }})

                elif act == "admin_broadcast":
                    if not est_admin: continue
                    msg = p.get("msg","").strip()
                    with lock: tous = list(clients.values())
                    for s in tous:
                        envoyer_srv(s, {"type": "annonce", "msg": msg, "heure": heure()})
                    envoyer_srv(conn, {"ok": True, "msg": f"Envoyé à {len(tous)} utilisateurs."})

                elif act == "admin_users":
                    if not est_admin: continue
                    data = charger()
                    with lock: en_ligne_set = set(clients.keys())
                    users = [{"nom": u["nom"], "numero": u["numero"], "pays": u.get("pays",""),
                              "inscription": u.get("inscription","")[:10],
                              "derniere_connexion": u.get("derniere_connexion","")[:16] if u.get("derniere_connexion") else "—",
                              "statut": u.get("statut","disponible"),
                              "en_ligne": u["numero"] in en_ligne_set}
                             for u in data["users"].values()]
                    envoyer_srv(conn, {"ok": True, "users": users})

                elif act == "admin_kick":
                    if not est_admin: continue
                    cible = p.get("numero","").strip()
                    with lock: s = clients.get(cible)
                    if s:
                        envoyer_srv(s, {"type": "kick", "msg": "Déconnecté par l'admin."})
                        try: s.close()
                        except: pass
                        envoyer_srv(conn, {"ok": True, "msg": "Déconnecté."})
                    else:
                        envoyer_srv(conn, {"ok": False, "msg": "Hors ligne."})

    except: pass
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
    print("╔══════════════════════════════════════════╗")
    print("║  💬  TERMCHAT v4.2 — SERVEUR             ║")
    print("║  by Aboudev Labs 🇨🇮                     ║")
    print("╚══════════════════════════════════════════╝")

    initialiser()

    # Lancer API REST en arrière-plan
    threading.Thread(target=demarrer_api, daemon=True).start()

    # Serveur TCP principal
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", PORT))
    srv.listen(200)
    print(f"✅ TCP  : port {PORT}")
    print(f"🌐 API  : port {API_PORT}")
    print(f"📦 GitHub : {GITHUB_REPO}")

    def quitter(sig, frame):
        print("\n🔌 Arrêt..."); srv.close(); sys.exit(0)
    signal.signal(signal.SIGINT, quitter)
    signal.signal(signal.SIGTERM, quitter)

    while True:
        try:
            conn, addr = srv.accept()
            threading.Thread(target=gerer_client, args=(conn, addr), daemon=True).start()
        except: break

if __name__ == "__main__":
    main()
