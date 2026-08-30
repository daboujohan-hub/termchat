#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TermChat v6.3 — Serveur (surveillance + modération)
by Aboudev Labs CI
Base de données : Firebase Firestore (données permanentes)

Correctifs sécurité v6.2 :
- 2FA retiré (Resend/Gmail non fiable en production locale)
- Limite de sessions simultanées (3 max) + déconnexion auto ancienne session
- Audit log étendu (échecs login, changement mdp, blocage, suppression)
- Rate limit admin broadcast (5 max / 5 min)
- Protection substitution clé publique E2E
- Admin login durci (comparaison constante + restriction IP)
- Fichiers optionnellement chiffrés au repos (FILE_ENCRYPTION_KEY)
"""

import socket, threading, json, os, hashlib, re, uuid, binascii, ipaddress, random
import datetime, time, base64, signal, sys, ssl, secrets
from pathlib import Path
import bcrypt
import pyotp

# Firebase Admin SDK
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    from google.cloud.firestore_v1.base_query import FieldFilter
    FIREBASE_OK = True
except ImportError:
    FIREBASE_OK = False
    print("⚠️  firebase-admin non installe — pip install firebase-admin")

# ══════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════
PORT       = int(os.environ.get("PORT", 9999))
BIND_HOST  = os.environ.get("BIND_HOST", "0.0.0.0")
ADMIN_CODE = os.environ.get("ADMIN_CODE", "")
PRODUCTION_MODE = os.environ.get("PRODUCTION_MODE", "1") != "0"
REQUIRE_TLS = os.environ.get("REQUIRE_TLS", "1") != "0"
REQUIRE_FIREBASE = os.environ.get("REQUIRE_FIREBASE", "1") != "0"
REQUIRE_EXISTING_TLS_CERT = os.environ.get("REQUIRE_EXISTING_TLS_CERT", "0") != "0"
ALLOW_SELF_SIGNED_DEV_CERT = os.environ.get("ALLOW_SELF_SIGNED_DEV_CERT", "0") == "1"
GEOIP_CHECK_ACTIF = os.environ.get("GEOIP_CHECK_ACTIF", "1") == "1"
ALLOW_LEGACY_SHA256_LOGIN = os.environ.get("ALLOW_LEGACY_SHA256_LOGIN", "0") == "1"
ALLOW_INLINE_MEDIA = os.environ.get("ALLOW_INLINE_MEDIA", "0") == "1"
ALLOW_ACCOUNT_DELETION = os.environ.get("ALLOW_ACCOUNT_DELETION", "0") == "1"
MIN_PASSWORD_LEN = int(os.environ.get("MIN_PASSWORD_LEN", "12"))
MAX_MESSAGE_LEN_FREE = int(os.environ.get("MAX_MESSAGE_LEN_FREE", "150"))
MAX_MESSAGE_LEN_PREMIUM = int(os.environ.get("MAX_MESSAGE_LEN_PREMIUM", "4000"))
EXPIRE_SECONDES_MIN = int(os.environ.get("EXPIRE_SECONDES_MIN", "10"))
EXPIRE_SECONDES_MAX = int(os.environ.get("EXPIRE_SECONDES_MAX", "604800"))  # 7 jours
MAX_NOM_GROUPE_LEN = int(os.environ.get("MAX_NOM_GROUPE_LEN", "100"))
MAX_MEMBRES_GROUPE = int(os.environ.get("MAX_MEMBRES_GROUPE", "500"))
MAX_EPINGLE_LEN = int(os.environ.get("MAX_EPINGLE_LEN", "1000"))
TYPES_ABONNEMENT_VALIDES = ("mensuel", "annuel", "fondateur", "beta")
MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", str(5 * 1024 * 1024)))
MAX_BUFFER_BYTES = int(os.environ.get("MAX_BUFFER_BYTES", str(MAX_UPLOAD_BYTES * 2 + 1024 * 1024)))
MAX_FEEDBACK_LEN = int(os.environ.get("MAX_FEEDBACK_LEN", "500"))
MAX_BIO_LEN = int(os.environ.get("MAX_BIO_LEN", "150"))
MAX_FILES_DIR_BYTES = int(os.environ.get("MAX_FILES_DIR_BYTES", str(256 * 1024 * 1024)))
MAX_FILE_RETENTION_SECONDS = int(os.environ.get("MAX_FILE_RETENTION_SECONDS", str(24 * 3600)))
GLOBAL_ACTIONS_PER_MIN = int(os.environ.get("GLOBAL_ACTIONS_PER_MIN", "180"))
AUTH_ATTEMPTS_PER_5MIN_IP = int(os.environ.get("AUTH_ATTEMPTS_PER_5MIN_IP", "20"))
AUTH_ATTEMPTS_PER_15MIN_ACCOUNT = int(os.environ.get("AUTH_ATTEMPTS_PER_15MIN_ACCOUNT", "10"))
ADMIN_ALLOWED_IPS_RAW = os.environ.get("ADMIN_ALLOWED_IPS", "")
# Clé optionnelle pour chiffrer les fichiers au repos (Fernet url-safe base64, 32 bytes)
# Générer avec : python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
FILE_ENCRYPTION_KEY = os.environ.get("FILE_ENCRYPTION_KEY", "").strip() or None

if not ADMIN_CODE or len(ADMIN_CODE) < 12:
    print("❌ ERREUR : la variable d'environnement ADMIN_CODE doit être définie "
          "(minimum 12 caractères, aléatoire). Aucune valeur par défaut n'est autorisée.")
    print('   Exemple : export ADMIN_CODE=$(python3 -c "import secrets;print(secrets.token_urlsafe(24))")')
    sys.exit(1)
RE_PSEUDO  = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]{2,19}$")
RE_EMAIL   = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
FIREBASE_CREDS = os.environ.get("FIREBASE_CREDS", "")  # JSON string
CERT_DIR   = os.path.join(os.path.expanduser("~"), ".termchat_tls")
CERT_FILE  = os.environ.get("TLS_CERT_FILE", os.path.join(CERT_DIR, "cert.pem"))
KEY_FILE   = os.environ.get("TLS_KEY_FILE", os.path.join(CERT_DIR, "key.pem"))

def preparer_certificat_tls():
    """Prépare TLS.
    En mode production, on exige un certificat existant fourni par l'opérateur.
    L'auto-signé n'est autorisé qu'en mode développement local explicite.
    """
    os.makedirs(CERT_DIR, exist_ok=True)

    # Si un certificat fixe est fourni via variables d'environnement, l'utiliser en priorite
    cert_b64 = os.environ.get("CERT_B64", "")
    key_b64 = os.environ.get("KEY_B64", "")
    if cert_b64 and key_b64:
        try:
            with open(CERT_FILE, "wb") as f:
                f.write(base64.b64decode(cert_b64))
            with open(KEY_FILE, "wb") as f:
                f.write(base64.b64decode(key_b64))
            os.chmod(KEY_FILE, 0o600)
            print("Certificat fixe charge depuis CERT_B64/KEY_B64.")
            return True
        except Exception as e:
            print(f"Erreur chargement certificat fixe: {e}")

    if os.path.exists(CERT_FILE) and os.path.exists(KEY_FILE):
        return True
    if REQUIRE_EXISTING_TLS_CERT or PRODUCTION_MODE:
        return False

    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        import datetime as dt
        cle = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        nom = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
        maintenant = dt.datetime.now(dt.timezone.utc)
        cert = (x509.CertificateBuilder()
                .subject_name(nom).issuer_name(nom).public_key(cle.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(maintenant)
                .not_valid_after(maintenant + dt.timedelta(days=30))
                .sign(cle, hashes.SHA256()))
        with open(KEY_FILE, "wb") as f:
            f.write(cle.private_bytes(serialization.Encoding.PEM,
                     serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()))
        os.chmod(KEY_FILE, 0o600)
        with open(CERT_FILE, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        os.chmod(CERT_FILE, 0o600)
        print("✅ Certificat TLS de développement auto-signé généré.")
        return True
    except Exception as e:
        print(f"⚠️  Impossible de générer le certificat TLS: {e}")
        return False

PAYS = {
    "1": ("Cote d'Ivoire", "+225"),
    "2": ("Senegal",       "+221"),
    "3": ("Guinee",        "+224"),
    "4": ("Burkina Faso",  "+226"),
    "5": ("Ghana",         "+233"),
    "6": ("Mali",          "+223"),
    "7": ("Togo",          "+228"),
    "8": ("Benin",         "+229"),
    "9": ("Niger",         "+227"),
    "10": ("Nigeria",      "+234"),
    "11": ("Cameroun",     "+237"),
}

# Correspondance code pays ISO (retourne par la geolocalisation IP) -> prefixe telephonique
ISO_VERS_PREFIXE = {
    "CI": "+225", "SN": "+221", "GN": "+224", "BF": "+226", "GH": "+233",
    "ML": "+223", "TG": "+228", "BJ": "+229", "NE": "+227", "NG": "+234", "CM": "+237",
}

def verifier_pays_ip(ip, prefixe_declare):
    """Retourne (ok, pays_detecte). Verifie via api.country.is (HTTPS, gratuit,
    sans cle) que le pays detecte par IP correspond au pays declare a
    l'inscription (deduit du prefixe telephonique). Simple controle
    anti-fraude a l'inscription, ne suit pas la position d'un utilisateur.
    Actif par defaut ; mettre GEOIP_CHECK_ACTIF=0 pour le desactiver."""
    if not GEOIP_CHECK_ACTIF:
        return True, None
    try:
        import urllib.request, json as _json
        with urllib.request.urlopen(f"https://api.country.is/{ip}", timeout=3) as resp:
            data = _json.loads(resp.read().decode())
        code_iso = data.get("country", "")
        if not code_iso:
            return True, None
        prefixe_detecte = ISO_VERS_PREFIXE.get(code_iso)
        if prefixe_detecte is None:
            return True, code_iso
        return (prefixe_detecte == prefixe_declare), code_iso
    except Exception:
        return True, None
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
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("✅ Firebase Firestore connecté !")
        return True
    except Exception as e:
        print(f"⚠️  Firebase erreur: {e}")
        return False

# ══════════════════════════════════════════════════════════
#  UTILITAIRES

# ══════════════════════════════════════════════════════════
#  UTILITAIRES
# ══════════════════════════════════════════════════════════
def hacher(s):
    return bcrypt.hashpw(s.encode(), bcrypt.gensalt()).decode()

def gen_id(prefix):
    return f"{prefix}{uuid.uuid4().hex}"

def nettoyer_nom_fichier(nom_fichier):
    brut = (nom_fichier or "fichier").strip()
    safe = "".join(c for c in brut if c.isalnum() or c in "._-") or "fichier"
    return safe[:120]

def decoder_base64_strict(c64, taille_annoncee=0, max_bytes=MAX_UPLOAD_BYTES):
    if not isinstance(c64, str) or not c64:
        raise ValueError("Contenu manquant.")
    try:
        data = base64.b64decode(c64, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError("Base64 invalide.")
    taille_reelle = len(data)
    if taille_reelle <= 0:
        raise ValueError("Contenu vide.")
    if taille_reelle > max_bytes:
        raise ValueError(f"Fichier trop volumineux (max {max_bytes // (1024*1024)} MB).")
    if taille_annoncee:
        try:
            annoncee = int(taille_annoncee)
        except Exception:
            raise ValueError("Taille invalide.")
        if annoncee != taille_reelle:
            raise ValueError("La taille annoncée ne correspond pas au contenu reçu.")
    return data, taille_reelle

def _fernet_fichiers():
    """Retourne un Fernet si FILE_ENCRYPTION_KEY est définie, sinon None."""
    if not FILE_ENCRYPTION_KEY:
        return None
    try:
        from cryptography.fernet import Fernet
        return Fernet(FILE_ENCRYPTION_KEY.encode() if isinstance(FILE_ENCRYPTION_KEY, str) else FILE_ENCRYPTION_KEY)
    except Exception as e:
        print(f"⚠️  FILE_ENCRYPTION_KEY invalide ({e}) — fichiers stockés en clair.")
        return None

def totp_generer_secret():
    """Genere un nouveau secret TOTP (base32, compatible Google Authenticator)."""
    return pyotp.random_base32()

def totp_chiffrer_secret(secret: str):
    """Chiffre un secret TOTP avant stockage. Reutilise FILE_ENCRYPTION_KEY
    (meme mecanisme que les fichiers proteges). Si aucune cle n'est configuree,
    stocke en clair avec un avertissement (comme ecrire_fichier_protege)."""
    fernet = _fernet_fichiers()
    if fernet:
        return fernet.encrypt(secret.encode()).decode()
    print("⚠️  FILE_ENCRYPTION_KEY non definie — secret TOTP stocke en clair.")
    return secret

def totp_dechiffrer_secret(secret_stocke: str):
    """Dechiffre un secret TOTP stocke. Retourne tel quel si pas chiffre."""
    fernet = _fernet_fichiers()
    if fernet:
        try:
            return fernet.decrypt(secret_stocke.encode()).decode()
        except Exception:
            return secret_stocke
    return secret_stocke

def totp_verifier_code(secret: str, code: str):
    """Verifie un code TOTP a 6 chiffres (fenetre de tolerance de 1 pas = 30s)."""
    if not secret or not code:
        return False
    try:
        return pyotp.TOTP(secret).verify(code.strip(), valid_window=1)
    except Exception:
        return False

def totp_generer_codes_recuperation(n=8):
    """Genere n codes de recuperation a usage unique (format XXXX-XXXX)."""
    codes = []
    for _ in range(n):
        brut = secrets.token_hex(4).upper()
        codes.append(f"{brut[:4]}-{brut[4:]}")
    return codes

def totp_hacher_code_recup(code: str):
    return hashlib.sha256(code.strip().upper().encode()).hexdigest()

def chiffrer_champ_repos(valeur):
    """Chiffre une valeur texte avant stockage Firestore (reutilise FILE_ENCRYPTION_KEY).
    Si aucune cle n'est configuree, retourne la valeur telle quelle (comportement
    identique a l'existant, pas de regression)."""
    if not valeur:
        return valeur
    fernet = _fernet_fichiers()
    if not fernet:
        return valeur
    try:
        return fernet.encrypt(valeur.encode()).decode()
    except Exception:
        return valeur

