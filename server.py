#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════╗
║         TERMCHAT v4.0  — SERVEUR                        ║
║         Messagerie Mondiale pour Développeurs            ║
║         by Aboudev Labs 🇨🇮                              ║
╚══════════════════════════════════════════════════════════╝

  Déploiement : Render.com (Background Worker)
  Port        : variable d'environnement PORT (défaut 9999)
  Données     : fichier JSON local (.termchat_data/)
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

# ══════════════════════════════════════════════════════════
#  PAYS SUPPORTÉS (Afrique + monde)
# ══════════════════════════════════════════════════════════
PAYS = {
    "1":  ("Côte d'Ivoire", "+225"),
    "2":  ("Sénégal",       "+221"),
    "3":  ("Mali",          "+223"),
    "4":  ("Burkina Faso",  "+226"),
    "5":  ("Guinée",        "+224"),
    "6":  ("Togo",          "+228"),
    "7":  ("Bénin",         "+229"),
    "8":  ("Niger",         "+227"),
    "9":  ("Cameroun",      "+237"),
    "10": ("Congo",         "+242"),
    "11": ("Gabon",         "+241"),
    "12": ("Ghana",         "+233"),
    "13": ("Nigeria",       "+234"),
    "14": ("France",        "+33"),
    "15": ("Belgique",      "+32"),
    "16": ("Canada",        "+1"),
    "17": ("USA",           "+1"),
    "18": ("Maroc",         "+212"),
    "19": ("Algérie",       "+213"),
    "20": ("Tunisie",       "+216"),
}

# ══════════════════════════════════════════════════════════
#  UTILITAIRES
# ══════════════════════════════════════════════════════════
def hacher(mdp):
    return hashlib.sha256(mdp.encode()).hexdigest()

def horodatage():
    return datetime.datetime.now().isoformat()

def heure():
    return datetime.datetime.now().strftime("%H:%M")

def fmt_taille(o):
    if o < 1024:       return f"{o} o"
    elif o < 1024**2:  return f"{o//1024} Ko"
    else:              return f"{o//1024//1024} Mo"

# ══════════════════════════════════════════════════════════
#  BASE DE DONNÉES
# ══════════════════════════════════════════════════════════
def charger():
    """Charge la base de données JSON."""
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(FILES_DIR, exist_ok=True)
    if not os.path.exists(DATA_FILE):
        sauver({
            "users":      {},   # clé = nom_lower
            "historique": {},   # clé = "num1_num2"
            "groupes":    {},   # clé = id_groupe
            "contacts":   {}    # clé = numero proprietaire
        })
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def sauver(data):
    """Sauvegarde la base de données JSON."""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def gen_numero(prefixe):
    """Génère un numéro unique avec le préfixe du pays."""
    data = charger()
    nums = {u["numero"] for u in data["users"].values()}
    while True:
        n = prefixe + str(random.randint(1000000000, 9999999999))
        if n not in nums:
            return n

def sauver_msg(de, vers, texte, type_msg="texte", nom_fich=None):
    """Sauvegarde un message dans l'historique."""
    data = charger()
    cle  = "_".join(sorted([de, vers]))
    hist = data.get("historique", {})
    hist.setdefault(cle, [])
    msg = {
        "de":    de,
        "vers":  vers,
        "texte": texte,
        "type":  type_msg,
        "heure": horodatage(),
        "lu":    False
    }
    if nom_fich:
        msg["fichier"] = nom_fich
    hist[cle].append(msg)
    hist[cle] = hist[cle][-500:]   # garder les 500 derniers messages
    data["historique"] = hist
    sauver(data)

def get_hist(n1, n2, limite=50):
    """Récupère l'historique entre deux utilisateurs."""
    data = charger()
    cle  = "_".join(sorted([n1, n2]))
    return data.get("historique", {}).get(cle, [])[-limite:]

def marquer_lus(n1, n2):
    """Marque les messages d'une conversation comme lus."""
    data = charger()
    cle  = "_".join(sorted([n1, n2]))
    hist = data.get("historique", {}).get(cle, [])
    for msg in hist:
        if msg.get("vers") == n1:
            msg["lu"] = True
    data["historique"][cle] = hist
    sauver(data)

