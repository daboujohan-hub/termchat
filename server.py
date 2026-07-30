from google.cloud.firestore_v1.base_query import FieldFilter
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TermChat v6.0 — Serveur
by Aboudev Labs CI
Base de donnees : Firebase Firestore (donnees permanentes)
"""

import socket, threading, json, os, random, hashlib, re
import datetime, time, base64, signal, sys, ssl, secrets
import bcrypt

# Firebase Admin SDK
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    # from google.cloud.firestore_v1.base_query import FieldFilter  # plus besoin
    FIREBASE_OK = True
except ImportError:
    FIREBASE_OK = False
    print("⚠️  firebase-admin non installe — pip install firebase-admin")

# ══════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════
PORT       = int(os.environ.get("PORT", 9999))
ADMIN_CODE = os.environ.get("ADMIN_CODE", "")
if not ADMIN_CODE or len(ADMIN_CODE) < 12:
    print("❌ ERREUR : la variable d'environnement ADMIN_CODE doit être définie "
          "(minimum 12 caractères, aléatoire). Aucune valeur par défaut n'est autorisée.")
    print("   Exemple : export ADMIN_CODE=$(python3 -c \"import secrets;print(secrets.token_urlsafe(24))\")")
    sys.exit(1)
RE_PSEUDO  = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]{2,19}$")
RE_EMAIL   = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
FIREBASE_CREDS = os.environ.get("FIREBASE_CREDS", "")  # JSON string
CERT_DIR   = os.path.join(os.path.expanduser("~"), ".termchat_tls")
CERT_FILE  = os.path.join(CERT_DIR, "cert.pem")
KEY_FILE   = os.path.join(CERT_DIR, "key.pem")

def preparer_certificat_tls():
    """Charge un certificat existant, ou en genere un auto-signe si absent.
    Un certificat auto-signe chiffre bien le trafic (protection contre
    l'ecoute passive), mais le client doit desactiver la verification de
    la chaine de confiance (pas de CA reconnue) — voir termchat.py."""
    os.makedirs(CERT_DIR, exist_ok=True)
    if os.path.exists(CERT_FILE) and os.path.exists(KEY_FILE):
        return
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        import datetime as dt
        cle = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        nom = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "termchat.local")])
        maintenant = dt.datetime.now(dt.timezone.utc)
        cert = (x509.CertificateBuilder()
                .subject_name(nom).issuer_name(nom).public_key(cle.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(maintenant)
                .not_valid_after(maintenant + dt.timedelta(days=3650))
                .sign(cle, hashes.SHA256()))
        with open(KEY_FILE, "wb") as f:
            f.write(cle.private_bytes(serialization.Encoding.PEM,
                     serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()))
        with open(CERT_FILE, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        print("✅ Certificat TLS auto-signe genere.")
    except Exception as e:
        print(f"⚠️  Impossible de generer le certificat TLS: {e}")

PAYS = {
    "1": ("Cote d'Ivoire", "+225"),
    "2": ("Senegal",       "+221"),
    "3": ("Guinee",        "+224"),
    "4": ("Burkina Faso",  "+226"),
    "5": ("Ghana",         "+233"),
}
STATUTS = ["disponible", "occupe", "ne_pas_deranger", "absent"]

# ══════════════════════════════════════════════════════════
#  FIREBASE FIRESTORE
# ══════════════════════════════════════════════════════════
db = None

def init_firebase():
    global db
    if not FIREBASE_OK:
        print("⚠️  Firebase non disponible")
        return False
    try:
        if FIREBASE_CREDS:
            try:
                creds_dict = json.loads(FIREBASE_CREDS)
                cred = credentials.Certificate(creds_dict)
            except Exception as e:
                print(f"⚠️  FIREBASE_CREDS invalide: {e}")
                return False
        elif os.path.exists("firebase-credentials.json"):
            cred = credentials.Certificate("firebase-credentials.json")
        else:
            print("⚠️  Pas de credentials Firebase")
            return False
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("✅ Firebase Firestore connecte!")
        return True
    except Exception as e:
        print(f"⚠️  Firebase erreur: {e}")
        return False

# ══════════════════════════════════════════════════════════
#  UTILITAIRES
# ══════════════════════════════════════════════════════════
def hacher(s):    return bcrypt.hashpw(s.encode(), bcrypt.gensalt()).decode()
def verifier_mdp(mdp, hash_stocke):
    """Verifie un mot de passe. Compatible avec les anciens hash sha256
    (comptes crees avant la migration bcrypt) qu'on remigre au vol."""
    if not hash_stocke: return False
    if hash_stocke.startswith("$2b$") or hash_stocke.startswith("$2a$"):
        try: return bcrypt.checkpw(mdp.encode(), hash_stocke.encode())
        except Exception: return False
    # ancien format sha256 (64 caracteres hexa)
    return hash_stocke == hashlib.sha256(mdp.encode()).hexdigest()
def horodatage(): return datetime.datetime.now().isoformat()
def heure():      return datetime.datetime.now().strftime("%H:%M")

def est_premium_actif(user):
    """True si le compte a un premium actif et non expire (ou a vie)."""
    if not user or not user.get("premium"): return False
    exp = user.get("premium_expire")
    if exp is None and user.get("premium_type") == "fondateur": return True
    if not exp: return False
    try: return datetime.datetime.fromisoformat(exp) > datetime.datetime.now()
    except Exception: return False

def gen_numero(prefixe):
    if db:
        try:
            users = db.collection("users").where(filter=FieldFilter("prefixe", "==", prefixe)).stream()
            nums  = {u.to_dict().get("numero","") for u in users}
        except Exception:
            nums = set()
    else:
        nums = set()
    while True:
        n = prefixe + str(random.randint(1000000000, 9999999999))
        if n not in nums:
            return n



# ══════════════════════════════════════════════════════════
#  OPÉRATIONS FIRESTORE
# ══════════════════════════════════════════════════════════
def fs_get_user_by_numero(numero):
    if not db: return None, None
    try:
        docs = db.collection("users").where(filter=FieldFilter("numero", "==", numero)).limit(1).stream()
        for doc in docs:
            return doc.id, doc.to_dict()
        return None, None
    except Exception as e:
        print(f"Firestore erreur: {e}"); return None, None

def fs_get_user_by_nom(nom):
    if not db: return []
    try:
        docs = db.collection("users").where(filter=FieldFilter("nom_lower", "==", nom.lower())).stream()
        return [(doc.id, doc.to_dict()) for doc in docs]
    except Exception as e:
        print(f"Firestore erreur: {e}"); return []

def fs_get_user_by_pseudo(pseudo):
    if not db: return None, None
    try:
        docs = db.collection("users").where(filter=FieldFilter("pseudo_lower", "==", pseudo.lower().lstrip("@"))).limit(1).stream()
        for doc in docs:
            return doc.id, doc.to_dict()
        return None, None
    except Exception as e:
        print(f"Firestore erreur: {e}"); return None, None

def fs_get_user_by_email(email):
    if not db: return None, None
    try:
        docs = db.collection("users").where(filter=FieldFilter("email_lower", "==", email.lower())).limit(1).stream()
        for doc in docs:
            return doc.id, doc.to_dict()
        return None, None
    except Exception as e:
        print(f"Firestore erreur: {e}"); return None, None

def fs_save_user(uid, data):
    if not db: return
    try: db.collection("users").document(uid).set(data)
    except Exception as e: print(f"Firestore erreur: {e}")

def fs_update_user(uid, fields):
    if not db: return
    try: db.collection("users").document(uid).update(fields)
    except Exception as e: print(f"Firestore erreur: {e}")

def fs_delete_user(uid):
    if not db: return
    try: db.collection("users").document(uid).delete()
    except Exception as e: print(f"Firestore erreur: {e}")

def fs_save_feedback(numero, nom, texte, prioritaire=False):
    if not db: return
    try:
        fid = f"fb_{int(time.time())}_{random.randint(1000,9999)}"
        db.collection("feedback").document(fid).set({
            "numero": numero, "nom": nom, "texte": texte,
            "heure": horodatage(), "lu": False, "prioritaire": prioritaire
        })
    except Exception as e: print(f"Firestore erreur: {e}")

def fs_save_paiement_attente(numero, nom, code_transaction, montant):
    if not db: return None
    try:
        pid = f"pay_{int(time.time())}_{random.randint(1000,9999)}"
        db.collection("paiements_attente").document(pid).set({
            "numero": numero, "nom": nom, "code_transaction": code_transaction,
            "montant": montant, "heure": horodatage(), "statut": "attente"
        })
        return pid
    except Exception as e:
        print(f"Firestore erreur: {e}"); return None

def fs_get_paiements_attente():
    if not db: return []
    try:
        docs = db.collection("paiements_attente")\
                  .where(filter=FieldFilter("statut", "==", "attente"))\
                  .order_by("heure").stream()
        return [{**d.to_dict(), "id": d.id} for d in docs]
    except Exception as e:
        print(f"Firestore erreur: {e}"); return []

def fs_update_paiement(pid, statut):
    if not db: return
    try:
        db.collection("paiements_attente").document(pid).update({"statut": statut})
    except Exception as e:
        print(f"Firestore erreur: {e}")

def fs_get_feedback(limite=30):
    if not db: return []
    try:
        docs = db.collection("feedback")\
                 .order_by("heure", direction=firestore.Query.DESCENDING)\
                 .limit(limite).stream()
        return [doc.to_dict() for doc in docs]
    except Exception as e:
        print(f"Firestore erreur: {e}"); return []

def fs_save_message(cle_conv, msg):
    if not db: return
    try:
        db.collection("historique").document(cle_conv)\
          .collection("messages").document(msg["id"]).set(msg)
        db.collection("historique").document(cle_conv)\
          .set({"derniere_activite": horodatage(), "participants": cle_conv.split("_")}, merge=True)
    except Exception as e: print(f"Firestore erreur: {e}")

def fs_get_messages(n1, n2, limite=50):
    if not db: return []
    try:
        if not n1 or not n2: return []
        cle = "_".join(sorted([n1, n2]))
        docs = db.collection("historique").document(cle)\
                 .collection("messages")\
                 .order_by("heure", direction=firestore.Query.DESCENDING)\
                 .limit(limite).stream()
        msgs = [doc.to_dict() for doc in docs]
        msgs.reverse()
        now = time.time()
        return [m for m in msgs if not m.get("expire_a") or m["expire_a"] > now]
    except Exception as e:
        print(f"Firestore erreur: {e}"); return []

def fs_marquer_lus(dest, exp):
    if not db: return
    try:
        cle  = "_".join(sorted([dest, exp]))
        docs = db.collection("historique").document(cle)\
                 .collection("messages")\
                 .where(filter=FieldFilter("vers", "==", dest))\
                 .where(filter=FieldFilter("lu", "==", False)).stream()
        batch = db.batch()
        for doc in docs:
            batch.update(doc.reference, {"lu": True})
        batch.commit()
    except Exception as e: print(f"Firestore erreur: {e}")

def fs_mes_contacts(numero):
    """Retourne la liste des numeros avec qui l'utilisateur a deja une conversation."""
    if not db: return []
    try:
        contacts = set()
        convs = db.collection("historique")\
                  .where(filter=FieldFilter("participants", "array_contains", numero)).stream()
        for conv in convs:
            data = conv.to_dict() or {}
            for part in data.get("participants", []):
                if part != numero: contacts.add(part)
        return list(contacts)
    except Exception as e:
        print(f"Firestore erreur: {e}"); return []

def fs_compter_non_lus(numero):
    if not db: return 0
    try:
        count = 0
        convs = db.collection("historique")\
                  .where(filter=FieldFilter("participants", "array_contains", numero)).stream()
        for conv in convs:
            msgs = db.collection("historique").document(conv.id)\
                     .collection("messages")\
                     .where(filter=FieldFilter("vers", "==", numero))\
                     .where(filter=FieldFilter("lu", "==", False)).stream()
            count += sum(1 for _ in msgs)
        return count
    except Exception as e:
        print(f"Firestore erreur: {e}"); return 0

def fs_compter_contacts_distincts(numero):
    """Compte le nombre de conversations distinctes (contacts) d'un utilisateur."""
    if not db: return 0
    try:
        docs = db.collection("historique")\
                  .where(filter=FieldFilter("participants", "array_contains", numero))\
                  .stream()
        return sum(1 for _ in docs)
    except Exception:
        return 0

def fs_get_conversations(numero):
    if not db: return []
    try:
        convs_ref = db.collection("historique")\
                      .where(filter=FieldFilter("participants", "array_contains", numero))\
                      .order_by("derniere_activite", direction=firestore.Query.DESCENDING)\
                      .limit(20).stream()
        result = []
        for conv in convs_ref:
            cid   = conv.id
            parts = cid.split("_")
            autre = next((p for p in parts if p != numero), None)
            if not autre: continue
            _, autre_user = fs_get_user_by_numero(autre)
            if not autre_user: continue
            msgs = db.collection("historique").document(cid)\
                     .collection("messages")\
                     .order_by("heure", direction=firestore.Query.DESCENDING)\
                     .limit(1).stream()
            dernier_msg = ""
            for m in msgs: dernier_msg = m.to_dict().get("texte","")[:40]
            non_lus = 0
            msgs_nl = db.collection("historique").document(cid)\
                        .collection("messages")\
                        .where(filter=FieldFilter("vers", "==", numero))\
                        .where(filter=FieldFilter("lu", "==", False)).stream()
            for _ in msgs_nl: non_lus += 1
            conv_data = conv.to_dict() or {}
            result.append({
                "numero": autre, "nom": autre_user.get("nom","?"),
                "dernier_msg": dernier_msg, "non_lus": non_lus,
                "heure": conv_data.get("derniere_activite","")[:16].replace("T"," ")
            })
        return result
    except Exception as e:
        print(f"Firestore erreur: {e}"); return []

def fs_save_groupe(gid, data):
    if not db or not gid: return
    try: db.collection("groupes").document(gid).set(data, merge=True)
    except Exception as e: print(f"Firestore erreur: {e}")

def fs_get_groupe(gid):
    if not db or not gid: return None
    try:
        doc = db.collection("groupes").document(gid).get()
        return doc.to_dict() if doc.exists else None
    except Exception as e:
        print(f"Firestore erreur: {e}"); return None

def fs_mes_groupes(numero):
    if not db: return []
    try:
        docs = db.collection("groupes")\
                 .where(filter=FieldFilter("membres", "array_contains", numero)).stream()
        return [(doc.id, doc.to_dict()) for doc in docs]
    except Exception as e:
        print(f"Firestore erreur: {e}"); return []

def fs_save_msg_groupe(gid, msg):
    if not db or not gid: return
    try:
        db.collection("groupes").document(gid)\
          .collection("messages").add(msg)
        db.collection("groupes").document(gid)\
          .update({"derniere_activite": horodatage()})
    except Exception as e: print(f"Firestore erreur: {e}")

def fs_get_stats():
    if not db: return {}
    try:
        nb_users  = sum(1 for _ in db.collection("users").stream())
        nb_convs  = sum(1 for _ in db.collection("historique").stream())
        nb_groupes= sum(1 for _ in db.collection("groupes").stream())
        return {"utilisateurs": nb_users, "conversations": nb_convs, "groupes": nb_groupes}
    except Exception as e:
        print(f"Firestore erreur: {e}"); return {}

# ══════════════════════════════════════════════════════════
#  FICHIERS LOCAUX (temporaires)
# ══════════════════════════════════════════════════════════
FILES_DIR = os.path.join(os.path.expanduser("~"), ".termchat_files")
os.makedirs(FILES_DIR, exist_ok=True)

# ══════════════════════════════════════════════════════════
#  CLIENTS CONNECTÉS
# ══════════════════════════════════════════════════════════
clients          = {}   # numero -> socket
admins_connectes = set()
lock             = threading.Lock()
TIMEOUT          = 1800

# ── Anti-bruteforce ──────────────────────────────────────────
tentatives_echec = {}   # cle (ex: "login_ip") -> [nb_echecs, timestamp_dernier_echec]
MAX_TENTATIVES   = 5
BLOCAGE_SECONDES = 300  # 5 minutes

def bloque(cle):
    """True si cette cle a depasse le nombre d'echecs autorises recemment."""
    with lock:
        nb, t = tentatives_echec.get(cle, [0, 0])
        if nb >= MAX_TENTATIVES and time.time() - t < BLOCAGE_SECONDES:
            return True
        if nb >= MAX_TENTATIVES:
            tentatives_echec[cle] = [0, 0]  # blocage expire, on reinitialise
        return False

def signaler_echec(cle):
    with lock:
        nb, _ = tentatives_echec.get(cle, [0, 0])
        tentatives_echec[cle] = [nb + 1, time.time()]

def signaler_succes(cle):
    with lock:
        tentatives_echec.pop(cle, None)

def temps_restant(cle):
    with lock:
        nb, t = tentatives_echec.get(cle, [0, 0])
        return max(0, int(BLOCAGE_SECONDES - (time.time() - t)))

# ── Cooldown feedback (anti-spam simple, independant de l'anti-bruteforce) ──
dernier_feedback = {}   # numero -> timestamp du dernier envoi
FEEDBACK_COOLDOWN = 60  # secondes entre deux feedbacks du meme compte
dernier_paiement = {}   # numero -> timestamp de la derniere soumission
PAIEMENT_COOLDOWN = 120  # secondes entre deux soumissions de paiement

envoi_lock = threading.Lock()

def envoyer_srv(sock, paquet):
    try:
        data = (json.dumps(paquet, ensure_ascii=False) + "\n").encode()
        with envoi_lock: sock.sendall(data)
    except Exception: pass

def livrer(numero, paquet):
    with lock: s = clients.get(numero)
    if s: envoyer_srv(s, paquet); return True
    return False

def notifier_statut(numero, en_ligne):
    uid, user = fs_get_user_by_numero(numero)
    if not user: return
    contacts = set(fs_mes_contacts(numero))
    if not contacts: return
    with lock: cibles = list(clients.items())
    for num, sock in cibles:
        if num != numero and num in contacts:
            envoyer_srv(sock, {"type": "statut", "numero": numero,
                               "nom": user.get("nom","?"), "en_ligne": en_ligne})

def _connecter_user(conn, user, uid):
    """Finalise la connexion d'un utilisateur."""
    num_co    = user["numero"]
    est_admin = user.get("est_admin", False)
    non_lus   = fs_compter_non_lus(num_co)

    fs_update_user(uid, {"derniere_connexion": horodatage()})

    with lock:
        clients[num_co] = conn
        if est_admin: admins_connectes.add(num_co)

    envoyer_srv(conn, {
        "ok": True, "nom": user.get("nom","?"), "numero": num_co,
        "pays": user.get("pays",""), "bio": user.get("bio",""),
        "couleur": user.get("couleur","cyan"),
        "statut": user.get("statut","disponible"),
        "est_admin": est_admin, "non_lus": non_lus,
        "a_pin": bool(user.get("pin")),
        "pseudo": user.get("pseudo",""),
        "premium": est_premium_actif(user),
        "premium_type": user.get("premium_type")
    })
    notifier_statut(num_co, True)
    return num_co, est_admin


# ══════════════════════════════════════════════════════════
#  GESTION D'UN CLIENT TCP
# ══════════════════════════════════════════════════════════
def gerer_client(conn, addr):
    num_co    = None
    buf       = ""
    est_admin = False

    try:
        while True:
            conn.settimeout(TIMEOUT)
            try: chunk = conn.recv(8192).decode("utf-8", errors="replace")
            except socket.timeout:
                if num_co: envoyer_srv(conn, {"type":"timeout","msg":"Deconnecte pour inactivite."})
                break
            if not chunk: break
            buf += chunk

            while "\n" in buf:
                ligne, buf = buf.split("\n", 1)
                ligne = ligne.strip()
                if not ligne: continue
                try: p = json.loads(ligne)
                except Exception: continue

                act = p.get("action", "")

                # ─── INSCRIPTION ──────────────────────────
                if act == "inscrire":
                    nom     = p.get("nom","").strip()
                    mdp     = p.get("mdp","").strip()
                    prefixe = p.get("prefixe","+225").strip()
                    couleur = p.get("couleur","cyan")
                    pseudo  = p.get("pseudo","").strip().lstrip("@")
                    email   = p.get("email","").strip()

                    if not nom or len(nom)<2 or len(nom)>20:
                        envoyer_srv(conn, {"ok":False,"msg":"Nom: 2 a 20 caracteres."})
                    elif len(mdp)<4:
                        envoyer_srv(conn, {"ok":False,"msg":"Mot de passe: minimum 4 caracteres."})
                    elif not RE_PSEUDO.match(pseudo):
                        envoyer_srv(conn, {"ok":False,"msg":"Pseudo invalide: 3-20 caracteres, doit commencer par une lettre, lettres/chiffres/underscore uniquement."})
                    elif email and not RE_EMAIL.match(email):
                        envoyer_srv(conn, {"ok":False,"msg":"Format d'email invalide."})
                    elif fs_get_user_by_pseudo(pseudo)[1] is not None:
                        envoyer_srv(conn, {"ok":False,"msg":f"Le pseudo @{pseudo} est deja pris."})
                    elif email and fs_get_user_by_email(email)[1] is not None:
                        envoyer_srv(conn, {"ok":False,"msg":"Cet email est deja associe a un compte."})
                    else:
                        numero = gen_numero(prefixe)
                        pays   = next((v[0] for v in PAYS.values() if v[1]==prefixe), "Inconnu")
                        uid    = f"u_{int(time.time())}_{random.randint(1000,9999)}"
                        user_data = {
                            "nom": nom, "nom_lower": nom.lower(), "numero": numero,
                            "pseudo": pseudo, "pseudo_lower": pseudo.lower(),
                            "email": email, "email_lower": email.lower() if email else None,
                            "mdp": hacher(mdp), "pays": pays, "prefixe": prefixe,
                            "bio": "", "couleur": couleur, "statut": "disponible",
                            "inscription": horodatage(), "derniere_connexion": None,
                            "favoris": [], "bloque": [], "est_admin": False, "pin": None,
                            "cle_publique": p.get("cle_publique") or None,
                            "premium": False, "premium_expire": None,
                            "premium_type": None, "active_par": None
                        }
                        fs_save_user(uid, user_data)
                        envoyer_srv(conn, {"ok":True,"numero":numero,"nom":nom,"pays":pays,"pseudo":pseudo})

                # ─── CONNEXION (numéro) ───────────────────
                elif act == "connecter_numero":
                    ip = addr[0]; cle_bf = f"login_{ip}"
                    if bloque(cle_bf):
                        envoyer_srv(conn, {"ok":False,"msg":f"Trop de tentatives. Reessaie dans {temps_restant(cle_bf)}s."})
                        continue
                    numero = p.get("numero","").strip(); mdp = p.get("mdp","").strip()
                    uid, user = fs_get_user_by_numero(numero)
                    if not user or not verifier_mdp(mdp, user.get("mdp")):
                        signaler_echec(cle_bf)
                        envoyer_srv(conn, {"ok":False,"msg":"Numero ou mot de passe incorrect."})
                    else:
                        signaler_succes(cle_bf)
                        if not user.get("mdp","").startswith(("$2b$","$2a$")):
                            fs_update_user(uid, {"mdp": hacher(mdp)})  # remigration bcrypt au vol
                        num_co, est_admin = _connecter_user(conn, user, uid)

                # ─── CONNEXION (email) ─────────────────────
                elif act == "connecter_email":
                    ip = addr[0]; cle_bf = f"login_{ip}"
                    if bloque(cle_bf):
                        envoyer_srv(conn, {"ok":False,"msg":f"Trop de tentatives. Reessaie dans {temps_restant(cle_bf)}s."})
                        continue
                    email = p.get("email","").strip(); mdp = p.get("mdp","").strip()
                    uid, user = fs_get_user_by_email(email)
                    if not user or not verifier_mdp(mdp, user.get("mdp")):
                        signaler_echec(cle_bf)
                        envoyer_srv(conn, {"ok":False,"msg":"Email ou mot de passe incorrect."})
                    else:
                        signaler_succes(cle_bf)
                        if not user.get("mdp","").startswith(("$2b$","$2a$")):
                            fs_update_user(uid, {"mdp": hacher(mdp)})  # remigration bcrypt au vol
                        num_co, est_admin = _connecter_user(conn, user, uid)

                # ─── DEFINIR PSEUDO (migration anciens comptes) ──
                elif act == "definir_pseudo":
                    if not num_co:
                        envoyer_srv(conn, {"ok":False,"msg":"Non connecte."})
                    else:
                        pseudo = p.get("pseudo","").strip().lstrip("@")
                        if not RE_PSEUDO.match(pseudo):
                            envoyer_srv(conn, {"ok":False,"msg":"Pseudo invalide: 3-20 caracteres, doit commencer par une lettre, lettres/chiffres/underscore uniquement."})
                        elif fs_get_user_by_pseudo(pseudo)[1] is not None:
                            envoyer_srv(conn, {"ok":False,"msg":f"Le pseudo @{pseudo} est deja pris."})
                        else:
                            uid, _ = fs_get_user_by_numero(num_co)
                            if uid:
                                fs_update_user(uid, {"pseudo": pseudo, "pseudo_lower": pseudo.lower()})
                                envoyer_srv(conn, {"ok":True,"pseudo":pseudo,"msg":f"Pseudo @{pseudo} enregistre!"})
                            else:
                                envoyer_srv(conn, {"ok":False,"msg":"Compte introuvable."})

                # ─── DÉCONNEXION ──────────────────────────
                elif act == "deconnecter":
                    break

                # ─── TYPING ───────────────────────────────
                elif act == "typing":
                    if num_co:
                        dest = p.get("dest","").strip()
                        _, user = fs_get_user_by_numero(num_co)
                        if user: livrer(dest, {"type":"typing","de":user.get("nom","?"),"numero":num_co,"actif":p.get("actif",True)})

                # ─── VERIFIER NUMERO / PSEUDO (usage interne uniquement) ──
                elif act == "chercher":
                    if not num_co: envoyer_srv(conn, {"ok":False,"msg":"Non connecte."})
                    else:
                        cle_bf_ch = f"chercher_{num_co}"
                        if bloque(cle_bf_ch):
                            envoyer_srv(conn, {"ok":False,"msg":f"Trop de recherches. Reessaie dans {temps_restant(cle_bf_ch)}s."})
                            continue
                        pseudo = p.get("pseudo","").strip()
                        numero = p.get("numero","").strip()
                        if pseudo:
                            _, trouve = fs_get_user_by_pseudo(pseudo)
                        else:
                            _, trouve = fs_get_user_by_numero(numero)
                        if not trouve:
                            signaler_echec(cle_bf_ch)
                            envoyer_srv(conn, {"ok":False,"msg":"Utilisateur introuvable."})
                        else:
                            signaler_succes(cle_bf_ch)
                            en_ligne = trouve["numero"] in clients
                            envoyer_srv(conn, {"ok":True,"user":{
                                "nom":trouve.get("nom","?"),"numero":trouve["numero"],
                                "pseudo":trouve.get("pseudo",""),
                                "statut":trouve.get("statut","disponible"),
                                "cle_publique":trouve.get("cle_publique"),
                                "en_ligne":en_ligne}})

                # ─── PUBLIER CLE PUBLIQUE (chiffrement E2E automatique) ──
                elif act == "publier_cle_publique":
                    if not num_co:
                        envoyer_srv(conn, {"ok":False,"msg":"Non connecte."})
                    else:
                        cle_pub = p.get("cle_publique","").strip()
                        uid, _ = fs_get_user_by_numero(num_co)
                        if uid and cle_pub:
                            fs_update_user(uid, {"cle_publique": cle_pub})
                        envoyer_srv(conn, {"ok":True})


# ─── CONVERSATIONS ─────────────────────────
                elif act == "mes_conversations":
                    if num_co:
                        convs = fs_get_conversations(num_co)
                        envoyer_srv(conn, {"ok":True,"conversations":convs})

                # ─── MESSAGE ──────────────────────────────
                elif act == "message":
                    if not num_co: envoyer_srv(conn, {"ok":False,"msg":"Non connecte."})
                    else:
                        dest     = p.get("dest","").strip()
                        texte    = p.get("texte","").strip()
                        chiffre  = p.get("chiffre",False)
                        reply_to = p.get("reply_to")
                        expire_s = p.get("expire_secondes")

                        if not texte or not dest:
                            envoyer_srv(conn, {"ok":False,"msg":"Message ou destinataire vide."})
                        else:
                            _, exp_user  = fs_get_user_by_numero(num_co)
                            _, dest_user = fs_get_user_by_numero(dest)
                            if not est_premium_actif(exp_user) and len(texte) > 150:
                                envoyer_srv(conn, {"ok":False,"msg":"Message trop long (max 150 caracteres en gratuit). Passe premium pour debloquer."})
                                continue
                            cle_verif = "_".join(sorted([num_co, dest]))
                            nouveau_contact = db.collection("historique").document(cle_verif).get().exists == False if db else False
                            if not dest_user:
                                envoyer_srv(conn, {"ok":False,"msg":"Destinataire introuvable."})
                            elif num_co in dest_user.get("bloque",[]):
                                envoyer_srv(conn, {"ok":False,"msg":"Tu es bloque par cet utilisateur."})
                            elif nouveau_contact and not est_premium_actif(exp_user) and fs_compter_contacts_distincts(num_co) >= 5:
                                envoyer_srv(conn, {"ok":False,"msg":"Limite de 5 contacts atteinte en gratuit. Passe premium pour debloquer."})
                            else:
                                cle    = "_".join(sorted([num_co, dest]))
                                msg_id = f"{int(time.time())}_{random.randint(1000,9999)}"
                                msg = {
                                    "id":msg_id,"de":num_co,"vers":dest,"texte":texte,
                                    "type":"texte","heure":horodatage(),"lu":False,
                                    "chiffre":chiffre,"reply_to":reply_to
                                }
                                if expire_s:
                                    try:
                                        msg["expire_a"] = time.time()+int(expire_s)
                                    except Exception:
                                        pass
                                fs_save_message(cle, msg)
                                nom_exp = exp_user["nom"] if exp_user and exp_user.get("nom") else "?"
                                livre = livrer(dest, {
                                    "type":"message","de":nom_exp,"numero":num_co,
                                    "texte":texte,"heure":heure(),"chiffre":chiffre,
                                    "reply_to":reply_to,"msg_id":msg_id,
                                    "premium":est_premium_actif(exp_user),
                                    "premium_type":exp_user.get("premium_type") if exp_user else None
                                })
                                envoyer_srv(conn, {"ok":True,"livre":livre,"msg_id":msg_id})
                                if livre: livrer(num_co, {"type":"livre","dest":dest,"msg_id":msg_id})

                # ─── RÉACTION ─────────────────────────────
                elif act == "reaction":
                    if num_co:
                        dest  = p.get("dest","").strip(); msg_id = p.get("msg_id",""); emoji = p.get("emoji","👍")
                        _, exp_user = fs_get_user_by_numero(num_co)
                        nom_de = exp_user.get("nom","?") if exp_user else "?"
                        livrer(dest, {"type":"reaction","de":nom_de,
                                      "numero":num_co,"msg_id":msg_id,"emoji":emoji,"heure":heure()})
                        envoyer_srv(conn, {"ok":True})

                # ─── MARQUER LU ───────────────────────────
                elif act == "marquer_lu":
                    if num_co:
                        avec = p.get("avec","").strip()
                        fs_marquer_lus(num_co, avec)
                        livrer(avec, {"type":"lu","par":num_co})

                # ─── HISTORIQUE ───────────────────────────
                elif act == "historique":
                    if num_co:
                        avec  = p.get("avec","").strip()
                        hist  = fs_get_messages(num_co, avec, p.get("limite",50))
                        _, eu = fs_get_user_by_numero(num_co)
                        _, au = fs_get_user_by_numero(avec)
                        noms  = {}
                        if eu: noms[num_co] = eu.get("nom", num_co)
                        if au: noms[avec]   = au.get("nom", avec)
                        for m in hist: m["nom_de"] = noms.get(m["de"], m["de"])
                        fs_marquer_lus(num_co, avec)
                        livrer(avec, {"type":"lu","par":num_co})
                        envoyer_srv(conn, {"ok":True,"historique":hist})

                elif act == "rechercher_msg":
                    if num_co:
                        mot  = p.get("mot","").strip().lower()
                        avec = p.get("avec","").strip()
                        hist = fs_get_messages(num_co, avec, 200)
                        res  = [m for m in hist if mot in m.get("texte","").lower()][-20:]
                        envoyer_srv(conn, {"ok":True,"resultats":res,"total":len(res)})

                elif act == "effacer_historique":
                    if num_co:
                        avec = p.get("avec","").strip()
                        cle  = "_".join(sorted([num_co, avec]))
                        if db:
                            try:
                                msgs = db.collection("historique").document(cle).collection("messages").stream()
                                batch = db.batch()
                                for m in msgs: batch.delete(m.reference)
                                batch.commit()
                            except Exception as e: print(f"Firestore erreur: {e}")
                        envoyer_srv(conn, {"ok":True,"msg":"Historique efface."})

                # ─── STATUT ───────────────────────────────
                elif act == "changer_statut":
                    if not num_co:
                        envoyer_srv(conn, {"ok":False,"msg":"Non connecte."})
                    else:
                        statut = p.get("statut","disponible")
                        if statut not in STATUTS: statut = "disponible"
                        uid, _ = fs_get_user_by_numero(num_co)
                        if not uid:
                            envoyer_srv(conn, {"ok":False,"msg":"Utilisateur introuvable."})
                        else:
                            fs_update_user(uid, {"statut": statut})
                            with lock: cibles = list(clients.items())
                            _, eu = fs_get_user_by_numero(num_co)
                            for num, sock in cibles:
                                if num != num_co:
                                    envoyer_srv(sock, {"type":"statut_change","numero":num_co,
                                                       "nom":eu.get("nom","?") if eu else "?","statut":statut})
                            envoyer_srv(conn, {"ok":True,"msg":f"Statut: {statut}"})

                # ─── FAVORIS ──────────────────────────────
                elif act == "ajouter_favori":
                    if not num_co:
                        envoyer_srv(conn, {"ok":False,"msg":"Non connecte."})
                    else:
                        cible = p.get("numero","").strip()
                        uid, user = fs_get_user_by_numero(num_co)
                        if not uid:
                            envoyer_srv(conn, {"ok":False,"msg":"Utilisateur introuvable."})
                        else:
                            favoris = user.get("favoris",[])
                            if cible not in favoris: favoris.append(cible)
                            fs_update_user(uid, {"favoris": favoris})
                            envoyer_srv(conn, {"ok":True,"msg":"Ajoute aux favoris!"})

                elif act == "mes_favoris":
                    if num_co:
                        _, user = fs_get_user_by_numero(num_co)
                        favoris = user.get("favoris",[]) if user else []
                        with lock: ens = set(clients.keys())
                        result = []
                        for n in favoris:
                            _, u = fs_get_user_by_numero(n)
                            if u: result.append({"nom":u.get("nom","?"),"numero":n,
                                "statut":u.get("statut","disponible"),"en_ligne":n in ens})
                        envoyer_srv(conn, {"ok":True,"favoris":result})

                # ─── BLOQUER ──────────────────────────────
                elif act == "bloquer":
                    if not num_co:
                        envoyer_srv(conn, {"ok":False,"msg":"Non connecte."})
                    else:
                        cible  = p.get("numero","").strip(); action = p.get("bloquer",True)
                        uid, user = fs_get_user_by_numero(num_co)
                        if not uid:
                            envoyer_srv(conn, {"ok":False,"msg":"Utilisateur introuvable."})
                        else:
                            liste_bloques = user.get("bloque",[])
                            if action and cible not in liste_bloques: liste_bloques.append(cible)
                            elif not action and cible in liste_bloques: liste_bloques.remove(cible)
                            fs_update_user(uid, {"bloque": liste_bloques})
                            envoyer_srv(conn, {"ok":True,"msg":"Bloque." if action else "Debloque."})

                # ─── PROFIL ───────────────────────────────
                elif act == "changer_couleur":
                    if not num_co:
                        envoyer_srv(conn, {"ok":False,"msg":"Non connecte."})
                    else:
                        couleur = p.get("couleur","cyan")
                        uid, _ = fs_get_user_by_numero(num_co)
                        if not uid:
                            envoyer_srv(conn, {"ok":False,"msg":"Utilisateur introuvable."})
                        else:
                            fs_update_user(uid, {"couleur":couleur}); envoyer_srv(conn, {"ok":True,"msg":"Couleur changee!","couleur":couleur})

                elif act == "modifier_bio":
                    if not num_co:
                        envoyer_srv(conn, {"ok":False,"msg":"Non connecte."})
                    else:
                        bio = p.get("bio","").strip()[:150]
                        uid, _ = fs_get_user_by_numero(num_co)
                        if not uid:
                            envoyer_srv(conn, {"ok":False,"msg":"Utilisateur introuvable."})
                        else:
                            fs_update_user(uid, {"bio":bio}); envoyer_srv(conn, {"ok":True,"msg":"Bio mise a jour!"})


                # ─── FEEDBACK (message au developpeur) ────
                elif act == "envoyer_feedback":
                    if not num_co:
                        envoyer_srv(conn, {"ok":False,"msg":"Non connecte."})
                    else:
                        _, user = fs_get_user_by_numero(num_co)
                        prioritaire = user.get("premium_type") in ("annuel","fondateur") if user else False
                        with lock:
                            dernier = dernier_feedback.get(num_co, 0)
                            attente = FEEDBACK_COOLDOWN - (time.time() - dernier)
                        if attente > 0 and not prioritaire:
                            envoyer_srv(conn, {"ok":False,"msg":f"Merci d'attendre {int(attente)}s avant un nouveau feedback."})
                        else:
                            texte = p.get("texte","").strip()[:500]
                            if len(texte) < 3:
                                envoyer_srv(conn, {"ok":False,"msg":"Message trop court."})
                            else:
                                fs_save_feedback(num_co, user.get("nom","?") if user else "?", texte, prioritaire)
                                with lock: dernier_feedback[num_co] = time.time()
                                msg_ok = "Merci! Message transmis en PRIORITE au developpeur." if prioritaire else "Merci! Ton message a bien ete transmis au developpeur."
                                envoyer_srv(conn, {"ok":True,"msg":msg_ok})

                elif act == "changer_mdp":
                    if not num_co: envoyer_srv(conn, {"ok":False,"msg":"Non connecte."})
                    else:
                        ancien = p.get("ancien","").strip(); nouveau = p.get("nouveau","").strip()
                        uid, user = fs_get_user_by_numero(num_co)
                        if len(nouveau)<4: envoyer_srv(conn, {"ok":False,"msg":"Min 4 caracteres."})
                        elif not uid or not verifier_mdp(ancien, user.get("mdp")): envoyer_srv(conn, {"ok":False,"msg":"Ancien mot de passe incorrect."})
                        else: fs_update_user(uid, {"mdp":hacher(nouveau)}); envoyer_srv(conn, {"ok":True,"msg":"Mot de passe change!"})

                elif act == "supprimer_compte":
                    if not num_co: envoyer_srv(conn, {"ok":False,"msg":"Non connecte."})
                    else:
                        mdp = p.get("mdp","").strip()
                        uid, user = fs_get_user_by_numero(num_co)
                        if not uid or not verifier_mdp(mdp, user.get("mdp")): envoyer_srv(conn, {"ok":False,"msg":"Mot de passe incorrect."})
                        else: fs_delete_user(uid); envoyer_srv(conn, {"ok":True,"msg":"Compte supprime."}); num_co = None

                # ─── PIN ──────────────────────────────────
                elif act == "definir_pin":
                    if num_co:
                        pin = p.get("pin","").strip()
                        if len(pin)!=4 or not pin.isdigit(): envoyer_srv(conn, {"ok":False,"msg":"Le PIN doit etre 4 chiffres."})
                        else:
                            uid, _ = fs_get_user_by_numero(num_co)
                            if uid: fs_update_user(uid, {"pin":hacher(pin)}); envoyer_srv(conn, {"ok":True,"msg":"Code PIN active!"})

                elif act == "supprimer_pin":
                    if num_co:
                        uid, _ = fs_get_user_by_numero(num_co)
                        if uid: fs_update_user(uid, {"pin":None}); envoyer_srv(conn, {"ok":True,"msg":"Code PIN desactive."})

                elif act == "verifier_pin":
                    if num_co:
                        cle_bf = f"pin_{num_co}"
                        if bloque(cle_bf):
                            envoyer_srv(conn, {"ok":False,"msg":f"Trop de tentatives. Reessaie dans {temps_restant(cle_bf)}s."})
                            continue
                        pin = p.get("pin","").strip()
                        _, user = fs_get_user_by_numero(num_co)
                        if not user or not user.get("pin"): envoyer_srv(conn, {"ok":True,"msg":"Pas de PIN defini."})
                        elif verifier_mdp(pin, user["pin"]): signaler_succes(cle_bf); envoyer_srv(conn, {"ok":True,"msg":"PIN correct."})
                        else: signaler_echec(cle_bf); envoyer_srv(conn, {"ok":False,"msg":"PIN incorrect."})

                # ─── FICHIER ──────────────────────────────
                elif act == "envoyer_fichier":
                    if not num_co: envoyer_srv(conn, {"ok":False,"msg":"Non connecte."})
                    else:
                        dest=p.get("dest","").strip(); nom_fich=p.get("nom_fichier","fichier")
                        c64=p.get("contenu",""); taille_raw=p.get("taille",0)
                        try:
                            taille = int(taille_raw or 0)
                        except Exception:
                            envoyer_srv(conn, {"ok":False,"msg":"Taille invalide."}); continue
                        _, exp_user  = fs_get_user_by_numero(num_co)
                        _, dest_user = fs_get_user_by_numero(dest)
                        if not est_premium_actif(exp_user):
                            envoyer_srv(conn, {"ok":False,"msg":"Envoi de fichiers reserve au premium. Passe premium pour debloquer."})
                        elif taille>50*1024*1024: envoyer_srv(conn, {"ok":False,"msg":"Max 50 MB."})
                        elif not dest_user: envoyer_srv(conn, {"ok":False,"msg":"Destinataire introuvable."})
                        else:
                            safe   = "".join(c for c in nom_fich if c.isalnum() or c in "._-") or "fichier"
                            chemin = os.path.join(FILES_DIR, f"{int(time.time())}_{safe}")
                            try:
                                with open(chemin,"wb") as f:
                                    f.write(base64.b64decode(c64))
                                cle    = "_".join(sorted([num_co, dest]))
                                msg_id = f"{int(time.time())}_{random.randint(1000,9999)}"
                                # On ne stocke pas le contenu base64 (trop volumineux pour Firestore),
                                # seulement la reference au fichier, pour que l'historique fonctionne.
                                msg = {
                                    "id":msg_id,"de":num_co,"vers":dest,
                                    "texte":nom_fich,"nom_fichier":safe,
                                    "type":"fichier","heure":horodatage(),"lu":False,
                                    "chiffre":False,"taille":taille
                                }
                                fs_save_message(cle, msg)
                                nom_exp = exp_user.get("nom","?") if exp_user else "?"
                                livre = livrer(dest, {"type":"fichier","de":nom_exp,
                                    "numero":num_co,"nom_fichier":nom_fich,"contenu":c64,"taille":taille,"heure":heure(),"msg_id":msg_id})
                                envoyer_srv(conn, {"ok":True,"livre":livre,"msg_id":msg_id,"msg":f"'{nom_fich}' envoye."})
                            except Exception as e: envoyer_srv(conn, {"ok":False,"msg":f"Erreur: {e}"})

                # ─── VOCAL ────────────────────────────────
                elif act == "envoyer_vocal":
                    if not num_co: envoyer_srv(conn, {"ok":False,"msg":"Non connecte."})
                    else:
                        dest=p.get("dest","").strip(); c64=p.get("contenu","")
                        taille_raw=p.get("taille",0); duree_raw=p.get("duree",0)
                        try:
                            taille = int(taille_raw or 0)
                        except Exception:
                            envoyer_srv(conn, {"ok":False,"msg":"Taille invalide."}); continue
                        try:
                            duree = int(duree_raw or 0)
                        except Exception:
                            duree = 0
                        _, exp_user  = fs_get_user_by_numero(num_co)
                        _, dest_user = fs_get_user_by_numero(dest)
                        if taille>50*1024*1024: envoyer_srv(conn, {"ok":False,"msg":"Max 50 MB."})
                        elif not dest_user: envoyer_srv(conn, {"ok":False,"msg":"Destinataire introuvable."})
                        else:
                            nom_fich=f"vocal_{int(time.time())}.ogg"; chemin=os.path.join(FILES_DIR,nom_fich)
                            try:
                                with open(chemin,"wb") as f: f.write(base64.b64decode(c64))
                                cle    = "_".join(sorted([num_co, dest]))
                                msg_id = f"{int(time.time())}_{random.randint(1000,9999)}"
                                msg = {
                                    "id":msg_id,"de":num_co,"vers":dest,
                                    "texte":nom_fich,"nom_fichier":nom_fich,
                                    "type":"vocal","heure":horodatage(),"lu":False,
                                    "chiffre":False,"taille":taille,"duree":duree
                                }
                                fs_save_message(cle, msg)
                                nom_exp = exp_user.get("nom","?") if exp_user else "?"
                                livre=livrer(dest, {"type":"vocal","de":nom_exp,
                                    "numero":num_co,"nom_fichier":nom_fich,"contenu":c64,"duree":duree,"taille":taille,"heure":heure(),"msg_id":msg_id})
                                envoyer_srv(conn, {"ok":True,"livre":livre,"msg_id":msg_id,"msg":"Vocal envoye!"})
                            except Exception as e: envoyer_srv(conn, {"ok":False,"msg":f"Erreur: {e}"})

                # ─── EN LIGNE ─────────────────────────────
                elif act == "en_ligne":
                    with lock: liste = list(clients.keys())
                    result = []
                    for n in liste:
                        if n == num_co: continue
                        _, u = fs_get_user_by_numero(n)
                        if u: result.append({"numero":n,"nom":u.get("nom","?"),"statut":u.get("statut","disponible")})
                    envoyer_srv(conn, {"ok":True,"users":result})

                # ─── GROUPES ──────────────────────────────
                elif act == "creer_groupe":
                    if num_co:
                        nom_g = p.get("nom","").strip()
                        if nom_g:
                            _, eu = fs_get_user_by_numero(num_co)
                            gid  = f"grp_{int(time.time())}_{random.randint(1000,9999)}"
                            fs_save_groupe(gid, {"nom":nom_g,"createur":num_co,"membres":[num_co],
                                "creation":horodatage(),"epingle":None,"derniere_activite":horodatage()})
                            envoyer_srv(conn, {"ok":True,"id_groupe":gid,"nom":nom_g})

                elif act == "ajouter_groupe":
                    if not num_co:
                        envoyer_srv(conn, {"ok":False,"msg":"Non connecte."})
                    else:
                        gid=p.get("id_groupe","").strip(); cible=p.get("numero","").strip()
                        groupe = fs_get_groupe(gid)
                        _, cible_user = fs_get_user_by_numero(cible)
                        if not groupe: envoyer_srv(conn, {"ok":False,"msg":"Groupe introuvable."})
                        elif groupe["createur"]!=num_co: envoyer_srv(conn, {"ok":False,"msg":"Seul le createur peut ajouter."})
                        elif not cible_user: envoyer_srv(conn, {"ok":False,"msg":"Utilisateur introuvable."})
                        elif cible in groupe.get("membres",[]): envoyer_srv(conn, {"ok":False,"msg":"Deja membre."})
                        else:
                            _, createur_user = fs_get_user_by_numero(groupe["createur"])
                            membres_actuels = groupe.get("membres",[])
                            if not est_premium_actif(createur_user) and len(membres_actuels) >= 5:
                                envoyer_srv(conn, {"ok":False,"msg":"Limite de 5 membres atteinte. Passe premium pour un groupe illimite."})
                                continue
                            membres = membres_actuels+[cible]
                            if db: db.collection("groupes").document(gid).update({"membres":membres})
                            livrer(cible, {"type":"invitation_groupe","groupe":groupe.get("nom","?"),"id_groupe":gid,"heure":heure()})
                            envoyer_srv(conn, {"ok":True,"msg":"Membre ajoute!"})

                elif act == "msg_groupe":
                    if not num_co:
                        envoyer_srv(conn, {"ok":False,"msg":"Non connecte."})
                    else:
                        gid=p.get("id_groupe","").strip(); texte=p.get("texte","").strip(); reply=p.get("reply_to")
                        groupe = fs_get_groupe(gid)
                        _, eu = fs_get_user_by_numero(num_co)
                        if groupe and num_co in groupe.get("membres",[]) and texte and not est_premium_actif(eu) and len(texte) > 150:
                            envoyer_srv(conn, {"ok":False,"msg":"Message trop long (max 150 caracteres en gratuit). Passe premium pour debloquer."})
                        elif groupe and num_co in groupe.get("membres",[]) and texte:
                            msg  = {"de":num_co,"nom":eu.get("nom","?") if eu else "?","texte":texte,"heure":horodatage(),"reply_to":reply}
                            fs_save_msg_groupe(gid, msg)
                            for m in groupe.get("membres",[]):
                                if m!=num_co: livrer(m, {"type":"msg_groupe","groupe":groupe.get("nom","?"),"id_groupe":gid,
                                    "de":eu.get("nom","?") if eu else "?","numero":num_co,"texte":texte,"heure":heure(),"reply_to":reply})
                            envoyer_srv(conn, {"ok":True})
                        else: envoyer_srv(conn, {"ok":False,"msg":"Groupe introuvable ou non membre."})

                elif act == "mes_groupes":
                    if not num_co:
                        envoyer_srv(conn, {"ok":False,"msg":"Non connecte."})
                    else:
                        groupes = fs_mes_groupes(num_co)
                        result  = [{"id":gid,"nom":g.get("nom","?"),"membres":len(g.get("membres",[])),"createur":g.get("createur")==num_co}
                                   for gid,g in groupes]
                        envoyer_srv(conn, {"ok":True,"groupes":result})

                elif act == "epingler_groupe":
                    if not num_co:
                        envoyer_srv(conn, {"ok":False,"msg":"Non connecte."})
                    else:
                        gid=p.get("id_groupe","").strip(); texte=p.get("texte","").strip()
                        groupe = fs_get_groupe(gid)
                        if not groupe: envoyer_srv(conn, {"ok":False,"msg":"Groupe introuvable."})
                        elif groupe["createur"]!=num_co: envoyer_srv(conn, {"ok":False,"msg":"Acces refuse."})
                        else:
                            if db: db.collection("groupes").document(gid).update({"epingle":texte})
                            for m in groupe.get("membres",[]): livrer(m, {"type":"epingle","groupe":groupe.get("nom","?"),"texte":texte,"heure":heure()})
                            envoyer_srv(conn, {"ok":True,"msg":"Message epingle!"})

                # ─── PREMIUM (abonnement) ──────────────────
                elif act == "verifier_mon_abonnement":
                    if not num_co: envoyer_srv(conn, {"ok":False,"msg":"Non connecte."})
                    else:
                        _, user = fs_get_user_by_numero(num_co)
                        actif = est_premium_actif(user)
                        envoyer_srv(conn, {"ok":True,"premium":actif,
                            "premium_expire":user.get("premium_expire") if user else None,
                            "premium_type":user.get("premium_type") if user else None})

                elif act == "soumettre_paiement":
                    if not num_co: envoyer_srv(conn, {"ok":False,"msg":"Non connecte."})
                    else:
                        with lock:
                            dernier_p = dernier_paiement.get(num_co, 0)
                            attente_p = PAIEMENT_COOLDOWN - (time.time() - dernier_p)
                        if attente_p > 0:
                            envoyer_srv(conn, {"ok":False,"msg":f"Merci d'attendre {int(attente_p)}s avant une nouvelle soumission."})
                            continue
                        code_t  = p.get("code_transaction","").strip()
                        montant = p.get("montant","").strip()
                        if not code_t or not montant:
                            envoyer_srv(conn, {"ok":False,"msg":"Code de transaction et montant requis."})
                        else:
                            with lock: dernier_paiement[num_co] = time.time()
                            _, user = fs_get_user_by_numero(num_co)
                            nom = user.get("nom","?") if user else "?"
                            pid = fs_save_paiement_attente(num_co, nom, code_t, montant)
                            if pid:
                                envoyer_srv(conn, {"ok":True,"msg":"Paiement soumis! L'admin va verifier et activer ton premium sous peu."})
                            else:
                                envoyer_srv(conn, {"ok":False,"msg":"Erreur, reessaie plus tard."})

                elif act == "admin_activer_premium":
                    if not est_admin: envoyer_srv(conn, {"ok":False,"msg":"Acces refuse."})
                    else:
                        cible = p.get("numero","").strip()
                        type_abo = p.get("type","mensuel")  # "mensuel", "annuel" ou "fondateur"
                        uid, user = fs_get_user_by_numero(cible)
                        if not uid: envoyer_srv(conn, {"ok":False,"msg":"Utilisateur introuvable."})
                        else:
                            if type_abo == "fondateur":
                                expire = None
                                fs_update_user(uid, {"premium":True,"premium_expire":expire,
                                    "premium_type":type_abo,"active_par":num_co})
                                livrer(cible, {"type":"premium_active","expire":"jamais","premium_type":"fondateur","msg":"Ton compte Fondateur est actif a vie!"})
                                envoyer_srv(conn, {"ok":True,"msg":f"Premium Fondateur (a vie) active pour {cible}."})
                            else:
                                jours = 365 if type_abo == "annuel" else 30
                                expire = (datetime.datetime.now() + datetime.timedelta(days=jours)).isoformat()
                                fs_update_user(uid, {"premium":True,"premium_expire":expire,
                                    "premium_type":type_abo,"active_par":num_co})
                                livrer(cible, {"type":"premium_active","expire":expire,"premium_type":type_abo,"msg":"Ton compte premium est actif!"})
                                envoyer_srv(conn, {"ok":True,"msg":f"Premium ({type_abo}) active pour {cible} jusqu'au {expire[:10]}."})

                elif act == "admin_desactiver_premium":
                    if not est_admin: envoyer_srv(conn, {"ok":False,"msg":"Acces refuse."})
                    else:
                        cible = p.get("numero","").strip()
                        uid, _ = fs_get_user_by_numero(cible)
                        if not uid: envoyer_srv(conn, {"ok":False,"msg":"Utilisateur introuvable."})
                        else:
                            fs_update_user(uid, {"premium":False,"premium_expire":None,"premium_type":None})
                            envoyer_srv(conn, {"ok":True,"msg":f"Premium desactive pour {cible}."})

                # ─── ADMIN ────────────────────────────────
                elif act == "admin_login":
                    ip = addr[0]; cle_bf = f"admin_{ip}"
                    if bloque(cle_bf):
                        envoyer_srv(conn, {"ok":False,"msg":f"Trop de tentatives. Reessaie dans {temps_restant(cle_bf)}s."})
                        continue
                    if secrets.compare_digest(p.get("code",""), ADMIN_CODE):
                        signaler_succes(cle_bf)
                        est_admin = True
                        if num_co:
                            with lock: admins_connectes.add(num_co)
                        envoyer_srv(conn, {"ok":True,"msg":"Acces admin accorde."})
                    else:
                        signaler_echec(cle_bf)
                        envoyer_srv(conn, {"ok":False,"msg":"Code incorrect."})

                elif act == "admin_stats":
                    if not est_admin: envoyer_srv(conn, {"ok":False,"msg":"Acces refuse."})
                    else:
                        stats = fs_get_stats()
                        with lock: stats["en_ligne"] = len(clients)
                        envoyer_srv(conn, {"ok":True,"stats":stats})

                elif act == "admin_feedback":
                    if not est_admin: envoyer_srv(conn, {"ok":False,"msg":"Acces refuse."})
                    else:
                        envoyer_srv(conn, {"ok":True,"feedback":fs_get_feedback()})

                elif act == "admin_users":
                    if not est_admin: envoyer_srv(conn, {"ok":False,"msg":"Acces refuse."})
                    else:
                        if db:
                            try:
                                with lock: ens = set(clients.keys())
                                docs  = db.collection("users").stream()
                                users = []
                                for doc in docs:
                                    u = doc.to_dict() or {}
                                    users.append({"nom":u.get("nom","?"),"numero":u.get("numero","?"),"pays":u.get("pays",""),
                                        "inscription":(u.get("inscription") or "")[:10],
                                        "en_ligne":u.get("numero") in ens})
                                envoyer_srv(conn, {"ok":True,"users":users})
                            except Exception as e: envoyer_srv(conn, {"ok":False,"msg":str(e)})

                elif act == "admin_broadcast":
                    if not est_admin: envoyer_srv(conn, {"ok":False,"msg":"Acces refuse."})
                    else:
                        msg = p.get("msg","").strip()
                        with lock: tous = list(clients.values())
                        for s in tous: envoyer_srv(s, {"type":"annonce","msg":msg,"heure":heure()})
                        envoyer_srv(conn, {"ok":True,"msg":f"Envoye a {len(tous)} utilisateurs."})

                elif act == "admin_kick":
                    if not est_admin: envoyer_srv(conn, {"ok":False,"msg":"Acces refuse."})
                    else:
                        cible = p.get("numero","").strip()
                        with lock: s = clients.get(cible)
                        if s:
                            envoyer_srv(s, {"type":"kick","msg":"Deconnecte par l'administrateur."})
                            try: s.close()
                            except Exception: pass
                            envoyer_srv(conn, {"ok":True,"msg":"Utilisateur deconnecte."})
                        else: envoyer_srv(conn, {"ok":False,"msg":"Utilisateur hors ligne."})

                elif act == "admin_message":
                    if not est_admin: envoyer_srv(conn, {"ok":False,"msg":"Acces refuse."})
                    else:
                        cible = p.get("numero","").strip()
                        texte = p.get("texte","").strip()
                        if not texte:
                            envoyer_srv(conn, {"ok":False,"msg":"Message vide."})
                        else:
                            livre = livrer(cible, {"type":"message_admin","msg":texte,"heure":heure()})
                            if livre:
                                envoyer_srv(conn, {"ok":True,"msg":"Message envoye."})
                            else:
                                envoyer_srv(conn, {"ok":False,"msg":"Utilisateur hors ligne, message non envoye."})

                elif act == "admin_paiements_attente":
                    if not est_admin: envoyer_srv(conn, {"ok":False,"msg":"Acces refuse."})
                    else:
                        paiements = fs_get_paiements_attente()
                        envoyer_srv(conn, {"ok":True,"paiements":paiements})

                elif act == "admin_confirmer_paiement":
                    if not est_admin: envoyer_srv(conn, {"ok":False,"msg":"Acces refuse."})
                    else:
                        pid    = p.get("id","").strip()
                        cible  = p.get("numero","").strip()
                        type_abo = p.get("type","mensuel")
                        uid, user = fs_get_user_by_numero(cible)
                        if not uid:
                            envoyer_srv(conn, {"ok":False,"msg":"Utilisateur introuvable."})
                        else:
                            if type_abo == "fondateur":
                                expire = None
                            else:
                                jours = 365 if type_abo == "annuel" else 30
                                expire = (datetime.datetime.now() + datetime.timedelta(days=jours)).isoformat()
                            fs_update_user(uid, {"premium":True,"premium_expire":expire,
                                "premium_type":type_abo,"active_par":num_co})
                            fs_update_paiement(pid, "confirme")
                            livrer(cible, {"type":"premium_active","expire":expire or "jamais","premium_type":type_abo,"msg":"Paiement confirme, ton premium est actif!"})
                            envoyer_srv(conn, {"ok":True,"msg":f"Paiement confirme, premium ({type_abo}) active pour {cible}."})

                elif act == "admin_rejeter_paiement":
                    if not est_admin: envoyer_srv(conn, {"ok":False,"msg":"Acces refuse."})
                    else:
                        pid = p.get("id","").strip()
                        fs_update_paiement(pid, "rejete")
                        envoyer_srv(conn, {"ok":True,"msg":"Paiement rejete."})

                else: envoyer_srv(conn, {"ok":False,"msg":f"Action inconnue: {act}"})

    except Exception as e:
        import traceback
        print(f"⚠️  Erreur gerer_client: {e}")
        traceback.print_exc()
    finally:
        if num_co:
            with lock: clients.pop(num_co,None); admins_connectes.discard(num_co)
            try: notifier_statut(num_co, False)
            except Exception: pass
        try: conn.close()
        except Exception: pass

# ══════════════════════════════════════════════════════════
#  DÉMARRAGE
# ══════════════════════════════════════════════════════════
def gerer_client_tls(conn, addr, ctx):
    """Fait le handshake TLS dans le thread du client (pas dans la boucle
    d'acceptation principale), avec un timeout court. Ainsi, une connexion
    qui ne complete jamais le handshake (ex: sonde de sante Railway qui se
    contente d'ouvrir/fermer le TCP sans TLS) ne bloque jamais l'acceptation
    des autres clients ni ne fait planter le serveur."""
    try:
        conn.settimeout(8)
        conn = ctx.wrap_socket(conn, server_side=True)
        conn.settimeout(None)
    except Exception as e:
        print(f"⚠️  Poignee de main TLS echouee avec {addr}: {e}")
        try: conn.close()
        except Exception: pass
        return
    gerer_client(conn, addr)

def main():
    print("╔══════════════════════════════════════════╗")
    print("║  💬  TERMCHAT v6.0 — SERVEUR             ║")
    print("║  by Aboudev Labs 🇨🇮                     ║")
    print("╚══════════════════════════════════════════╝")
    init_firebase()
    preparer_certificat_tls()
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", PORT)); srv.listen(200)

    ctx = None
    if os.path.exists(CERT_FILE) and os.path.exists(KEY_FILE):
        try:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(CERT_FILE, KEY_FILE)
            print(f"✅ TCP+TLS port {PORT}")
        except Exception as e:
            ctx = None
            print(f"⚠️  TLS desactive ({e}) — trafic EN CLAIR!")
    else:
        print(f"⚠️  Pas de certificat TLS — trafic EN CLAIR! (port {PORT})")

    def quitter(sig, frame): srv.close(); sys.exit(0)
    signal.signal(signal.SIGINT, quitter); signal.signal(signal.SIGTERM, quitter)
    while True:
        try:
            conn, addr = srv.accept()
            if ctx:
                threading.Thread(target=gerer_client_tls, args=(conn, addr, ctx), daemon=True).start()
            else:
                threading.Thread(target=gerer_client, args=(conn, addr), daemon=True).start()
        except Exception as e:
            print(f"⚠️  Erreur boucle accept (ignoree, on continue): {e}")
            continue

if __name__ == "__main__": main()