def dechiffrer_champ_repos(valeur):
    """Dechiffre une valeur chiffree par chiffrer_champ_repos."""
    if not valeur:
        return valeur
    fernet = _fernet_fichiers()
    if not fernet:
        return valeur
    try:
        return fernet.decrypt(valeur.encode()).decode()
    except Exception:
        return valeur

def ecrire_fichier_protege(chemin, data: bytes):
    """Écrit un fichier, chiffré au repos si une clé est configurée."""
    fernet = _fernet_fichiers()
    payload = fernet.encrypt(data) if fernet else data
    with open(chemin, "wb") as f:
        f.write(payload)
    try:
        os.chmod(chemin, 0o600)
    except Exception:
        pass

def lire_fichier_protege(chemin) -> bytes:
    """Lit un fichier, le déchiffre si nécessaire."""
    with open(chemin, "rb") as f:
        raw = f.read()
    fernet = _fernet_fichiers()
    if fernet:
        try:
            return fernet.decrypt(raw)
        except Exception:
            # Peut être un ancien fichier en clair
            return raw
    return raw

def taille_stockage_local():
    total = 0
    for p in Path(FILES_DIR).glob("*"):
        try:
            if p.is_file():
                total += p.stat().st_size
        except OSError:
            continue
    return total

def nettoyer_fichiers_temporaires():
    maintenant = time.time()
    for p in Path(FILES_DIR).glob("*"):
        try:
            if p.is_file() and maintenant - p.stat().st_mtime > MAX_FILE_RETENTION_SECONDS:
                p.unlink(missing_ok=True)
        except OSError:
            continue

def verifier_budget_stockage():
    nettoyer_fichiers_temporaires()
    if taille_stockage_local() > MAX_FILES_DIR_BYTES:
        raise ValueError("Stockage temporaire saturé. Réessaie plus tard.")
def verifier_mdp(mdp, hash_stocke):
    """Vérifie un mot de passe.
    Le format SHA-256 historique est désactivé par défaut en production.
    """
    if not hash_stocke:
        return False
    if hash_stocke.startswith(("$2b$", "$2a$")):
        try:
            return bcrypt.checkpw(mdp.encode(), hash_stocke.encode())
        except Exception:
            return False
    if not ALLOW_LEGACY_SHA256_LOGIN:
        return False
    return hash_stocke == hashlib.sha256(mdp.encode()).hexdigest()

def mot_de_passe_est_fort(mdp):
    if len(mdp) < MIN_PASSWORD_LEN:
        return False
    classes = [
        any(c.islower() for c in mdp),
        any(c.isupper() for c in mdp),
        any(c.isdigit() for c in mdp),
        any(not c.isalnum() for c in mdp),
    ]
    return sum(classes) >= 3

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
        n = prefixe + str(secrets.randbelow(9000000000) + 1000000000)
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

def fs_get_user(uid):
    if not db or not uid: return None
    try:
        doc = db.collection("users").document(uid).get()
        return doc.to_dict() if doc.exists else None
    except Exception as e:
        print(f"Firestore erreur: {e}"); return None

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

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
RESEND_FROM = os.environ.get("RESEND_FROM", "onboarding@resend.dev")