# ══════════════════════════════════════════════════════════
#  GESTION DES CLIENTS CONNECTÉS
# ══════════════════════════════════════════════════════════
clients = {}        # numero → socket
lock    = threading.Lock()

def envoyer_srv(sock, paquet):
    """Envoie un paquet JSON au client."""
    try:
        sock.sendall((json.dumps(paquet, ensure_ascii=False) + "\n").encode())
    except:
        pass

def livrer(numero, paquet):
    """Livre un paquet à un utilisateur connecté."""
    with lock:
        s = clients.get(numero)
    if s:
        envoyer_srv(s, paquet)
        return True
    return False

# ══════════════════════════════════════════════════════════
#  GESTION D'UN CLIENT
# ══════════════════════════════════════════════════════════
def gerer_client(conn, addr):
    """Gère la connexion d'un client."""
    num_co = None
    buf    = ""

    try:
        while True:
            chunk = conn.recv(8192).decode("utf-8", errors="replace")
            if not chunk:
                break
            buf += chunk

            while "\n" in buf:
                ligne, buf = buf.split("\n", 1)
                ligne = ligne.strip()
                if not ligne:
                    continue
                try:
                    p = json.loads(ligne)
                except:
                    continue

                act = p.get("action", "")

                # ── INSCRIPTION ───────────────────────────────
                if act == "inscrire":
                    nom     = p.get("nom", "").strip()
                    mdp     = p.get("mdp", "").strip()
                    prefixe = p.get("prefixe", "+225").strip()

                    if not nom or not mdp:
                        envoyer_srv(conn, {"ok": False, "msg": "Nom et mot de passe requis."}); continue
                    if len(nom) < 2 or len(nom) > 20:
                        envoyer_srv(conn, {"ok": False, "msg": "Nom : 2 à 20 caractères."}); continue
                    if len(mdp) < 4:
                        envoyer_srv(conn, {"ok": False, "msg": "Mot de passe : minimum 4 caractères."}); continue

                    data = charger()
                    for u in data["users"].values():
                        if u["nom"].lower() == nom.lower():
                            envoyer_srv(conn, {"ok": False, "msg": f"Nom '{nom}' déjà utilisé."}); break
                    else:
                        numero = gen_numero(prefixe)
                        pays   = next((v[0] for v in PAYS.values() if v[1] == prefixe), "Inconnu")
                        data["users"][nom.lower()] = {
                            "nom":         nom,
                            "numero":      numero,
                            "mdp":         hacher(mdp),
                            "pays":        pays,
                            "prefixe":     prefixe,
                            "bio":         "",
                            "inscription": horodatage()
                        }
                        sauver(data)
                        envoyer_srv(conn, {"ok": True, "numero": numero, "nom": nom, "pays": pays})

                # ── CONNEXION ─────────────────────────────────
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
                        num_co = user["numero"]
                        with lock:
                            clients[num_co] = conn
                        envoyer_srv(conn, {
                            "ok":     True,
                            "nom":    user["nom"],
                            "numero": num_co,
                            "pays":   user.get("pays", ""),
                            "bio":    user.get("bio", "")
                        })
                        # Notifier les contacts que l'utilisateur est en ligne
                        _notifier_connexion(num_co, True, data)

                # ── DÉCONNEXION ───────────────────────────────
                elif act == "deconnecter":
                    break

                # ── CHERCHER UN UTILISATEUR ───────────────────
                elif act == "chercher":
                    numero = p.get("numero", "").strip()
                    data   = charger()
                    trouve = next((u for u in data["users"].values() if u["numero"] == numero), None)
                    if trouve:
                        en_ligne = numero in clients
                        envoyer_srv(conn, {
                            "ok":   True,
                            "user": {
                                "nom":      trouve["nom"],
                                "numero":   trouve["numero"],
                                "pays":     trouve.get("pays", ""),
                                "bio":      trouve.get("bio", ""),
                                "en_ligne": en_ligne
                            }
                        })
                    else:
                        envoyer_srv(conn, {"ok": False, "msg": "Utilisateur introuvable."})

                # ── ENVOYER UN MESSAGE ────────────────────────
                elif act == "message":
                    if not num_co:
                        envoyer_srv(conn, {"ok": False, "msg": "Non connecté."}); continue

                    dest  = p.get("dest", "").strip()
                    texte = p.get("texte", "").strip()

                    if not texte or not dest:
                        envoyer_srv(conn, {"ok": False, "msg": "Message vide."}); continue

                    data = charger()
                    exp  = next((u for u in data["users"].values() if u["numero"] == num_co), None)
                    if not any(u["numero"] == dest for u in data["users"].values()):
                        envoyer_srv(conn, {"ok": False, "msg": "Destinataire introuvable."}); continue

                    sauver_msg(num_co, dest, texte)
                    livre = livrer(dest, {
                        "type":   "message",
                        "de":     exp["nom"],
                        "numero": num_co,
                        "texte":  texte,
                        "heure":  heure()
                    })
                    envoyer_srv(conn, {"ok": True, "livre": livre})

                # ── ENVOYER UN FICHIER ────────────────────────
                elif act == "envoyer_fichier":
                    if not num_co:
                        envoyer_srv(conn, {"ok": False, "msg": "Non connecté."}); continue

                    dest     = p.get("dest", "").strip()
                    nom_fich = p.get("nom_fichier", "fichier")
                    c64      = p.get("contenu", "")
                    taille   = p.get("taille", 0)

                    if taille > 10 * 1024 * 1024:
                        envoyer_srv(conn, {"ok": False, "msg": "Taille max : 10 MB."}); continue

                    data = charger()
                    exp  = next((u for u in data["users"].values() if u["numero"] == num_co), None)
                    if not any(u["numero"] == dest for u in data["users"].values()):
                        envoyer_srv(conn, {"ok": False, "msg": "Destinataire introuvable."}); continue

                    # Sauvegarder le fichier sur le serveur
                    safe   = "".join(c for c in nom_fich if c.isalnum() or c in "._-")
                    chemin = os.path.join(FILES_DIR, f"{int(time.time())}_{safe}")
                    try:
                        with open(chemin, "wb") as f:
                            f.write(base64.b64decode(c64))
                    except Exception as e:
                        envoyer_srv(conn, {"ok": False, "msg": f"Erreur : {e}"}); continue

                    sauver_msg(num_co, dest, f"[Fichier] {nom_fich}", "fichier", nom_fich)
                    livre = livrer(dest, {
                        "type":         "fichier",
                        "de":           exp["nom"],
                        "numero":       num_co,
                        "nom_fichier":  nom_fich,
                        "contenu":      c64,
                        "taille":       taille,
                        "heure":        heure()
                    })
                    envoyer_srv(conn, {"ok": True, "livre": livre, "msg": f"'{nom_fich}' envoyé."})

                # ── MESSAGE DE GROUPE ─────────────────────────
                elif act == "msg_groupe":
                    if not num_co:
                        envoyer_srv(conn, {"ok": False, "msg": "Non connecté."}); continue

                    id_groupe = p.get("id_groupe", "").strip()
                    texte     = p.get("texte", "").strip()
                    data      = charger()
                    groupe    = data.get("groupes", {}).get(id_groupe)

                    if not groupe:
                        envoyer_srv(conn, {"ok": False, "msg": "Groupe introuvable."}); continue
                    if num_co not in groupe.get("membres", []):
                        envoyer_srv(conn, {"ok": False, "msg": "Tu n'es pas membre de ce groupe."}); continue

                    exp = next((u for u in data["users"].values() if u["numero"] == num_co), None)

                    # Distribuer le message à tous les membres en ligne
                    livres = 0
                    for membre in groupe["membres"]:
                        if membre != num_co:
                            ok = livrer(membre, {
                                "type":       "msg_groupe",
                                "groupe":     groupe["nom"],
                                "id_groupe":  id_groupe,
                                "de":         exp["nom"],
                                "numero":     num_co,
                                "texte":      texte,
                                "heure":      heure()
                            })
                            if ok:
                                livres += 1

                    # Sauvegarder dans l'historique du groupe
                    data["groupes"][id_groupe].setdefault("historique", []).append({
                        "de":    num_co,
                        "nom":   exp["nom"],
                        "texte": texte,
                        "heure": horodatage()
                    })
                    data["groupes"][id_groupe]["historique"] = \
                        data["groupes"][id_groupe]["historique"][-500:]
                    sauver(data)
                    envoyer_srv(conn, {"ok": True, "livres": livres})

                # ── CRÉER UN GROUPE ───────────────────────────
                elif act == "creer_groupe":
                    if not num_co:
                        envoyer_srv(conn, {"ok": False, "msg": "Non connecté."}); continue

                    nom_g = p.get("nom", "").strip()
                    if not nom_g or len(nom_g) < 2:
                        envoyer_srv(conn, {"ok": False, "msg": "Nom du groupe invalide."}); continue

                    data     = charger()
                    id_g     = f"grp_{int(time.time())}_{random.randint(1000,9999)}"
                    data.setdefault("groupes", {})[id_g] = {
                        "nom":        nom_g,
                        "createur":   num_co,
                        "membres":    [num_co],
                        "creation":   horodatage(),
                        "historique": []
                    }
                    sauver(data)
                    envoyer_srv(conn, {"ok": True, "id_groupe": id_g, "nom": nom_g})

                # ── AJOUTER AU GROUPE ─────────────────────────
                elif act == "ajouter_groupe":
                    if not num_co:
                        envoyer_srv(conn, {"ok": False, "msg": "Non connecté."}); continue

                    id_g   = p.get("id_groupe", "").strip()
                    cible  = p.get("numero", "").strip()
                    data   = charger()
                    groupe = data.get("groupes", {}).get(id_g)

                    if not groupe:
                        envoyer_srv(conn, {"ok": False, "msg": "Groupe introuvable."}); continue
                    if groupe["createur"] != num_co:
                        envoyer_srv(conn, {"ok": False, "msg": "Seul le créateur peut ajouter des membres."}); continue
                    if not any(u["numero"] == cible for u in data["users"].values()):
                        envoyer_srv(conn, {"ok": False, "msg": "Utilisateur introuvable."}); continue
                    if cible in groupe["membres"]:
                        envoyer_srv(conn, {"ok": False, "msg": "Déjà membre du groupe."}); continue

                    data["groupes"][id_g]["membres"].append(cible)
                    sauver(data)
                    # Notifier le nouvel membre
                    livrer(cible, {
                        "type":      "invitation_groupe",
                        "groupe":    groupe["nom"],
                        "id_groupe": id_g,
                        "heure":     heure()
                    })
                    envoyer_srv(conn, {"ok": True, "msg": f"Membre ajouté au groupe '{groupe['nom']}'"})

                # ── MES GROUPES ───────────────────────────────
                elif act == "mes_groupes":
                    if not num_co:
                        envoyer_srv(conn, {"ok": False, "msg": "Non connecté."}); continue

                    data    = charger()
                    groupes = [
                        {
                            "id":       gid,
                            "nom":      g["nom"],
                            "membres":  len(g["membres"]),
                            "createur": g["createur"] == num_co
                        }
                        for gid, g in data.get("groupes", {}).items()
                        if num_co in g.get("membres", [])
                    ]
                    envoyer_srv(conn, {"ok": True, "groupes": groupes})

                # ── HISTORIQUE ────────────────────────────────
                elif act == "historique":
                    if not num_co:
                        envoyer_srv(conn, {"ok": False, "msg": "Non connecté."}); continue

                    avec  = p.get("avec", "").strip()
                    hist  = get_hist(num_co, avec, p.get("limite", 50))
                    data  = charger()
                    noms  = {u["numero"]: u["nom"] for u in data["users"].values()}
                    for m in hist:
                        m["nom_de"] = noms.get(m["de"], m["de"])
                    marquer_lus(num_co, avec)
                    envoyer_srv(conn, {"ok": True, "historique": hist})

                # ── MODIFIER BIO ──────────────────────────────
                elif act == "modifier_bio":
                    if not num_co:
                        envoyer_srv(conn, {"ok": False, "msg": "Non connecté."}); continue

                    bio  = p.get("bio", "").strip()[:150]
                    data = charger()
                    for cle, u in data["users"].items():
                        if u["numero"] == num_co:
                            data["users"][cle]["bio"] = bio
                            sauver(data)
                            envoyer_srv(conn, {"ok": True, "msg": "Bio mise à jour !"}); break

                # ── CHANGER MOT DE PASSE ──────────────────────
                elif act == "changer_mdp":
                    if not num_co:
                        envoyer_srv(conn, {"ok": False, "msg": "Non connecté."}); continue

                    ancien  = p.get("ancien", "").strip()
                    nouveau = p.get("nouveau", "").strip()
                    if len(nouveau) < 4:
                        envoyer_srv(conn, {"ok": False, "msg": "Minimum 4 caractères."}); continue

                    data = charger()
                    for cle, u in data["users"].items():
                        if u["numero"] == num_co:
                            if u["mdp"] != hacher(ancien):
                                envoyer_srv(conn, {"ok": False, "msg": "Ancien mot de passe incorrect."}); break
                            data["users"][cle]["mdp"] = hacher(nouveau)
                            sauver(data)
                            envoyer_srv(conn, {"ok": True, "msg": "Mot de passe changé !"}); break

                # ── SUPPRIMER COMPTE ──────────────────────────
                elif act == "supprimer_compte":
                    if not num_co:
                        envoyer_srv(conn, {"ok": False, "msg": "Non connecté."}); continue

                    mdp  = p.get("mdp", "").strip()
                    data = charger()
                    for cle, u in data["users"].items():
                        if u["numero"] == num_co:
                            if u["mdp"] != hacher(mdp):
                                envoyer_srv(conn, {"ok": False, "msg": "Mot de passe incorrect."}); break
                            del data["users"][cle]
                            sauver(data)
                            envoyer_srv(conn, {"ok": True, "msg": "Compte supprimé."})
                            num_co = None; break

                # ── LISTE DES UTILISATEURS EN LIGNE ──────────
                elif act == "en_ligne":
                    with lock:
                        liste = list(clients.keys())
                    data = charger()
                    noms = {u["numero"]: u["nom"] for u in data["users"].values()}
                    users_en_ligne = [
                        {"numero": n, "nom": noms.get(n, "?")}
                        for n in liste if n != num_co
                    ]
                    envoyer_srv(conn, {"ok": True, "users": users_en_ligne})

    except Exception as e:
        pass
    finally:
        if num_co:
            with lock:
                clients.pop(num_co, None)
            # Notifier déconnexion
            try:
                data = charger()
                _notifier_connexion(num_co, False, data)
            except:
                pass
        try:
            conn.close()
        except:
            pass

def _notifier_connexion(numero, en_ligne, data):
    """Notifie les utilisateurs connectés du changement de statut."""
    user = next((u for u in data["users"].values() if u["numero"] == numero), None)
    if not user:
        return
    # Notifier tous les clients connectés (simple broadcast de statut)
    with lock:
        for num, sock in list(clients.items()):
            if num != numero:
                envoyer_srv(sock, {
                    "type":     "statut",
                    "numero":   numero,
                    "nom":      user["nom"],
                    "en_ligne": en_ligne
                })

# ══════════════════════════════════════════════════════════
#  DÉMARRAGE DU SERVEUR
# ══════════════════════════════════════════════════════════
def main():
    charger()   # Initialise la base de données

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", PORT))
    srv.listen(200)

    print(f"╔══════════════════════════════════════════╗")
    print(f"║  💬  TERMCHAT v4.0 — SERVEUR ACTIF      ║")
    print(f"║  by Aboudev Labs 🇨🇮                     ║")
    print(f"╚══════════════════════════════════════════╝")
    print(f"✅ Serveur démarré sur le port {PORT}")
    print(f"📁 Données : {DATA_DIR}")
    print(f"🌍 En attente de connexions...")

    def quitter(sig, frame):
        print("\n🔌 Arrêt du serveur...")
        srv.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, quitter)
    signal.signal(signal.SIGTERM, quitter)

    while True:
        try:
            conn, addr = srv.accept()
            threading.Thread(
                target=gerer_client,
                args=(conn, addr),
                daemon=True
            ).start()
        except:
            break

if __name__ == "__main__":
    main()