def envoyer_email_resend(destinataire, sujet, corps_html):
    """Envoie un email via l'API Resend (urllib, pas de dependance supplementaire)."""
    if not RESEND_API_KEY:
        print("RESEND_API_KEY non configuree, email non envoye.")
        return False
    try:
        import urllib.request
        payload = json.dumps({
            "from": RESEND_FROM,
            "to": [destinataire],
            "subject": sujet,
            "html": corps_html
        }).encode()
        req = urllib.request.Request(
            "https://api.resend.com/emails",
            data=payload,
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            return resp.status in (200, 201)
    except Exception as e:
        print(f"Erreur envoi email Resend: {e}")
        return False

def fs_log_audit_complet(numero, action, details="", cible="", ip_client=""):
    """Journal d'audit étendu pour toutes les actions sensibles."""
    if not db: return
    try:
        aid = f"audit_{int(time.time())}_{secrets.token_hex(4)}"
        db.collection("audit_log").document(aid).set({
            "numero": numero, "action": action, "cible": cible,
            "details": details, "heure": horodatage(),
            "ip": ip_client or "inconnu"
        })
    except Exception as e:
        print(f"Firestore erreur (audit complet): {e}")

def fs_log_audit(admin_numero, action, cible="", details=""):
    """Enregistre une action admin dans le journal d'audit (jamais modifiable/supprimable via l'app)."""
    if not db: return
    try:
        aid = f"audit_{int(time.time())}_{random.randint(1000,9999)}"
        db.collection("audit_log").document(aid).set({
            "admin": admin_numero, "action": action, "cible": cible,
            "details": details, "heure": horodatage()
        })
    except Exception as e:
        print(f"Firestore erreur (audit): {e}")

def fs_save_feedback(numero, nom, texte, prioritaire=False):
    if not db: return
    try:
        fid = gen_id("fb_")
        db.collection("feedback").document(fid).set({
            "numero": numero, "nom": nom, "texte": texte,
            "heure": horodatage(), "lu": False, "prioritaire": prioritaire
        })
    except Exception as e: print(f"Firestore erreur: {e}")

TARIFS_PREMIUM = {"500": "mensuel", "8000": "annuel", "200": "fondateur"}

def fs_verifier_paiement_sms(code_transaction, montant):
    """Cherche un paiement confirme automatiquement par SMS (collection
    paiements_confirmes_sms, alimentee par surveiller_paiements_sms.py).
    Retourne le type d'abonnement si trouve, valide et non deja utilise, sinon None."""
    if not db: return None
    try:
        doc_ref = db.collection("paiements_confirmes_sms").document(code_transaction)
        doc = doc_ref.get()
        if not doc.exists: return None
        data = doc.to_dict()
        if data.get("statut") != "non_utilise": return None
        montant_recu = str(data.get("montant", ""))
        type_abo = TARIFS_PREMIUM.get(montant_recu)
        if not type_abo: return None
        if str(montant).strip() != montant_recu: return None
        doc_ref.update({"statut": "utilise", "utilise_le": horodatage()})
        return type_abo
    except Exception as e:
        print(f"Firestore erreur verif paiement SMS: {e}"); return None

def fs_save_paiement_attente(numero, nom, code_transaction, montant):
    if not db: return None
    try:
        pid = gen_id("pay_")
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

def fs_get_paiement(pid):
    if not db: return None
    try:
        doc = db.collection("paiements_attente").document(pid).get()
        if not doc.exists: return None
        return {**doc.to_dict(), "id": doc.id}
    except Exception as e:
        print(f"Firestore erreur: {e}"); return None

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
        fernet = _fernet_fichiers()
        if fernet and msg.get("texte"):
            msg = dict(msg)
            msg["texte"] = fernet.encrypt(msg["texte"].encode()).decode()
            msg["texte_chiffree"] = True
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
        for m in msgs:
            if m.get("texte_chiffree"):
                m["texte"] = dechiffrer_champ_repos(m.get("texte",""))
        msgs.reverse()
        now = time.time()
        return [m for m in msgs if not m.get("expire_a") or m["expire_a"] > now]
    except Exception as e:
        print(f"Firestore erreur: {e}"); return []

def fs_message_existe(num_co, dest, msg_id):
    if not db or not msg_id: return False
    try:
        cle = "_".join(sorted([num_co, dest]))
        doc = db.collection("historique").document(cle)\
                .collection("messages").document(msg_id).get()
        return doc.exists
    except Exception as e:
        print(f"Firestore erreur: {e}"); return False

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
            for m in msgs:
                d = m.to_dict()
                txt = d.get("texte","")
                if d.get("texte_chiffree"):
                    txt = dechiffrer_champ_repos(txt)
                dernier_msg = txt[:40]
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
        fernet = _fernet_fichiers()
        if fernet and msg.get("texte"):
            msg = dict(msg)
            msg["texte"] = fernet.encrypt(msg["texte"].encode()).decode()
            msg["texte_chiffree"] = True
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
try:
    os.chmod(FILES_DIR, 0o700)
except Exception:
    pass

# ══════════════════════════════════════════════════════════
#  CLIENTS CONNECTÉS
# ══════════════════════════════════════════════════════════
clients          = {}   # numero -> socket
sessions_par_user = {}  # numero -> set de sockets (limitation multi-session)
MAX_SESSIONS     = 3
# ── Surveillance connexions ──
connexions_actives = {}  # numero -> {"ip": str, "heure_connexion": str, "pays": str}
# ── Alertes sécurité ──
alertes_securite = []  # [{"heure", "severite", "type", "ip", "details"}]
admins_connectes = set()
connexions_en_attente_totp = {}  # conn -> {"uid": str, "ip": str}
lock             = threading.Lock()
TIMEOUT          = 1800
MAX_CONNEXIONS_SIMULTANEES = 500  # au-dela, nouvelles connexions refusees (protection DoS)
connexions_count = 0
connexions_lock = threading.Lock()
MAX_TAILLE_BUFFER = MAX_BUFFER_BYTES

# ── Anti-bruteforce (persistant via Firestore) ───────────────
tentatives_echec = {}   # cache local: cle -> [nb_echecs, timestamp_dernier_echec]
MAX_TENTATIVES   = 5
BLOCAGE_SECONDES = 300  # 5 minutes

def _fs_cle_bruteforce(cle):
    # Firestore n'aime pas les "/" dans les IDs de document
    return cle.replace("/", "_")

def _fs_charger_bruteforce(cle):
    """Charge l'etat depuis Firestore si absent du cache local (ex: apres redemarrage)."""
    if cle in tentatives_echec or not db:
        return
    try:
        doc = db.collection("rate_limits_bruteforce").document(_fs_cle_bruteforce(cle)).get()
        if doc.exists:
            d = doc.to_dict()
            tentatives_echec[cle] = [d.get("nb", 0), d.get("t", 0)]
    except Exception as e:
        print(f"Firestore erreur (bruteforce load): {e}")

def _fs_sauver_bruteforce(cle):
    if not db:
        return
    try:
        nb, t = tentatives_echec.get(cle, [0, 0])
        db.collection("rate_limits_bruteforce").document(_fs_cle_bruteforce(cle)).set({"nb": nb, "t": t})
    except Exception as e:
        print(f"Firestore erreur (bruteforce save): {e}")

def _fs_effacer_bruteforce(cle):
    if not db:
        return
    try:
        db.collection("rate_limits_bruteforce").document(_fs_cle_bruteforce(cle)).delete()
    except Exception as e:
        print(f"Firestore erreur (bruteforce delete): {e}")

def bloque(cle):
    """True si cette cle a depasse le nombre d'echecs autorises recemment."""
    with lock:
        _fs_charger_bruteforce(cle)
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
    _fs_sauver_bruteforce(cle)

def signaler_succes(cle):
    with lock:
        tentatives_echec.pop(cle, None)
    _fs_effacer_bruteforce(cle)

def temps_restant(cle):
    with lock:
        nb, t = tentatives_echec.get(cle, [0, 0])
        return max(0, int(BLOCAGE_SECONDES - (time.time() - t)))

# ── Cooldown feedback (anti-spam simple, independant de l'anti-bruteforce) ──
dernier_feedback = {}   # numero -> timestamp du dernier envoi
FEEDBACK_COOLDOWN = 60  # secondes entre deux feedbacks du meme compte
dernier_paiement = {}   # numero -> timestamp de la derniere soumission
PAIEMENT_COOLDOWN = 120  # secondes entre deux soumissions de paiement
rate_limits = {}

try:
    ADMIN_ALLOWED_IPS = [ipaddress.ip_network(x.strip(), strict=False) for x in ADMIN_ALLOWED_IPS_RAW.split(",") if x.strip()]
except Exception:
    ADMIN_ALLOWED_IPS = []

def limite_depassee(cle, limite, fenetre_sec):
    maintenant = time.time()
    with lock:
        serie = [t for t in rate_limits.get(cle, []) if maintenant - t < fenetre_sec]
        if len(serie) >= limite:
            rate_limits[cle] = serie
            return True
        serie.append(maintenant)
        rate_limits[cle] = serie
        return False

def ip_autorisee_pour_admin(ip):
    if not ADMIN_ALLOWED_IPS:
        return True
    try:
        ip_obj = ipaddress.ip_address(ip)
        return any(ip_obj in net for net in ADMIN_ALLOWED_IPS)
    except ValueError:
        return False

envoi_lock = threading.Lock()

def envoyer_srv(sock, paquet):
    try:
        data = (json.dumps(paquet, ensure_ascii=False) + "\n").encode()
        with envoi_lock:
            sock.sendall(data)
    except Exception:
        return False
    return True

def livrer(numero, paquet):
    with lock:
        s = clients.get(numero)

    if s:
        envoyer_srv(s, paquet)
        return True

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

# ══════════════════════════════════════════════════════════
#  RBAC — RÔLES ADMIN
# ══════════════════════════════════════════════════════════
ROLES_ADMIN = {"super_admin", "moderator", "payment_admin"}

# None = accès total (super_admin). Sinon: ensemble des actions autorisées.
PERMISSIONS_PAR_ROLE = {
    "super_admin": None,
    "moderator": {
        "admin_stats", "admin_feedback", "admin_users", "admin_broadcast",
        "admin_kick", "admin_message", "admin_signalements", "admin_traiter_signalement",
    },
    "payment_admin": {
        "admin_activer_premium", "admin_desactiver_premium",
        "admin_paiements_attente", "admin_confirmer_paiement", "admin_rejeter_paiement",
    },
}

def a_permission(role, action):
    """Vérifie si un rôle admin a le droit d'exécuter une action donnée."""
    if not role:
        return False
    perms = PERMISSIONS_PAR_ROLE.get(role)
    if perms is None:
        return True  # super_admin : accès total
    return action in perms


def _connecter_user(conn, user, uid, ip_client=""):
    """Finalise la connexion d'un utilisateur avec limite de sessions."""
    num_co    = user["numero"]
    est_admin = user.get("est_admin", False)
    # Migration : anciens comptes admin sans champ "role" -> super_admin
    admin_role = (user.get("role") or "super_admin") if est_admin else None
    non_lus   = fs_compter_non_lus(num_co)

    fs_update_user(uid, {"derniere_connexion": horodatage()})

    with lock:
        # Limiter à MAX_SESSIONS connexions simultanées
        existing = sessions_par_user.get(num_co, set())
        if len(existing) >= MAX_SESSIONS:
            # Déconnecter la plus ancienne (premier socket du set)
            oldest = next(iter(existing))
            try:
                envoyer_srv(oldest, {"type":"kick","msg":"Nouvelle connexion détectée. Déconnexion de l'ancienne session."})
                oldest.close()
            except Exception:
                pass
            existing.discard(oldest)
            clients.pop(num_co, None)
            connexions_actives.pop(num_co, None)
            fs_log_audit_complet(num_co, "session_kick_auto", "Ancienne session déconnectée (limite atteinte)", ip_client=ip_client)
        clients[num_co] = conn
        sessions_par_user.setdefault(num_co, set()).add(conn)
        if est_admin: admins_connectes.add(num_co)
        # Enregistrer pour surveillance
        connexions_actives[num_co] = {
            "ip": ip_client,
            "heure_connexion": horodatage(),
            "pays": user.get("pays", "Inconnu"),
            "nom": user.get("nom", "?"),
            "statut": user.get("statut", "disponible")
        }

    envoyer_srv(conn, {
        "ok": True, "nom": user.get("nom","?"), "numero": num_co,
        "pays": user.get("pays",""), "bio": user.get("bio",""),
        "couleur": user.get("couleur","cyan"),
        "statut": user.get("statut","disponible"),
        "est_admin": est_admin, "non_lus": non_lus,
        "a_pin": bool(user.get("pin")),
        "pseudo": user.get("pseudo",""),
        "premium": est_premium_actif(user),
        "premium_type": user.get("premium_type"),
        "role": admin_role
    })
    notifier_statut(num_co, True)
    return num_co, est_admin, admin_role


# ══════════════════════════════════════════════════════════
#  GESTION D'UN CLIENT TCP
# ══════════════════════════════════════════════════════════
def gerer_client(conn, addr):
    num_co    = None
    buf       = ""
    est_admin = False
    admin_role = None

    with connexions_lock:
        global connexions_count
        connexions_count += 1

    try:
        while True:
            conn.settimeout(TIMEOUT)
            try: chunk = conn.recv(8192).decode("utf-8", errors="replace")
            except socket.timeout:
                if num_co: envoyer_srv(conn, {"type":"timeout","msg":"Deconnecte pour inactivite."})
                break
            if not chunk: break
            if len(buf) + len(chunk) > MAX_TAILLE_BUFFER:
                try: envoyer_srv(conn, {"ok":False,"msg":"Message trop volumineux."})
                except Exception: pass
                break
            buf += chunk

            while "\n" in buf:
                ligne, buf = buf.split("\n", 1)
                ligne = ligne.strip()
                if not ligne: continue
                try: p = json.loads(ligne)
                except Exception: continue

                ip_client = addr[0]
                if not isinstance(p, dict):
                    envoyer_srv(conn, {"ok":False,"msg":"Requête invalide."})
                    continue
                act = p.get("action", "")
                if not act:
                    envoyer_srv(conn, {"ok":False,"msg":"Requête invalide."})
                    continue
                if limite_depassee(f"act_ip:{ip_client}", GLOBAL_ACTIONS_PER_MIN, 60):
                    envoyer_srv(conn, {"ok":False,"msg":"Trop de requêtes. Réessaie plus tard."})
                    continue

                # ─── INSCRIPTION ──────────────────────────
                if act == "inscrire":
                    cle_bf_insc = f"inscrire_{addr[0]}"
                    if bloque(cle_bf_insc):
                        envoyer_srv(conn, {"ok":False,"msg":f"Trop de tentatives d'inscription. Reessaie dans {temps_restant(cle_bf_insc)}s."})
                        continue
                    nom     = p.get("nom","").strip()
                    mdp     = p.get("mdp","").strip()
                    prefixe = p.get("prefixe","+225").strip()
                    couleur = p.get("couleur","cyan")
                    pseudo  = p.get("pseudo","").strip().lstrip("@")
                    email   = p.get("email","").strip().lower()
                    geo_ok, pays_reel = verifier_pays_ip(addr[0], prefixe)
                    prefixes_valides = [v[1] for v in PAYS.values()]

                    if not nom or len(nom) < 2 or len(nom) > 20:
                        signaler_echec(cle_bf_insc)
                        envoyer_srv(conn, {"ok":False,"msg":"Nom: 2 à 20 caractères."})
                    elif not mot_de_passe_est_fort(mdp):
                        signaler_echec(cle_bf_insc)
                        envoyer_srv(conn, {"ok":False,"msg":f"Mot de passe insuffisamment robuste (min {MIN_PASSWORD_LEN} caractères, 3 classes parmi minuscule/majuscule/chiffre/symbole)."})
                    elif prefixe not in prefixes_valides:
                        signaler_echec(cle_bf_insc)
                        envoyer_srv(conn, {"ok":False,"msg":"Pays/prefixe invalide."})
                    elif not RE_PSEUDO.match(pseudo):
                        envoyer_srv(conn, {"ok":False,"msg":"Pseudo invalide: 3-20 caractères, doit commencer par une lettre, lettres/chiffres/underscore uniquement."})
                    elif email and not RE_EMAIL.match(email):
                        envoyer_srv(conn, {"ok":False,"msg":"Format d'email invalide."})
                    elif fs_get_user_by_pseudo(pseudo)[1] is not None:
                        envoyer_srv(conn, {"ok":False,"msg":f"Le pseudo @{pseudo} est déjà pris."})
                    elif email and fs_get_user_by_email(email)[1] is not None:
                        envoyer_srv(conn, {"ok":False,"msg":"Cet email est déjà associé à un compte."})
                    else:
                        numero = gen_numero(prefixe)
                        pays   = next((v[0] for v in PAYS.values() if v[1] == prefixe), "Inconnu")
                        uid    = gen_id("u_")
                        user_data = {
                            "nom": nom, "nom_lower": nom.lower(), "numero": numero,
                            "pseudo": pseudo, "pseudo_lower": pseudo.lower(),
                            "email": email, "email_lower": email if email else None,
                            "mdp": hacher(mdp), "pays": pays, "prefixe": prefixe,
                            "bio": "", "couleur": couleur, "statut": "disponible",
                            "inscription": horodatage(), "derniere_connexion": None,
                            "favoris": [], "bloque": [], "est_admin": False, "pin": None,
                            "cle_publique": (p.get("cle_publique") or "")[:8192] or None,
                            "premium": False, "premium_expire": None,
                            "premium_type": None, "active_par": None,
                            "totp_actif": False, "totp_secret": None, "totp_recovery_codes": [],
                            "pays_incoherent": (not geo_ok),
                            "pays_detecte_ip": pays_reel
                        }
                        if not geo_ok:
                            print(f"⚠️  Inscription avec pays incoherent: {nom} declare {pays} mais IP detectee comme {pays_reel or '?'}")
                        fs_save_user(uid, user_data)
                        signaler_succes(cle_bf_insc)
                        envoyer_srv(conn, {"ok":True,"numero":numero,"nom":nom,"pays":pays,"pseudo":pseudo})

                # ─── CONNEXION (numéro) ───────────────────
                elif act == "connecter_numero":
                    ip = addr[0]
                    cle_bf_ip = f"login_ip:{ip}"
                    numero = p.get("numero","").strip()
                    mdp = p.get("mdp","").strip()
                    cle_bf_acct = f"login_numero:{numero}"
                    if limite_depassee(cle_bf_ip, AUTH_ATTEMPTS_PER_5MIN_IP, 300) or (numero and limite_depassee(cle_bf_acct, AUTH_ATTEMPTS_PER_15MIN_ACCOUNT, 900)):
                        envoyer_srv(conn, {"ok":False,"msg":"Trop de tentatives. Réessaie plus tard."})
                        continue
                    uid, user = fs_get_user_by_numero(numero)
                    if not user or not verifier_mdp(mdp, user.get("mdp")):
                        signaler_echec(cle_bf_ip)
                        if numero:
                            signaler_echec(cle_bf_acct)
                        fs_log_audit_complet(numero or "inconnu", "echec_login", f"Échec connexion numéro depuis {ip}", ip_client=ip)
                        envoyer_srv(conn, {"ok":False,"msg":"Identifiants invalides."})
                    elif user.get("desactive"):
                        signaler_echec(cle_bf_ip)
                        fs_log_audit_complet(numero, "login_compte_desactive", f"Tentative connexion sur compte desactive depuis {ip}", ip_client=ip)
                        envoyer_srv(conn, {"ok":False,"msg":"Ce compte a ete desactive."})
                    else:
                        signaler_succes(cle_bf_ip)
                        signaler_succes(cle_bf_acct)
                        if ALLOW_LEGACY_SHA256_LOGIN and not user.get("mdp","").startswith(("$2b$","$2a$")):
                            fs_update_user(uid, {"mdp": hacher(mdp)})
                        if user.get("totp_actif"):
                            with lock:
                                connexions_en_attente_totp[conn] = {"uid": uid, "ip": ip}
                            envoyer_srv(conn, {"ok":True,"totp_requis":True,"msg":"Entrez votre code TOTP."})
                        else:
                            num_co, est_admin, admin_role = _connecter_user(conn, user, uid, ip_client=ip)

                # ─── CONNEXION (email) ─────────────────────
                # ─── CONNEXION (email) ─────────────────────
                elif act == "connecter_email":
                    ip = addr[0]
                    cle_bf_ip = f"login_ip:{ip}"
                    email = p.get("email","").strip().lower()
                    mdp = p.get("mdp","").strip()
                    cle_bf_acct = f"login_email:{email}"
                    if limite_depassee(cle_bf_ip, AUTH_ATTEMPTS_PER_5MIN_IP, 300) or (email and limite_depassee(cle_bf_acct, AUTH_ATTEMPTS_PER_15MIN_ACCOUNT, 900)):
                        envoyer_srv(conn, {"ok":False,"msg":"Trop de tentatives. Réessaie plus tard."})
                        continue
                    uid, user = fs_get_user_by_email(email)
                    if not user or not verifier_mdp(mdp, user.get("mdp")):
                        signaler_echec(cle_bf_ip)
                        if email:
                            signaler_echec(cle_bf_acct)
                        fs_log_audit_complet(email or "inconnu", "echec_login_email", f"Échec connexion email depuis {ip}", ip_client=ip)
                        envoyer_srv(conn, {"ok":False,"msg":"Identifiants invalides."})
                    elif user.get("desactive"):
                        signaler_echec(cle_bf_ip)
                        fs_log_audit_complet(email, "login_compte_desactive", f"Tentative connexion sur compte desactive depuis {ip}", ip_client=ip)
                        envoyer_srv(conn, {"ok":False,"msg":"Ce compte a ete desactive."})
                    else:
                        signaler_succes(cle_bf_ip)
                        signaler_succes(cle_bf_acct)
                        if ALLOW_LEGACY_SHA256_LOGIN and not user.get("mdp","").startswith(("$2b$","$2a$")):
                            fs_update_user(uid, {"mdp": hacher(mdp)})
                        if user.get("totp_actif"):
                            with lock:
                                connexions_en_attente_totp[conn] = {"uid": uid, "ip": ip}
                            envoyer_srv(conn, {"ok":True,"totp_requis":True,"msg":"Entrez votre code TOTP."})
                        else:
                            num_co, est_admin, admin_role = _connecter_user(conn, user, uid, ip_client=ip)

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

                # ─── TOTP: VERIFIER CODE A LA CONNEXION ───
                elif act == "totp_verifier_connexion":
                    attente = connexions_en_attente_totp.get(conn)
                    if not attente:
                        envoyer_srv(conn, {"ok":False,"msg":"Aucune connexion en attente de code TOTP."})
                    else:
                        cle_bf_totp = f"totp_login:{attente['uid']}"
                        if bloque(cle_bf_totp):
                            envoyer_srv(conn, {"ok":False,"msg":f"Trop de tentatives. Reessaie dans {temps_restant(cle_bf_totp)}s."})
                            continue
                        code = p.get("code","").strip()
                        uid = attente["uid"]
                        user = fs_get_user(uid)
                        secret = totp_dechiffrer_secret(user.get("totp_secret")) if user else None
                        code_recup_valide = False
                        if user and not totp_verifier_code(secret, code):
                            # Tenter un code de recuperation
                            code_hache = totp_hacher_code_recup(code)
                            codes_actuels = user.get("totp_recovery_codes", [])
                            if code_hache in codes_actuels:
                                code_recup_valide = True
                                fs_update_user(uid, {"totp_recovery_codes": [c for c in codes_actuels if c != code_hache]})
                                fs_log_audit_complet(user.get("numero","?"), "totp_code_recup_utilise", "Connexion via code de recuperation TOTP", ip_client=attente["ip"])
                        if not user or (not totp_verifier_code(secret, code) and not code_recup_valide):
                            signaler_echec(cle_bf_totp)
                            fs_log_audit_complet(user.get("numero","?") if user else "inconnu", "totp_login_echec", "Code TOTP invalide a la connexion", ip_client=attente["ip"])
                            envoyer_srv(conn, {"ok":False,"msg":"Code invalide."})
                        else:
                            signaler_succes(cle_bf_totp)
                            with lock:
                                connexions_en_attente_totp.pop(conn, None)
                            num_co, est_admin, admin_role = _connecter_user(conn, user, uid, ip_client=attente["ip"])

                # ─── TOTP: DEMARRER CONFIGURATION ─────────
                elif act == "totp_setup_demarrer":
                    if not num_co:
                        envoyer_srv(conn, {"ok":False,"msg":"Non connecte."})
                    else:
                        uid, user = fs_get_user_by_numero(num_co)
                        if not uid:
                            envoyer_srv(conn, {"ok":False,"msg":"Compte introuvable."})
                        elif user.get("totp_actif"):
                            envoyer_srv(conn, {"ok":False,"msg":"TOTP deja active. Desactivez-le d'abord pour reconfigurer."})
                        else:
                            secret_existant = user.get("totp_secret")
                            if secret_existant:
                                # Une configuration est deja en attente (non confirmee) : on la reutilise
                                # au lieu d'en generer une nouvelle, pour eviter un secret perime.
                                secret = totp_dechiffrer_secret(secret_existant)
                            else:
                                secret = totp_generer_secret()
                                fs_update_user(uid, {"totp_secret": totp_chiffrer_secret(secret)})
                            uri = pyotp.TOTP(secret).provisioning_uri(name=user.get("pseudo") or num_co, issuer_name="TermChat")
                            envoyer_srv(conn, {"ok":True,"secret":secret,"uri":uri,
                                "msg":"Entrez ce secret dans Google Authenticator, puis confirmez avec un code."})
                            fs_log_audit_complet(num_co, "totp_setup_demarre", "Configuration TOTP initiee", ip_client=addr[0])

                # ─── TOTP: CONFIRMER CONFIGURATION ────────
                elif act == "totp_setup_confirmer":
                    if not num_co:
                        envoyer_srv(conn, {"ok":False,"msg":"Non connecte."})
                    else:
                        code = p.get("code","").strip()
                        uid, user = fs_get_user_by_numero(num_co)
                        secret_stocke = user.get("totp_secret") if user else None
                        if not uid or not secret_stocke:
                            envoyer_srv(conn, {"ok":False,"msg":"Aucune configuration TOTP en cours. Lancez totp_setup_demarrer d'abord."})
                        else:
                            secret = totp_dechiffrer_secret(secret_stocke)
                            if not totp_verifier_code(secret, code):
                                fs_log_audit_complet(num_co, "totp_setup_echec", "Code de confirmation TOTP invalide", ip_client=addr[0])
                                envoyer_srv(conn, {"ok":False,"msg":"Code invalide. Reessayez."})
                            else:
                                codes_recup = totp_generer_codes_recuperation()
                                codes_hashes = [totp_hacher_code_recup(c) for c in codes_recup]
                                fs_update_user(uid, {"totp_actif": True, "totp_recovery_codes": codes_hashes})
                                fs_log_audit_complet(num_co, "totp_active", "TOTP active avec succes", ip_client=addr[0])
                                envoyer_srv(conn, {"ok":True,
                                    "msg":"TOTP active ! Notez ces codes de recuperation (usage unique, affiches une seule fois).",
                                    "codes_recuperation": codes_recup})

                # ─── TOTP: DESACTIVER ──────────────────────
                elif act == "totp_desactiver":
                    if not num_co:
                        envoyer_srv(conn, {"ok":False,"msg":"Non connecte."})
                    else:
                        mdp = p.get("mdp","").strip()
                        code = p.get("code","").strip()
                        uid, user = fs_get_user_by_numero(num_co)
                        if not uid or not verifier_mdp(mdp, user.get("mdp")):
                            fs_log_audit_complet(num_co, "totp_desactiver_echec", "Mot de passe invalide pour desactivation TOTP", ip_client=addr[0])
                            envoyer_srv(conn, {"ok":False,"msg":"Mot de passe incorrect."})
                        elif not user.get("totp_actif"):
                            envoyer_srv(conn, {"ok":False,"msg":"TOTP n'est pas active sur ce compte."})
                        else:
                            secret = totp_dechiffrer_secret(user.get("totp_secret"))
                            if not totp_verifier_code(secret, code):
                                fs_log_audit_complet(num_co, "totp_desactiver_echec", "Code TOTP invalide pour desactivation", ip_client=addr[0])
                                envoyer_srv(conn, {"ok":False,"msg":"Code TOTP incorrect."})
                            else:
                                fs_update_user(uid, {"totp_actif": False, "totp_secret": None, "totp_recovery_codes": []})
                                fs_log_audit_complet(num_co, "totp_desactive", "TOTP desactive par l'utilisateur", ip_client=addr[0])
                                envoyer_srv(conn, {"ok":True,"msg":"TOTP desactive."})

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
                    if not num_co:
                        envoyer_srv(conn, {"ok":False,"msg":"Non connecté."})
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
                            contacts = set(fs_mes_contacts(num_co))
                            est_contact = trouve["numero"] in contacts
                            envoyer_srv(conn, {"ok":True,"user":{
                                "nom":trouve.get("nom","?"),"numero":trouve["numero"],
                                "pseudo":trouve.get("pseudo",""),
                                "statut":trouve.get("statut","disponible") if est_contact else None,
                                "cle_publique":trouve.get("cle_publique"),
                                "en_ligne":(trouve["numero"] in clients) if est_contact else False}})

                # ─── PUBLIER CLE PUBLIQUE (chiffrement E2E) ──────────────
                elif act == "publier_cle_publique":
                    if not num_co:
                        envoyer_srv(conn, {"ok": False, "msg": "Non connecté."})
                    else:
                        cle_pub = (p.get("cle_publique") or "").strip()
                        if not cle_pub or len(cle_pub) > 8192:
                            envoyer_srv(conn, {"ok": False, "msg": "Clé publique invalide."})
                            continue
                        uid, user = fs_get_user_by_numero(num_co)
                        if not uid:
                            envoyer_srv(conn, {"ok": False, "msg": "Compte introuvable."})
                            continue
                        ancienne = (user or {}).get("cle_publique")
                        # Refuser le remplacement silencieux d'une clé déjà publiée
                        # (protège contre la substitution de clé / MITM E2E)
                        if ancienne and ancienne != cle_pub:
                            print(f"⚠️  Refus de changement de clé publique pour {num_co}")
                            envoyer_srv(conn, {
                                "ok": False,
                                "msg": "Une clé publique existe déjà. Rotation non autorisée pour le moment."
                            })
                            continue
                        fs_update_user(uid, {
                            "cle_publique": cle_pub,
                            "cle_publique_maj": horodatage()
                        })
                        envoyer_srv(conn, {"ok": True, "msg": "Clé publique enregistrée."})


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
                        elif len(texte) > MAX_MESSAGE_LEN_PREMIUM:
                            envoyer_srv(conn, {"ok":False,"msg":f"Message trop long (max {MAX_MESSAGE_LEN_PREMIUM} caractères)."})
                        else:
                            _, exp_user  = fs_get_user_by_numero(num_co)
                            _, dest_user = fs_get_user_by_numero(dest)
                            if not est_premium_actif(exp_user) and len(texte) > MAX_MESSAGE_LEN_FREE:
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
                                msg_id = gen_id("msg_")
                                msg = {
                                    "id":msg_id,"de":num_co,"vers":dest,"texte":texte,
                                    "type":"texte","heure":horodatage(),"lu":False,
                                    "chiffre":chiffre,"reply_to":reply_to
                                }
                                if expire_s:
                                    try:
                                        expire_s_int = int(expire_s)
                                        if EXPIRE_SECONDES_MIN <= expire_s_int <= EXPIRE_SECONDES_MAX:
                                            msg["expire_a"] = time.time()+expire_s_int
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
                        dest  = p.get("dest","").strip(); msg_id = p.get("msg_id",""); emoji = p.get("emoji","👍")[:8]
                        _, dest_user = fs_get_user_by_numero(dest)
                        if not dest_user:
                            envoyer_srv(conn, {"ok":False,"msg":"Destinataire introuvable."})
                        elif not fs_message_existe(num_co, dest, msg_id):
                            envoyer_srv(conn, {"ok":False,"msg":"Message introuvable dans cette conversation."})
                        else:
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
                        envoyer_srv(conn, {"ok":False,"msg":"Non connecté."})
                    else:
                        statut = p.get("statut","disponible")
                        if statut not in STATUTS:
                            statut = "disponible"
                        uid, _ = fs_get_user_by_numero(num_co)
                        if not uid:
                            envoyer_srv(conn, {"ok":False,"msg":"Utilisateur introuvable."})
                        else:
                            fs_update_user(uid, {"statut": statut})
                            contacts = set(fs_mes_contacts(num_co))
                            with lock:
                                cibles = [(n, s) for n, s in clients.items() if n != num_co and n in contacts]
                            _, eu = fs_get_user_by_numero(num_co)
                            for num, sock in cibles:
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
                        cible_uid, _ = fs_get_user_by_numero(cible)
                        if not uid:
                            envoyer_srv(conn, {"ok":False,"msg":"Utilisateur introuvable."})
                        elif not cible_uid:
                            envoyer_srv(conn, {"ok":False,"msg":"Ce numero ne correspond a aucun compte."})
                        elif cible == num_co:
                            envoyer_srv(conn, {"ok":False,"msg":"Impossible de s'ajouter soi-meme."})
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
                            fs_log_audit_complet(num_co, "bloquer" if action else "debloquer", f"Cible: {cible}", ip_client=addr[0])
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
                        bio = p.get("bio","").strip()[:MAX_BIO_LEN]
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
                            texte = p.get("texte","").strip()[:MAX_FEEDBACK_LEN]
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
                        if not mot_de_passe_est_fort(nouveau): envoyer_srv(conn, {"ok":False,"msg":f"Mot de passe insuffisamment robuste (min {MIN_PASSWORD_LEN} caractères, 3 classes)."})
                        elif not uid or not verifier_mdp(ancien, user.get("mdp")): envoyer_srv(conn, {"ok":False,"msg":"Ancien mot de passe incorrect."})
                        else:
                            fs_update_user(uid, {"mdp":hacher(nouveau)})
                            fs_log_audit_complet(num_co, "changement_mdp", "Mot de passe modifié", ip_client=addr[0])
                            envoyer_srv(conn, {"ok":True,"msg":"Mot de passe change!"})

                elif act == "supprimer_compte":
                    if not num_co: envoyer_srv(conn, {"ok":False,"msg":"Non connecte."})
                    else:
                        if not ALLOW_ACCOUNT_DELETION:
                            envoyer_srv(conn, {"ok":False,"msg":"Suppression de compte désactivée sur cette instance de production."})
                        else:
                            mdp = p.get("mdp","").strip()
                            uid, user = fs_get_user_by_numero(num_co)
                            if not uid or not verifier_mdp(mdp, user.get("mdp")):
                                envoyer_srv(conn, {"ok":False,"msg":"Mot de passe incorrect."})
                            else:
                                fs_log_audit_complet(num_co, "suppression_compte", "Compte désactivé par l'utilisateur", ip_client=addr[0])
                                fs_update_user(uid, {"desactive": True, "desactive_le": horodatage(), "premium": False, "premium_expire": None, "pin": None})
                                envoyer_srv(conn, {"ok":True,"msg":"Compte désactivé."})
                                num_co = None

                # ─── PIN ──────────────────────────────────
                elif act == "definir_pin":
                    if not num_co:
                        envoyer_srv(conn, {"ok":False,"msg":"Non connecte."})
                    else:
                        pin = p.get("pin","").strip()
                        if len(pin)!=4 or not pin.isdigit(): envoyer_srv(conn, {"ok":False,"msg":"Le PIN doit etre 4 chiffres."})
                        else:
                            uid, _ = fs_get_user_by_numero(num_co)
                            if not uid:
                                envoyer_srv(conn, {"ok":False,"msg":"Utilisateur introuvable."})
                            else:
                                fs_update_user(uid, {"pin":hacher(pin)}); envoyer_srv(conn, {"ok":True,"msg":"Code PIN active!"})

                elif act == "supprimer_pin":
                    if not num_co:
                        envoyer_srv(conn, {"ok":False,"msg":"Non connecte."})
                    else:
                        uid, _ = fs_get_user_by_numero(num_co)
                        if not uid:
                            envoyer_srv(conn, {"ok":False,"msg":"Utilisateur introuvable."})
                        else:
                            fs_update_user(uid, {"pin":None}); envoyer_srv(conn, {"ok":True,"msg":"Code PIN desactive."})

                elif act == "verifier_pin":
                    if not num_co:
                        envoyer_srv(conn, {"ok":False,"msg":"Non connecte."})
                    else:
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
                    if not num_co: envoyer_srv(conn, {"ok":False,"msg":"Non connecté."})
                    else:
                        dest = p.get("dest","").strip()
                        nom_fich = p.get("nom_fichier","fichier")
                        c64 = p.get("contenu","")
                        taille_raw = p.get("taille",0)
                        chiffre_f = bool(p.get("chiffre", False))
                        _, exp_user = fs_get_user_by_numero(num_co)
                        _, dest_user = fs_get_user_by_numero(dest)
                        if not ALLOW_INLINE_MEDIA:
                            envoyer_srv(conn, {"ok":False,"msg":"Envoi inline de fichiers désactivé en production Internet."})
                        elif not est_premium_actif(exp_user):
                            envoyer_srv(conn, {"ok":False,"msg":"Envoi de fichiers réservé au premium."})
                        elif not dest_user:
                            envoyer_srv(conn, {"ok":False,"msg":"Destinataire introuvable."})
                        else:
                            try:
                                verifier_budget_stockage()
                                data, taille = decoder_base64_strict(c64, taille_raw, MAX_UPLOAD_BYTES)
                                safe_nom = nettoyer_nom_fichier(nom_fich)
                                chemin = os.path.join(FILES_DIR, f"{gen_id('file_')}_{safe_nom}")
                                ecrire_fichier_protege(chemin, data)
                                cle = "_".join(sorted([num_co, dest]))
                                msg_id = gen_id("msg_")
                                msg = {
                                    "id": msg_id, "de": num_co, "vers": dest,
                                    "texte": safe_nom, "nom_fichier": safe_nom,
                                    "type": "fichier", "heure": horodatage(), "lu": False,
                                    "chiffre": chiffre_f, "taille": taille,
                                    "stockage": "local_temporaire"
                                }
                                fs_save_message(cle, msg)
                                nom_exp = exp_user.get("nom","?") if exp_user else "?"
                                livre = livrer(dest, {"type":"fichier","de":nom_exp,
                                    "numero":num_co,"nom_fichier":safe_nom,"contenu":c64,
                                    "taille":taille,"heure":heure(),"msg_id":msg_id,"chiffre":chiffre_f})
                                envoyer_srv(conn, {"ok":True,"livre":livre,"msg_id":msg_id,"msg":f"'{safe_nom}' envoyé."})
                            except Exception as e:
                                envoyer_srv(conn, {"ok":False,"msg":f"Erreur: {e}"})

                # ─── VOCAL ────────────────────────────────
                elif act == "envoyer_vocal":
                    if not num_co: envoyer_srv(conn, {"ok":False,"msg":"Non connecté."})
                    else:
                        dest = p.get("dest","").strip()
                        c64 = p.get("contenu","")
                        taille_raw = p.get("taille",0)
                        duree_raw = p.get("duree",0)
                        chiffre_v = bool(p.get("chiffre", False))
                        try:
                            duree = int(duree_raw or 0)
                        except Exception:
                            duree = 0
                        _, exp_user = fs_get_user_by_numero(num_co)
                        _, dest_user = fs_get_user_by_numero(dest)
                        if not ALLOW_INLINE_MEDIA:
                            envoyer_srv(conn, {"ok":False,"msg":"Envoi inline de vocaux désactivé en production Internet."})
                        elif not dest_user:
                            envoyer_srv(conn, {"ok":False,"msg":"Destinataire introuvable."})
                        else:
                            try:
                                verifier_budget_stockage()
                                data, taille = decoder_base64_strict(c64, taille_raw, MAX_UPLOAD_BYTES)
                                nom_fich = f"{gen_id('vocal_')}.ogg"
                                chemin = os.path.join(FILES_DIR, nom_fich)
                                ecrire_fichier_protege(chemin, data)
                                cle = "_".join(sorted([num_co, dest]))
                                msg_id = gen_id("msg_")
                                msg = {
                                    "id": msg_id, "de": num_co, "vers": dest,
                                    "texte": nom_fich, "nom_fichier": nom_fich,
                                    "type": "vocal", "heure": horodatage(), "lu": False,
                                    "chiffre": chiffre_v, "taille": taille, "duree": duree,
                                    "stockage": "local_temporaire"
                                }
                                fs_save_message(cle, msg)
                                nom_exp = exp_user.get("nom","?") if exp_user else "?"
                                livre = livrer(dest, {"type":"vocal","de":nom_exp,
                                    "numero":num_co,"nom_fichier":nom_fich,"contenu":c64,
                                    "duree":duree,"taille":taille,"heure":heure(),"msg_id":msg_id,"chiffre":chiffre_v})
                                envoyer_srv(conn, {"ok":True,"livre":livre,"msg_id":msg_id,"msg":"Vocal envoyé!"})
                            except Exception as e:
                                envoyer_srv(conn, {"ok":False,"msg":f"Erreur: {e}"})

                # ─── EN LIGNE ─────────────────────────────
                elif act == "en_ligne":
                    if not num_co:
                        envoyer_srv(conn, {"ok":False,"msg":"Non connecté."})
                    else:
                        contacts = set(fs_mes_contacts(num_co))
                        with lock:
                            liste = [n for n in clients.keys() if n in contacts and n != num_co]
                        result = []
                        for n in liste:
                            _, u = fs_get_user_by_numero(n)
                            if u:
                                result.append({"numero":n,"nom":u.get("nom","?"),"statut":u.get("statut","disponible")})
                        envoyer_srv(conn, {"ok":True,"users":result})

                # ─── GROUPES ──────────────────────────────
                elif act == "creer_groupe":
                    if num_co:
                        nom_g = p.get("nom","").strip()[:MAX_NOM_GROUPE_LEN]
                        if nom_g:
                            _, eu = fs_get_user_by_numero(num_co)
                            gid  = gen_id("grp_")
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
                            if len(membres_actuels) >= MAX_MEMBRES_GROUPE:
                                envoyer_srv(conn, {"ok":False,"msg":f"Limite maximale de {MAX_MEMBRES_GROUPE} membres atteinte."})
                                continue
                            membres = membres_actuels+[cible]
                            if db: db.collection("groupes").document(gid).update({"membres":membres})
                            livrer(cible, {"type":"invitation_groupe","groupe":groupe.get("nom","?"),"id_groupe":gid,"heure":heure()})
                            envoyer_srv(conn, {"ok":True,"msg":"Membre ajoute!"})

                elif act == "retirer_groupe":
                    if not num_co:
                        envoyer_srv(conn, {"ok":False,"msg":"Non connecte."})
                    else:
                        gid=p.get("id_groupe","").strip(); cible=p.get("numero","").strip()
                        groupe = fs_get_groupe(gid)
                        if not groupe: envoyer_srv(conn, {"ok":False,"msg":"Groupe introuvable."})
                        elif groupe["createur"]!=num_co: envoyer_srv(conn, {"ok":False,"msg":"Seul le createur peut retirer un membre."})
                        elif cible == groupe["createur"]: envoyer_srv(conn, {"ok":False,"msg":"Le createur ne peut pas se retirer lui-meme."})
                        elif cible not in groupe.get("membres",[]): envoyer_srv(conn, {"ok":False,"msg":"N'est pas membre de ce groupe."})
                        else:
                            membres = [m for m in groupe.get("membres",[]) if m != cible]
                            if db: db.collection("groupes").document(gid).update({"membres":membres})
                            livrer(cible, {"type":"retire_groupe","groupe":groupe.get("nom","?"),"id_groupe":gid,"heure":heure()})
                            envoyer_srv(conn, {"ok":True,"msg":"Membre retire!"})

                elif act == "membres_groupe":
                    if not num_co:
                        envoyer_srv(conn, {"ok":False,"msg":"Non connecte."})
                    else:
                        gid = p.get("id_groupe","").strip()
                        groupe = fs_get_groupe(gid)
                        if not groupe or num_co not in groupe.get("membres",[]):
                            envoyer_srv(conn, {"ok":False,"msg":"Groupe introuvable ou non membre."})
                        else:
                            envoyer_srv(conn, {"ok":True,"membres":groupe.get("membres",[]),"epoch":groupe.get("epoch",0)})

                elif act == "maj_cle_groupe":
                    if not num_co:
                        envoyer_srv(conn, {"ok":False,"msg":"Non connecte."})
                    else:
                        gid = p.get("id_groupe","").strip()
                        cles = p.get("cles", {})
                        groupe = fs_get_groupe(gid)
                        if not groupe:
                            envoyer_srv(conn, {"ok":False,"msg":"Groupe introuvable."})
                        elif groupe["createur"] != num_co:
                            envoyer_srv(conn, {"ok":False,"msg":"Seul le createur peut gerer les cles."})
                        elif not isinstance(cles, dict) or not cles:
                            envoyer_srv(conn, {"ok":False,"msg":"Cles manquantes."})
                        else:
                            epoch = groupe.get("epoch", 0) + 1
                            if db: db.collection("groupes").document(gid).update({"cles_membres": cles, "epoch": epoch})
                            for m, wrapped in cles.items():
                                if m != num_co:
                                    livrer(m, {"type":"cle_groupe","id_groupe":gid,"epoch":epoch,"cle":wrapped})
                            envoyer_srv(conn, {"ok":True,"epoch":epoch,"msg":"Cle de groupe distribuee."})

                elif act == "obtenir_cle_groupe":
                    if not num_co:
                        envoyer_srv(conn, {"ok":False,"msg":"Non connecte."})
                    else:
                        gid = p.get("id_groupe","").strip()
                        groupe = fs_get_groupe(gid)
                        if not groupe or num_co not in groupe.get("membres",[]):
                            envoyer_srv(conn, {"ok":False,"msg":"Groupe introuvable ou non membre."})
                        else:
                            cles = groupe.get("cles_membres", {})
                            envoyer_srv(conn, {"ok":True,"epoch":groupe.get("epoch",0),"cle":cles.get(num_co),"createur":groupe.get("createur")})

                elif act == "msg_groupe":
                    if not num_co:
                        envoyer_srv(conn, {"ok":False,"msg":"Non connecte."})
                    else:
                        gid=p.get("id_groupe","").strip(); texte=p.get("texte","").strip()
                        reply_raw = p.get("reply_to")
                        reply = str(reply_raw)[:64] if reply_raw else None
                        groupe = fs_get_groupe(gid)
                        _, eu = fs_get_user_by_numero(num_co)
                        if groupe and num_co in groupe.get("membres",[]) and texte and len(texte) > MAX_MESSAGE_LEN_PREMIUM:
                            envoyer_srv(conn, {"ok":False,"msg":f"Message trop long (max {MAX_MESSAGE_LEN_PREMIUM} caractères)."})
                        elif groupe and num_co in groupe.get("membres",[]) and texte and not est_premium_actif(eu) and len(texte) > MAX_MESSAGE_LEN_FREE:
                            envoyer_srv(conn, {"ok":False,"msg":"Message trop long (max 150 caracteres en gratuit). Passe premium pour debloquer."})
                        elif groupe and num_co in groupe.get("membres",[]) and texte:
                            chiffre_g = bool(p.get("chiffre", False))
                            epoch_g = p.get("epoch")
                            msg  = {"de":num_co,"nom":eu.get("nom","?") if eu else "?","texte":texte,"heure":horodatage(),"reply_to":reply,"chiffre":chiffre_g,"epoch":epoch_g}
                            fs_save_msg_groupe(gid, msg)
                            for m in groupe.get("membres",[]):
                                if m!=num_co: livrer(m, {"type":"msg_groupe","groupe":groupe.get("nom","?"),"id_groupe":gid,
                                    "de":eu.get("nom","?") if eu else "?","numero":num_co,"texte":texte,"heure":heure(),"reply_to":reply,"chiffre":chiffre_g,"epoch":epoch_g})
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
                        gid=p.get("id_groupe","").strip(); texte=p.get("texte","").strip()[:MAX_EPINGLE_LEN]
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
                            type_auto = fs_verifier_paiement_sms(code_t, montant)
                            if type_auto:
                                uid_auto, _ = fs_get_user_by_numero(num_co)
                                if type_auto == "fondateur":
                                    expire_auto = None
                                else:
                                    jours_auto = 365 if type_auto == "annuel" else 30
                                    expire_auto = (datetime.datetime.now() + datetime.timedelta(days=jours_auto)).isoformat()
                                fs_update_user(uid_auto, {"premium":True,"premium_expire":expire_auto,
                                    "premium_type":type_auto,"active_par":"auto_sms"})
                                fs_log_audit("auto_sms", "activer_premium_auto", num_co, type_auto)
                                envoyer_srv(conn, {"ok":True,"msg":f"Paiement confirme automatiquement! Premium ({type_auto}) active."})
                                continue
                            pid = fs_save_paiement_attente(num_co, nom, code_t, montant)
                            if pid:
                                envoyer_srv(conn, {"ok":True,"msg":"Paiement soumis! L'admin va verifier et activer ton premium sous peu."})
                            else:
                                envoyer_srv(conn, {"ok":False,"msg":"Erreur, reessaie plus tard."})

                elif act == "admin_activer_premium":
                    if not a_permission(admin_role, "admin_activer_premium"): envoyer_srv(conn, {"ok":False,"msg":"Acces refuse."})
                    else:
                        cible = p.get("numero","").strip()
                        type_abo = p.get("type","mensuel")  # "mensuel", "annuel" ou "fondateur"
                        uid, user = fs_get_user_by_numero(cible)
                        if not uid: envoyer_srv(conn, {"ok":False,"msg":"Utilisateur introuvable."})
                        elif type_abo not in TYPES_ABONNEMENT_VALIDES:
                            envoyer_srv(conn, {"ok":False,"msg":f"Type d'abonnement invalide. Valeurs autorisees: {', '.join(TYPES_ABONNEMENT_VALIDES)}."})
                        else:
                            fs_log_audit(num_co, "activer_premium", cible, type_abo)
                            if type_abo in ("fondateur", "beta"):
                                expire = None
                                libelle = "Fondateur" if type_abo == "fondateur" else "Beta Testeur"
                                fs_update_user(uid, {"premium":True,"premium_expire":expire,
                                    "premium_type":type_abo,"active_par":num_co})
                                livrer(cible, {"type":"premium_active","expire":"jamais","premium_type":type_abo,"msg":f"Ton compte {libelle} est actif a vie!"})
                                envoyer_srv(conn, {"ok":True,"msg":f"Premium {libelle} (a vie) active pour {cible}."})
                            else:
                                jours = 365 if type_abo == "annuel" else 30
                                expire = (datetime.datetime.now() + datetime.timedelta(days=jours)).isoformat()
                                fs_update_user(uid, {"premium":True,"premium_expire":expire,
                                    "premium_type":type_abo,"active_par":num_co})
                                livrer(cible, {"type":"premium_active","expire":expire,"premium_type":type_abo,"msg":"Ton compte premium est actif!"})
                                envoyer_srv(conn, {"ok":True,"msg":f"Premium ({type_abo}) active pour {cible} jusqu'au {expire[:10]}."})

                elif act == "admin_desactiver_premium":
                    if not a_permission(admin_role, "admin_desactiver_premium"): envoyer_srv(conn, {"ok":False,"msg":"Acces refuse."})
                    else:
                        cible = p.get("numero","").strip()
                        uid, _ = fs_get_user_by_numero(cible)
                        if not uid: envoyer_srv(conn, {"ok":False,"msg":"Utilisateur introuvable."})
                        else:
                            fs_log_audit(num_co, "desactiver_premium", cible)
                            fs_update_user(uid, {"premium":False,"premium_expire":None,"premium_type":None})
                            envoyer_srv(conn, {"ok":True,"msg":f"Premium desactive pour {cible}."})

                # ─── ADMIN ────────────────────────────────
                elif act == "admin_login":
                    ip = addr[0]
                    cle_bf = f"admin_{ip}"
                    if bloque(cle_bf):
                        envoyer_srv(conn, {"ok": False, "msg": f"Trop de tentatives. Réessaie dans {temps_restant(cle_bf)}s."})
                        continue
                    if not ip_autorisee_pour_admin(ip):
                        signaler_echec(cle_bf)
                        envoyer_srv(conn, {"ok": False, "msg": "Origine IP non autorisée pour l’administration."})
                        continue
                    if not num_co:
                        signaler_echec(cle_bf)
                        envoyer_srv(conn, {"ok": False, "msg": "Authentifie-toi d’abord avec un compte."})
                        continue
                    # Le compte doit déjà porter le flag est_admin dans Firestore
                    # (à définir manuellement, jamais via l’interface publique)
                    _, user = fs_get_user_by_numero(num_co)
                    if not user or not user.get("est_admin"):
                        signaler_echec(cle_bf)
                        envoyer_srv(conn, {"ok": False, "msg": "Ce compte n’est pas autorisé à devenir administrateur."})
                        continue
                    # Comparaison en temps constant
                    if secrets.compare_digest(p.get("code", "") or "", ADMIN_CODE):
                        signaler_succes(cle_bf)
                        est_admin = True
                        admin_role = user.get("role") or "super_admin"
                        with lock:
                            admins_connectes.add(num_co)
                        envoyer_srv(conn, {"ok": True, "msg": "Accès admin accordé.", "role": admin_role})
                    else:
                        signaler_echec(cle_bf)
                        envoyer_srv(conn, {"ok": False, "msg": "Code incorrect."})

                elif act == "admin_stats":
                    if not a_permission(admin_role, "admin_stats"): envoyer_srv(conn, {"ok":False,"msg":"Acces refuse."})
                    else:
                        stats = fs_get_stats()
                        with lock: stats["en_ligne"] = len(clients)
                        envoyer_srv(conn, {"ok":True,"stats":stats})

                elif act == "admin_feedback":
                    if not a_permission(admin_role, "admin_feedback"): envoyer_srv(conn, {"ok":False,"msg":"Acces refuse."})
                    else:
                        envoyer_srv(conn, {"ok":True,"feedback":fs_get_feedback()})

                elif act == "admin_users":
                    if not a_permission(admin_role, "admin_users"): envoyer_srv(conn, {"ok":False,"msg":"Acces refuse."})
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
                                        "en_ligne":u.get("numero") in ens,
                                        "pays_incoherent":u.get("pays_incoherent", False)})
                                envoyer_srv(conn, {"ok":True,"users":users})
                            except Exception as e: envoyer_srv(conn, {"ok":False,"msg":str(e)})

                elif act == "admin_broadcast":
                    if not a_permission(admin_role, "admin_broadcast"): envoyer_srv(conn, {"ok":False,"msg":"Acces refuse."})
                    else:
                        cle_bf_br = f"broadcast_{num_co}"
                        if bloque(cle_bf_br):
                            envoyer_srv(conn, {"ok":False,"msg":f"Trop de broadcasts. Réessaie dans {temps_restant(cle_bf_br)}s."})
                            continue
                        msg = p.get("msg","").strip()
                        if not msg:
                            envoyer_srv(conn, {"ok":False,"msg":"Message vide."})
                            continue
                        with lock: tous = list(clients.values())
                        for s in tous: envoyer_srv(s, {"type":"annonce","msg":msg,"heure":heure()})
                        signaler_echec(cle_bf_br)  # incrémente le compteur (5 broadcasts max puis blocage 5min)
                        fs_log_audit(num_co, "broadcast", details=f"Envoyé à {len(tous)} utilisateurs")
                        envoyer_srv(conn, {"ok":True,"msg":f"Envoye a {len(tous)} utilisateurs."})

                elif act == "admin_kick":
                    if not a_permission(admin_role, "admin_kick"): envoyer_srv(conn, {"ok":False,"msg":"Acces refuse."})
                    else:
                        cible = p.get("numero","").strip()
                        fs_log_audit(num_co, "kick", cible)
                        with lock: s = clients.get(cible)
                        if s:
                            envoyer_srv(s, {"type":"kick","msg":"Deconnecte par l'administrateur."})
                            try: s.close()
                            except Exception: pass
                            envoyer_srv(conn, {"ok":True,"msg":"Utilisateur deconnecte."})
                        else: envoyer_srv(conn, {"ok":False,"msg":"Utilisateur hors ligne."})

                elif act == "admin_message":
                    if not a_permission(admin_role, "admin_message"): envoyer_srv(conn, {"ok":False,"msg":"Acces refuse."})
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
                    if not a_permission(admin_role, "admin_paiements_attente"): envoyer_srv(conn, {"ok":False,"msg":"Acces refuse."})
                    else:
                        paiements = fs_get_paiements_attente()
                        envoyer_srv(conn, {"ok":True,"paiements":paiements})

                elif act == "admin_audit_log":
                    if not a_permission(admin_role, "admin_audit_log"): envoyer_srv(conn, {"ok":False,"msg":"Acces refuse."})
                    else:
                        if not db:
                            envoyer_srv(conn, {"ok":False,"msg":"Base de donnees indisponible."})
                        else:
                            try:
                                docs = db.collection("audit_log").order_by("heure", direction=firestore.Query.DESCENDING).limit(30).stream()
                                entries = [d.to_dict() for d in docs]
                                envoyer_srv(conn, {"ok":True,"entries":entries})
                            except Exception as e:
                                envoyer_srv(conn, {"ok":False,"msg":str(e)})

                elif act == "admin_confirmer_paiement":
                    if not a_permission(admin_role, "admin_confirmer_paiement"): envoyer_srv(conn, {"ok":False,"msg":"Acces refuse."})
                    else:
                        pid    = p.get("id","").strip()
                        cible  = p.get("numero","").strip()
                        type_abo = p.get("type","mensuel")
                        paiement = fs_get_paiement(pid)
                        uid, user = fs_get_user_by_numero(cible)
                        if not uid:
                            envoyer_srv(conn, {"ok":False,"msg":"Utilisateur introuvable."})
                        elif type_abo not in TYPES_ABONNEMENT_VALIDES:
                            envoyer_srv(conn, {"ok":False,"msg":f"Type d'abonnement invalide. Valeurs autorisees: {', '.join(TYPES_ABONNEMENT_VALIDES)}."})
                        elif not paiement:
                            envoyer_srv(conn, {"ok":False,"msg":"Paiement introuvable."})
                        elif paiement.get("statut") != "attente":
                            envoyer_srv(conn, {"ok":False,"msg":"Ce paiement a deja ete traite."})
                        elif paiement.get("numero") != cible:
                            envoyer_srv(conn, {"ok":False,"msg":"Ce paiement n'appartient pas a ce numero."})
                        elif TARIFS_PREMIUM.get(str(paiement.get("montant","")).strip()) != type_abo:
                            envoyer_srv(conn, {"ok":False,"msg":"Le montant du paiement ne correspond pas au type d'abonnement choisi."})
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
                    if not a_permission(admin_role, "admin_rejeter_paiement"): envoyer_srv(conn, {"ok":False,"msg":"Acces refuse."})
                    else:
                        pid = p.get("id","").strip()
                        fs_update_paiement(pid, "rejete")
                        envoyer_srv(conn, {"ok":True,"msg":"Paiement rejete."})

                elif act == "admin_surveillance":
                    if not a_permission(admin_role, "admin_surveillance"): envoyer_srv(conn, {"ok":False,"msg":"Acces refuse."})
                    else:
                        with lock:
                            result = []
                            for num, info in connexions_actives.items():
                                _, u = fs_get_user_by_numero(num)
                                result.append({
                                    "numero": num,
                                    "nom": info.get("nom", "?"),
                                    "ip": info.get("ip", "?"),
                                    "pays": info.get("pays", "?"),
                                    "heure_connexion": info.get("heure_connexion", "")[:16].replace("T", " "),
                                    "statut": info.get("statut", "disponible"),
                                    "en_ligne": True
                                })
                        envoyer_srv(conn, {"ok":True,"connexions":result})

                elif act == "admin_alertes_securite":
                    if not a_permission(admin_role, "admin_alertes_securite"): envoyer_srv(conn, {"ok":False,"msg":"Acces refuse."})
                    else:
                        # Générer alertes dynamiques depuis l'audit log
                        alerts = []
                        if db:
                            try:
                                docs = db.collection("audit_log")                                         .where(filter=FieldFilter("action", "in", ["echec_login", "echec_login_email", "session_kick_auto"]))                                         .order_by("heure", direction=firestore.Query.DESCENDING)                                         .limit(50).stream()
                                for d in docs:
                                    data = d.to_dict()
                                    sev = "CRITIQUE" if "echec" in data.get("action","") and "login" in data.get("action","") else "MOYEN"
                                    alerts.append({
                                        "heure": data.get("heure","")[:16].replace("T"," "),
                                        "severite": sev,
                                        "type": data.get("action","").replace("_", " ").title(),
                                        "ip": data.get("ip","inconnu"),
                                        "details": data.get("details",""),
                                        "numero": data.get("numero","?")
                                    })
                            except Exception as e:
                                print(f"Firestore alertes: {e}")
                        envoyer_srv(conn, {"ok":True,"alertes":alerts})

                elif act == "admin_voir_conversation":
                    if not a_permission(admin_role, "admin_voir_conversation"): envoyer_srv(conn, {"ok":False,"msg":"Acces refuse."})
                    else:
                        n1 = p.get("numero1","").strip()
                        n2 = p.get("numero2","").strip()
                        if not n1 or not n2:
                            envoyer_srv(conn, {"ok":False,"msg":"Deux numéros requis."})
                        else:
                            hist = fs_get_messages(n1, n2, 100)
                            _, u1 = fs_get_user_by_numero(n1)
                            _, u2 = fs_get_user_by_numero(n2)
                            noms = {}
                            if u1: noms[n1] = u1.get("nom", n1)
                            if u2: noms[n2] = u2.get("nom", n2)
                            for m in hist:
                                m["nom_de"] = noms.get(m.get("de"), m.get("de", "?"))
                            fs_log_audit(num_co, "voir_conversation", f"{n1}_{n2}", "Modération")
                            envoyer_srv(conn, {"ok":True,"historique":hist,"entre":f"{noms.get(n1,n1)} ↔ {noms.get(n2,n2)}"})

                elif act == "admin_voir_fichiers":
                    if not a_permission(admin_role, "admin_voir_fichiers"): envoyer_srv(conn, {"ok":False,"msg":"Acces refuse."})
                    else:
                        fichiers = []
                        try:
                            for f in sorted(Path(FILES_DIR).glob("*"), key=lambda x: x.stat().st_mtime, reverse=True)[:50]:
                                if f.is_file():
                                    fichiers.append({
                                        "nom": f.name,
                                        "taille": f.stat().st_size,
                                        "date": datetime.datetime.fromtimestamp(f.stat().st_mtime).isoformat()[:16].replace("T"," ")
                                    })
                        except Exception:
                            pass
                        envoyer_srv(conn, {"ok":True,"fichiers":fichiers})

                elif act == "signaler":
                    if not num_co:
                        envoyer_srv(conn, {"ok":False,"msg":"Non connecte."})
                    else:
                        cible = p.get("numero","").strip()
                        raison = p.get("raison","").strip()
                        msg_id = p.get("msg_id","")
                        if not cible or not raison:
                            envoyer_srv(conn, {"ok":False,"msg":"Numéro et raison requis."})
                        else:
                            fs_log_audit_complet(num_co, "signalement", f"Signale {cible}: {raison}", ip_client=addr[0])
                            if db:
                                try:
                                    sid = gen_id("sig_")
                                    db.collection("signalements").document(sid).set({
                                        "signaleur": num_co,
                                        "cible": cible,
                                        "raison": raison,
                                        "msg_id": msg_id,
                                        "heure": horodatage(),
                                        "statut": "nouveau",
                                        "ip": addr[0]
                                    })
                                except Exception as e:
                                    print(f"Firestore signalement: {e}")
                            envoyer_srv(conn, {"ok":True,"msg":"Signalement enregistré. L'admin va examiner."})

                elif act == "admin_signalements":
                    if not a_permission(admin_role, "admin_signalements"): envoyer_srv(conn, {"ok":False,"msg":"Acces refuse."})
                    else:
                        sigs = []
                        if db:
                            try:
                                docs = db.collection("signalements")                                         .where(filter=FieldFilter("statut", "==", "nouveau"))                                         .order_by("heure", direction=firestore.Query.DESCENDING)                                         .limit(30).stream()
                                for d in docs:
                                    data = d.to_dict()
                                    data["id"] = d.id
                                    sigs.append(data)
                            except Exception as e:
                                print(f"Firestore signalements: {e}")
                        envoyer_srv(conn, {"ok":True,"signalements":sigs})

                elif act == "admin_traiter_signalement":
                    if not a_permission(admin_role, "admin_traiter_signalement"): envoyer_srv(conn, {"ok":False,"msg":"Acces refuse."})
                    else:
                        sid = p.get("id","").strip()
                        decision = p.get("decision","").strip()  # "archive" ou "kick"
                        if db and sid:
                            try:
                                db.collection("signalements").document(sid).update({"statut": "traite", "decision": decision, "traite_par": num_co, "traite_le": horodatage()})
                            except Exception:
                                pass
                        envoyer_srv(conn, {"ok":True,"msg":f"Signalement {decision}."})

                elif act == "admin_gerer_role":
                    if not a_permission(admin_role, "admin_gerer_role"):
                        envoyer_srv(conn, {"ok":False,"msg":"Acces refuse. Seul le super-admin peut gerer les roles."})
                    else:
                        cible = p.get("numero","").strip()
                        nouveau_role = p.get("role","").strip()  # "super_admin"/"moderator"/"payment_admin" ou "" pour retirer
                        uid_c, user_c = fs_get_user_by_numero(cible)
                        if not uid_c:
                            envoyer_srv(conn, {"ok":False,"msg":"Utilisateur introuvable."})
                        elif nouveau_role and nouveau_role not in ROLES_ADMIN:
                            envoyer_srv(conn, {"ok":False,"msg":f"Role invalide. Valeurs autorisees: {', '.join(ROLES_ADMIN)}."})
                        elif nouveau_role:
                            fs_update_user(uid_c, {"est_admin": True, "role": nouveau_role})
                            fs_log_audit(num_co, "gerer_role", cible, f"role={nouveau_role}")
                            envoyer_srv(conn, {"ok":True,"msg":f"{cible} est maintenant {nouveau_role}."})
                        else:
                            fs_update_user(uid_c, {"est_admin": False, "role": None})
                            fs_log_audit(num_co, "gerer_role", cible, "revoque")
                            envoyer_srv(conn, {"ok":True,"msg":f"Acces admin retire pour {cible}."})

                elif act == "admin_reinitialiser_cle":
                    if not a_permission(admin_role, "admin_reinitialiser_cle"):
                        envoyer_srv(conn, {"ok":False,"msg":"Acces refuse. Seul le super-admin peut reinitialiser une cle publique."})
                    else:
                        cible = p.get("numero","").strip()
                        uid_c, user_c = fs_get_user_by_numero(cible)
                        if not uid_c:
                            envoyer_srv(conn, {"ok":False,"msg":"Utilisateur introuvable."})
                        elif not user_c.get("cle_publique"):
                            envoyer_srv(conn, {"ok":False,"msg":"Ce compte n'a pas de cle publique enregistree."})
                        else:
                            fs_update_user(uid_c, {"cle_publique": None})
                            fs_log_audit(num_co, "reinitialiser_cle_publique", cible, "cle publique effacee")
                            envoyer_srv(conn, {"ok":True,"msg":f"Cle publique de {cible} reinitialisee. Elle sera republiee a sa prochaine connexion. Prevenir l'utilisateur : ses contacts devront revalider l'empreinte /empreinte."})

                else: envoyer_srv(conn, {"ok":False,"msg":f"Action inconnue: {act}"})

    except Exception as e:
        print(f"⚠️  Erreur gerer_client: {e}")
    finally:
        if num_co:
            with lock:
                clients.pop(num_co,None)
                admins_connectes.discard(num_co)
                if num_co in sessions_par_user:
                    sessions_par_user[num_co].discard(conn)
                    if not sessions_par_user[num_co]:
                        sessions_par_user.pop(num_co, None)
                connexions_actives.pop(num_co, None)
            try: notifier_statut(num_co, False)
            except Exception: pass
        try: conn.close()
        except Exception: pass
        with connexions_lock:
            connexions_count -= 1

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
    print("║  💬  TERMCHAT v6.1 — SERVEUR (sécurisé)  ║")
    print("║  by Aboudev Labs 🇨🇮                     ║")
    print("╚══════════════════════════════════════════╝")
    print(f"🔒 Bind: {BIND_HOST}:{PORT} | TLS requis: {REQUIRE_TLS} | Production: {PRODUCTION_MODE}")
    if REQUIRE_FIREBASE and not init_firebase():
        print("❌ Démarrage refusé: Firebase requis mais indisponible.")
        sys.exit(1)
    elif not REQUIRE_FIREBASE:
        init_firebase()
    preparer_certificat_tls()
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    srv.bind((BIND_HOST, PORT)); srv.listen(512)

    ctx = None
    if os.path.exists(CERT_FILE) and os.path.exists(KEY_FILE):
        try:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.minimum_version = ssl.TLSVersion.TLSv1_3 if hasattr(ssl.TLSVersion, "TLSv1_3") else ssl.TLSVersion.TLSv1_2
            ctx.options |= getattr(ssl, "OP_NO_COMPRESSION", 0)
            try:
                ctx.set_ciphers("ECDHE+AESGCM:ECDHE+CHACHA20")
            except ssl.SSLError:
                pass
            ctx.load_cert_chain(CERT_FILE, KEY_FILE)
            print(f"✅ TCP+TLS port {PORT}")
        except Exception as e:
            ctx = None
            print(f"⚠️  TLS indisponible ({e})")
    else:
        print(f"⚠️  Pas de certificat TLS valide pour le port {PORT}")

    if REQUIRE_TLS and ctx is None:
        print("❌ Démarrage refusé: TLS requis mais indisponible.")
        sys.exit(1)

    def quitter(sig, frame): srv.close(); sys.exit(0)
    signal.signal(signal.SIGINT, quitter); signal.signal(signal.SIGTERM, quitter)
    while True:
        try:
            conn, addr = srv.accept()
            with connexions_lock:
                nb_actifs = connexions_count
            if nb_actifs >= MAX_CONNEXIONS_SIMULTANEES:
                try: conn.close()
                except Exception: pass
                continue
            if ctx:
                threading.Thread(target=gerer_client_tls, args=(conn, addr, ctx), daemon=True).start()
            else:
                try:
                    conn.close()
                except Exception:
                    pass
        except Exception as e:
            print(f"⚠️  Erreur boucle accept (ignoree, on continue): {e}")
            continue

if __name__ == "__main__": main()
