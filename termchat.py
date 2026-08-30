#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TermChat v6.3 — Client (surveillance + signalement)
Messagerie mondiale pour développeurs — by Aboudev Labs 🇨🇮
Correctifs v6.3 : Connexion directe, surveillance admin, signalement, TLS renforcé, E2E.
"""

import socket
import threading
import json
import os
import base64
import ssl
import datetime
import time
import sys
import signal
import hashlib
import getpass
import secrets

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.backends import default_backend

# ── Couleurs terminal ──────────────────────────────────────────────────────────
R = "\033[91m"
B = "\033[1m"
Z = "\033[0m"
G = "\033[90m"
V = "\033[92m"
J = "\033[93m"
M = "\033[95m"

COULEURS = {
    "cyan": "\033[96m",
    "vert": "\033[92m",
    "jaune": "\033[93m",
    "magenta": "\033[95m",
    "bleu": "\033[94m",
    "rouge": "\033[91m",
    "blanc": "\033[97m",
}

STATUTS_ICONS = {
    "disponible": f"{V}🟢 Disponible{Z}",
    "occupe": f"{J}🟡 Occupe{Z}",
    "ne_pas_deranger": f"{R}🔴 Ne pas deranger{Z}",
    "absent": f"{G}⚫ Absent{Z}",
}

# ── Chemins ───────────────────────────────────────────────────────────────────
DOWNLOADS = os.path.join(os.path.expanduser("~"), "termchat_downloads")
os.makedirs(DOWNLOADS, exist_ok=True)

TRUST_DIR = os.path.join(os.path.expanduser("~"), ".termchat_tls")
KNOWN_HOSTS = os.path.join(TRUST_DIR, "known_hosts.json")
def _identity_file_pour(numero):
    """Chaque compte a son propre fichier de cle d'identite, isole par numero."""
    safe_num = "".join(c for c in (numero or "defaut") if c.isalnum() or c == "+")
    return os.path.join(TRUST_DIR, f"identity_key_{safe_num}.enc")
os.makedirs(TRUST_DIR, exist_ok=True)
TLS_PIN_FILE = KNOWN_HOSTS


def empreinte_certificat(sock):
    cert = sock.getpeercert(binary_form=True)
    return hashlib.sha256(cert).hexdigest()


def verifier_confiance_tls(host, port, empreinte):
    cle = f"{host}:{port}"

    try:
        with open(TLS_PIN_FILE, "r", encoding="utf-8") as f:
            pins = json.load(f)
    except Exception:
        pins = {}

    if cle not in pins:
        pins[cle] = empreinte
        with open(TLS_PIN_FILE, "w", encoding="utf-8") as f:
            json.dump(pins, f, indent=2)
        try:
            os.chmod(TLS_PIN_FILE, 0o600)
        except Exception:
            pass
        print(f"{J}🔐 Premier certificat enregistré (TOFU).{Z}")
        return True

    if pins[cle] != empreinte:
        print(f"{R}❌ Le certificat du serveur a changé !{Z}")
        return False

    return True

MAX_FILE_RECV = 15 * 1024 * 1024  # 15 Mo max à la réception
MAX_FILE_SEND = 50 * 1024 * 1024  # 50 Mo max à l'envoi

# ── Pays ──────────────────────────────────────────────────────────────────────
PAYS = {
    "1": ("🇨🇮 Cote d'Ivoire", "+225"),
    "2": ("🇸🇳 Senegal", "+221"),
    "3": ("🇬🇳 Guinee", "+224"),
    "4": ("🇧🇫 Burkina Faso", "+226"),
    "5": ("🇬🇭 Ghana", "+233"),
    "6": ("🇲🇱 Mali", "+223"),
    "7": ("🇹🇬 Togo", "+228"),
    "8": ("🇧🇯 Benin", "+229"),
    "9": ("🇳🇪 Niger", "+227"),
    "10": ("🇳🇬 Nigeria", "+234"),
    "11": ("🇨🇲 Cameroun", "+237"),
}

# ── État global ───────────────────────────────────────────────────────────────
session = {
    "connecte": False,
    "nom": None,
    "numero": None,
    "pays": None,
    "bio": "",
    "couleur": "cyan",
    "statut": "disponible",
    "est_admin": False,
    "non_lus": 0,
    "a_pin": False,
    "pseudo": "",
    "premium": False,
    "premium_type": None,
    "role": None,
}

sock_cli = None
en_cours = True
reponses = []
rep_lock = threading.Lock()

phrases_secretes = {}          # numero -> phrase secrète (RAM uniquement)
ma_cle_privee = None
cles_partagees_cache = {}      # numero -> clé Fernet dérivée
cles_groupes_cache = {}        # id_groupe -> {epoch: clé Fernet}

# Le code de connexion TLS est dans main().


# ══════════════════════════════════════════════════════════════════════════════
#  Identité X25519 (clé privée chiffrée au repos)
# ══════════════════════════════════════════════════════════════════════════════

def _deriver_cle_fichier(mdp: str, salt: bytes) -> bytes:
    kdf = Scrypt(
        salt=salt,
        length=32,
        n=2**14,
        r=8,
        p=1,
        backend=default_backend(),
    )
    return kdf.derive(mdp.encode())


def charger_ou_creer_identite(numero=None):
    """Charge la clé privée X25519 chiffrée, ou en crée une protégée par mot de passe."""
    identity_file = _identity_file_pour(numero)
    if os.path.exists(identity_file):
        try:
            with open(identity_file, "rb") as f:
                data = f.read()
            if len(data) < 17:
                raise ValueError("Fichier identité corrompu")
            salt, ciphertext = data[:16], data[16:]
            mdp = getpass.getpass(f"{J}Mot de passe de ta clé d'identité : {Z}")
            key = _deriver_cle_fichier(mdp, salt)
            fernet = Fernet(base64.urlsafe_b64encode(key))
            raw = fernet.decrypt(ciphertext)
            return X25519PrivateKey.from_private_bytes(raw)
        except Exception as e:
            erreur(f"Impossible de déchiffrer la clé d'identité ({e}).")
            print(f"{J}Si tu as oublié le mot de passe, supprime le fichier :{Z}")
            print(f"   {identity_file}")

    else:
        priv = X25519PrivateKey.generate()
        raw = priv.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
        print(f"\n{J}🔐 Première utilisation — protection de ta clé d'identité{Z}")
        print(f"{G}Ce mot de passe protège ta clé privée sur le disque.{Z}")
        print(f"{G}Il est différent de ton mot de passe TermChat.{Z}\n")
        while True:
            mdp = getpass.getpass(f"{J}Choisis un mot de passe (min 8 car.) : {Z}")
            if len(mdp) < 8:
                erreur("Minimum 8 caractères.")
                continue
            mdp2 = getpass.getpass(f"{J}Confirme : {Z}")
            if mdp != mdp2:
                erreur("Les mots de passe ne correspondent pas.")
                continue
            break

        salt = os.urandom(16)
        key = _deriver_cle_fichier(mdp, salt)
        fernet = Fernet(base64.urlsafe_b64encode(key))
        ciphertext = fernet.encrypt(raw)

        with open(identity_file, "wb") as f:
            f.write(salt + ciphertext)
        try:
            os.chmod(identity_file, 0o600)
        except Exception:
            pass
        succes("Clé d'identité créée et protégée.")
        return priv


def cle_publique_b64(priv):
    pub = priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return base64.urlsafe_b64encode(pub).decode()


def calculer_empreinte_verification(ma_cle_pub_b64, cle_pub_pair_b64):
    """Calcule une empreinte courte a partir des deux cles publiques (verification manuelle anti-MITM)."""
    import hashlib
    cles = sorted([ma_cle_pub_b64 or "", cle_pub_pair_b64 or ""])
    combinaison = (cles[0] + cles[1]).encode()
    h = hashlib.sha256(combinaison).hexdigest()
    groupes = [h[i:i+5] for i in range(0, 30, 5)]
    return " ".join(groupes).upper()

def deriver_cle_partagee(ma_cle_privee, cle_publique_pair_b64, n1, n2):
    """Établit une clé symétrique via ECDH X25519 + HKDF (versionnée)."""
    pub_pair = X25519PublicKey.from_public_bytes(
        base64.urlsafe_b64decode(cle_publique_pair_b64)
    )
    secret = ma_cle_privee.exchange(pub_pair)
    sel = "".join(sorted([n1, n2])).encode()
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=sel,
        info=b"termchat-e2e-v2",
    )
    return base64.urlsafe_b64encode(hkdf.derive(secret))


def generer_cle(n1, n2, phrase_secrete):
    """Dérive une clé Fernet à partir d'une phrase secrète (mode secours)."""
    sel = "".join(sorted([n1, n2])).encode()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=sel,
        iterations=200_000,
    )
    return base64.urlsafe_b64encode(kdf.derive(phrase_secrete.encode()))


def obtenir_cle_partagee(nd):
    """Retourne la clé Fernet partagée avec un contact si elle est connue
    (auto via échange de clés publiques, ou manuelle via phrase secrète)."""
    cle = cles_partagees_cache.get(nd)
    if cle:
        return cle
    phrase = phrases_secretes.get(nd)
    if phrase:
        try:
            return generer_cle(session.get("numero", ""), nd, phrase)
        except Exception:
            return None
    return None


def distribuer_cle_groupe(id_groupe, membres):
    """Genere une nouvelle cle de groupe et la distribue, chiffree individuellement
    pour chaque membre actuel (via ECDH X25519 1-a-1). Seul le createur du groupe
    doit appeler cette fonction (creation du groupe, ajout ou retrait d'un membre).
    Retourne le numero d'epoque si succes, sinon None."""
    if not ma_cle_privee:
        return None
    moi = session.get("numero", "")
    nouvelle_cle = Fernet.generate_key()
    cles_wrap = {}
    ma_pub = cle_publique_b64(ma_cle_privee)
    for m in membres:
        if m == moi:
            cle_pub_m = ma_pub
        else:
            envoyer_cli({"action": "chercher", "numero": m})
            rep = attendre()
            if not rep or not rep.get("ok"):
                continue
            cle_pub_m = rep.get("user", {}).get("cle_publique")
        if not cle_pub_m:
            continue
        try:
            partagee = deriver_cle_partagee(ma_cle_privee, cle_pub_m, moi, m)
            cles_wrap[m] = chiffrer_bytes(nouvelle_cle, partagee).decode()
        except Exception:
            continue
    envoyer_cli({"action": "maj_cle_groupe", "id_groupe": id_groupe, "cles": cles_wrap})
    rep = attendre()
    if rep and rep.get("ok"):
        epoch = rep.get("epoch")
        cles_groupes_cache.setdefault(id_groupe, {})[epoch] = nouvelle_cle
        return epoch
    return None


def obtenir_cle_groupe(id_groupe):
    """Retourne la clé de groupe pour l'époque courante, en la récupérant du
    serveur si elle n'est pas déjà en cache local (ex: après reconnexion)."""
    cache = cles_groupes_cache.get(id_groupe, {})
    if cache:
        epoch_max = max(cache.keys())
        return epoch_max, cache[epoch_max]
    envoyer_cli({"action": "obtenir_cle_groupe", "id_groupe": id_groupe})
    rep = attendre()
    if not rep or not rep.get("ok") or not rep.get("cle") or not ma_cle_privee:
        return None, None
    createur = rep.get("createur")
    moi = session.get("numero", "")
    if not createur:
        return None, None
    if createur == moi:
        cle_pub_source = cle_publique_b64(ma_cle_privee)
        source = moi
    else:
        envoyer_cli({"action": "chercher", "numero": createur})
        rep_c = attendre()
        if not rep_c or not rep_c.get("ok"):
            return None, None
        cle_pub_source = rep_c.get("user", {}).get("cle_publique")
        source = createur
    if not cle_pub_source:
        return None, None
    try:
        partagee = deriver_cle_partagee(ma_cle_privee, cle_pub_source, moi, source)
        cle_groupe = dechiffrer_bytes(rep["cle"].encode(), partagee)
        epoch = rep.get("epoch")
        cles_groupes_cache.setdefault(id_groupe, {})[epoch] = cle_groupe
        return epoch, cle_groupe
    except Exception:
        return None, None


def chiffrer_bytes(data: bytes, cle) -> bytes:
    """Chiffre des octets bruts avec Fernet, renvoie un token base64 standard
    (le token Fernet est en base64 'urlsafe', réencodé en standard pour
    passer la validation stricte du serveur)."""
    token = Fernet(cle).encrypt(data)
    return base64.b64encode(token)


def dechiffrer_bytes(contenu_b64: bytes, cle) -> bytes:
    """Inverse de chiffrer_bytes : redécode le base64 standard, puis déchiffre le token Fernet."""
    token = base64.b64decode(contenu_b64, validate=True)
    return Fernet(cle).decrypt(token)


def chiffrer(t, cle):
    try:
        return Fernet(cle).encrypt(t.encode()).decode()
    except Exception:
        return t


def dechiffrer(t64, cle):
    try:
        return Fernet(cle).decrypt(t64.encode()).decode()
    except (InvalidToken, Exception):
        return "🔒 [Message chiffré — clé incorrecte]"


# ══════════════════════════════════════════════════════════════════════════════
#  Utilitaires d'affichage
# ══════════════════════════════════════════════════════════════════════════════

def clear():
    os.system("clear" if os.name != "nt" else "cls")


def beep():
    print("\a", end="", flush=True)


def get_C():
    return COULEURS.get(session.get("couleur", "cyan"), "\033[96m")


def get_theme():
    pt = session.get("premium_type")
    if pt == "fondateur":
        return ("\033[93m", "Fondateur 🏆", "Merci de faire partie de l'aventure")
    elif pt == "beta":
        return ("\033[92m", "Bêta Testeur 🧪", "Merci de tester TermChat avant tout le monde")
    elif pt == "annuel":
        return ("\033[95m", "Premium 💎", "Abonnement annuel · Support prio")
    elif pt == "mensuel" or session.get("premium"):
        return ("\033[96m", "Premium ✨", "Abonnement mensuel actif")
    else:
        return ("\033[97m", "Compte Gratuit", "")


def fmt(o):
    if o < 1024:
        return f"{o} o"
    elif o < 1024**2:
        return f"{o // 1024} Ko"
    else:
        return f"{o // 1024 // 1024} Mo"


def titre(t):
    C2 = get_C()
    print(f"\n{C2}{B}{'─' * 46}{Z}\n{C2}{B}  {t}{Z}\n{C2}{B}{'─' * 46}{Z}\n")


def succes(m):
    print(f"{V}{B}✅  {m}{Z}")


def erreur(m):
    print(f"{R}❌  {m}{Z}")


def info(m):
    print(f"{J}ℹ️   {m}{Z}")


def entree():
    input(f"\n{G}[Entrée pour continuer]{Z}")


def banniere():
    clear()
    if session.get("connecte"):
        couleur_t, label_t, extra_t = get_theme()
        ligne_extra = f"║   {extra_t:<43}║\n" if extra_t else ""
        print(f"""{couleur_t}{B}
 ╔══════════════════════════════════════════════╗
 ║   💬  TERMCHAT — {label_t:<28}║
{ligne_extra} ╚══════════════════════════════════════════════╝{Z}
 """)
    else:
        C2 = get_C()
        print(f"""{C2}{B}
 ╔══════════════════════════════════════════════╗
 ║                                              ║
 ║   💬   T E R M C H A T   v6.3              ║
 ║   Messagerie Mondiale pour Développeurs      ║
 ║   by Aboudev Labs 🇨🇮  · Sécurisé           ║
 ║                                              ║
 ╚══════════════════════════════════════════════╝{Z}
 """)


# ══════════════════════════════════════════════════════════════════════════════
#  Réseau
# ══════════════════════════════════════════════════════════════════════════════

def envoyer_cli(p):
    try:
        with rep_lock:
            reponses.clear()
        sock_cli.sendall((json.dumps(p, ensure_ascii=False) + "\n").encode())
    except Exception as e:
        erreur(f"Réseau: {e}")


def attendre(timeout=6):
    debut = time.time()
    while time.time() - debut < timeout:
        with rep_lock:
            if reponses:
                return reponses.pop(0)
        time.sleep(0.05)
    return None


def recevoir():
    global en_cours
    buf = ""
    while en_cours:
        try:
            chunk = sock_cli.recv(8192).decode("utf-8", errors="replace")
            if not chunk:
                en_cours = False
                break
            buf += chunk
            while "\n" in buf:
                ligne, buf = buf.split("\n", 1)
                ligne = ligne.strip()
                if not ligne:
                    continue
                try:
                    p = json.loads(ligne)
                except Exception:
                    continue
                if "type" in p:
                    afficher_entrant(p)
                else:
                    with rep_lock:
                        reponses.append(p)
        except Exception:
            if en_cours:
                print(f"\n{R}Connexion perdue.{Z}")
            en_cours = False
            break


def _sanitizer_nom_fichier(nom_f):
    """Nettoie strictement un nom de fichier reçu."""
    safe = "".join(c for c in (nom_f or "fichier") if c.isalnum() or c in "._-")
    safe = safe[:100] or "fichier"
    if ".." in safe or safe.startswith("."):
        safe = "fichier_suspect"
    return safe


def afficher_entrant(p):
    C2 = get_C()
    t = p.get("type", "")
    h = p.get("heure", "")

    if t == "message":
        num_exp = p.get("numero", "")
        texte = p.get("texte", "")
        if p.get("chiffre") and session.get("numero"):
            cle_auto = cles_partagees_cache.get(num_exp)
            phrase = phrases_secretes.get(num_exp)
            if cle_auto:
                texte = dechiffrer(texte, cle_auto)
            elif phrase:
                try:
                    texte = dechiffrer(
                        texte, generer_cle(session["numero"], num_exp, phrase)
                    )
                except Exception:
                    texte = "🔒 [Message chiffré — clé incorrecte]"
            else:
                texte = "🔒 [Message chiffré — ouvre la conversation pour établir la clé]"
        beep()
        reply = p.get("reply_to")
        _pt = p.get("premium_type")
        if _pt == "fondateur":
            badge_p = " 🏆"
        elif _pt == "annuel":
            badge_p = " 💎"
        elif p.get("premium"):
            badge_p = " ✨"
        else:
            badge_p = ""
        print(f"\n{V}{B}[{h}] 💬 {p.get('de', '?')}{badge_p} ({num_exp}){Z}")
        if reply:
            print(f"{G}     ↩️  {reply[:40]}{Z}")
        print(f"     {texte}")
        if p.get("chiffre"):
            print(f"{G}     🔐 Chiffré{Z}")
        print(f"{G}> {Z}", end="", flush=True)

    elif t == "typing":
        if p.get("actif"):
            print(f"\r{G}  ✍️  {p.get('de', '?')} écrit...{Z}    ", end="", flush=True)
        else:
            print(f"\r{' ' * 50}\r", end="", flush=True)

    elif t == "livre":
        print(f"\r{G}  ✓ Livre{Z}  ", end="", flush=True)

    elif t == "lu":
        print(f"\r{G}  ✓✓ Lu{Z}  ", end="", flush=True)

    elif t == "reaction":
        print(f"\n{J}  {p.get('emoji', '👍')} {p.get('de', '?')} a réagi{Z}")
        print(f"{G}> {Z}", end="", flush=True)

    elif t == "fichier":
        nom_f = p.get("nom_fichier", "fichier")
        taille = p.get("taille", 0)
        contenu_b64 = p.get("contenu", "")
        beep()
        print(f"\n{M}{B}[{h}] 📎 {p.get('de', '?')} → {nom_f} ({fmt(taille)}){Z}")

        if not contenu_b64:
            print(f"{R}     ❌ Aucun contenu reçu{Z}")
        elif taille > MAX_FILE_RECV or len(contenu_b64) > int(MAX_FILE_RECV * 1.4):
            print(f"{R}     ❌ Fichier trop volumineux rejeté (max {fmt(MAX_FILE_RECV)}){Z}")
        else:
            safe_name = _sanitizer_nom_fichier(nom_f)
            chemin = os.path.join(DOWNLOADS, safe_name)
            base_, ext = os.path.splitext(safe_name)
            c = 1
            while os.path.exists(chemin):
                chemin = os.path.join(DOWNLOADS, f"{base_}_{c}{ext}")
                c += 1
            try:
                data = base64.b64decode(contenu_b64, validate=True)
                if len(data) > MAX_FILE_RECV:
                    raise ValueError("Taille réelle trop grande")
                if p.get("chiffre"):
                    cle = obtenir_cle_partagee(p.get("numero", ""))
                    if not cle:
                        print(f"{R}     🔒 Fichier chiffré — ouvre la conversation pour établir la clé{Z}")
                        print(f"{G}> {Z}", end="", flush=True)
                        return
                    data = dechiffrer_bytes(data, cle)
                with open(chemin, "wb") as f:
                    f.write(data)
                print(f"{V}     ✅ {chemin}{Z}")
            except Exception as e:
                print(f"{R}     ❌ Fichier rejeté : {e}{Z}")
        print(f"{G}> {Z}", end="", flush=True)

    elif t == "vocal":
        nom_f = p.get("nom_fichier", "vocal.ogg")
        duree = p.get("duree", 0)
        contenu_b64 = p.get("contenu", "")
        beep()
        print(f"\n{M}{B}[{h}] 🎙️  {p.get('de', '?')} → Message vocal ({duree}s){Z}")

        if not contenu_b64:
            print(f"{R}     ❌ Aucun contenu reçu{Z}")
        elif len(contenu_b64) > int(MAX_FILE_RECV * 1.4):
            print(f"{R}     ❌ Vocal trop volumineux rejeté{Z}")
        else:
            safe_name = _sanitizer_nom_fichier(nom_f)
            chemin = os.path.join(DOWNLOADS, safe_name)
            try:
                data = base64.b64decode(contenu_b64, validate=True)
                if len(data) > MAX_FILE_RECV:
                    raise ValueError("Taille réelle trop grande")
                if p.get("chiffre"):
                    cle = obtenir_cle_partagee(p.get("numero", ""))
                    if not cle:
                        print(f"{R}     🔒 Vocal chiffré — ouvre la conversation pour établir la clé{Z}")
                        print(f"{G}> {Z}", end="", flush=True)
                        return
                    data = dechiffrer_bytes(data, cle)
                with open(chemin, "wb") as f:
                    f.write(data)
                print(f"{V}     ✅ {chemin}{Z}")
                print(f"{G}     ▶️  termux-media-player play {chemin}{Z}")
            except Exception as e:
                print(f"{R}     ❌ {e}{Z}")
        print(f"{G}> {Z}", end="", flush=True)

    elif t == "msg_groupe":
        beep()
        reply = p.get("reply_to")
        texte_g = p.get("texte", "")
        if p.get("chiffre"):
            id_g = p.get("id_groupe")
            epoch_g = p.get("epoch")
            cle_g = cles_groupes_cache.get(id_g, {}).get(epoch_g)
            if cle_g:
                try:
                    texte_g = dechiffrer(texte_g, cle_g)
                except Exception:
                    texte_g = "🔒 [Message de groupe chiffré — clé incorrecte]"
            else:
                # Ne jamais faire d'appel réseau bloquant ici : ce code tourne
                # dans le thread d'écoute, pas le thread principal. La clé sera
                # récupérée proprement via obtenir_cle_groupe() à l'ouverture
                # du groupe ou au prochain envoi.
                texte_g = "🔒 [Message de groupe chiffré — ouvre le groupe pour établir la clé]"
        print(f"\n{C2}{B}[{h}] 👥 [{p.get('groupe', '?')}] {p.get('de', '?')}{Z}")
        if reply:
            print(f"{G}     ↩️  {reply[:40]}{Z}")
        print(f"     {texte_g}")
        print(f"{G}> {Z}", end="", flush=True)

    elif t == "cle_groupe":
        # Nouvelle clé de groupe reçue en direct (rotation suite à un ajout de
        # membre) : on invalide le cache local, obtenir_cle_groupe() la
        # rechargera proprement (avec le createur) au prochain message.
        id_g = p.get("id_groupe")
        cles_groupes_cache.pop(id_g, None)

    elif t == "invitation_groupe":
        beep()
        print(f"\n{J}{B}📩 Ajouté au groupe '{p.get('groupe', '?')}' !{Z}")
        print(f"{G}> {Z}", end="", flush=True)

    elif t == "epingle":
        print(f"\n{J}{B}📌 [{p.get('groupe', '?')}] Épinglé: {p.get('texte', '')}{Z}")
        print(f"{G}> {Z}", end="", flush=True)

    elif t == "statut":
        icone = f"{V}🟢{Z}" if p.get("en_ligne") else f"{G}⚫{Z}"
        print(
            f"\n{G}  {icone} {p.get('nom', '?')} "
            f"{'en ligne' if p.get('en_ligne') else 'hors ligne'}{Z}"
        )
        print(f"{G}> {Z}", end="", flush=True)

    elif t == "statut_change":
        st = STATUTS_ICONS.get(p.get("statut", ""), "")
        print(f"\n{G}  {p.get('nom', '?')} → {st}{Z}")
        print(f"{G}> {Z}", end="", flush=True)

    elif t == "annonce":
        beep()
        beep()
        print(f"\n{J}{B}📢 ANNONCE [{h}]: {p.get('msg', '')}{Z}")
        print(f"{G}> {Z}", end="", flush=True)

    elif t == "message_admin":
        beep()
        beep()
        print(f"\n{M}{B}📩 MESSAGE ADMIN [{h}]: {p.get('msg', '')}{Z}")
        print(f"{G}> {Z}", end="", flush=True)

    elif t == "timeout":
        print(f"\n{J}⏱️  {p.get('msg', 'Déconnecté.')}{Z}")
        en_cours = False

    elif t == "kick":
        print(f"\n{R}{B}⛔ {p.get('msg', 'Déconnecté par admin.')}{Z}")
        en_cours = False

    elif t == "premium_active":
        session["premium"] = True
        session["premium_type"] = p.get("premium_type")
        exp_p = p.get("expire", "")
        beep()
        beep()
        print(f"\n{V}{B}🎉 {p.get('msg', 'Ton premium est actif!')}{Z}")
        if exp_p and exp_p != "jamais":
            print(f"{V}   Expire le: {exp_p[:10]}{Z}")
        print(f"{G}> {Z}", end="", flush=True)


# ══════════════════════════════════════════════════════════════════════════════
#  Menus
# ══════════════════════════════════════════════════════════════════════════════

def menu_accueil():
    banniere()
    C2 = get_C()
    print(f"  {C2}1{Z} — 🆕  Créer un compte")
    print(f"  {C2}2{Z} — 📱  Se connecter (numéro + mot de passe)")
    print(f"  {C2}3{Z} — 📧  Se connecter par email")
    print(f"  {C2}q{Z} — 🚪  Quitter\n")
    return input(f"{J}Choix: {Z}").strip().lower()


def menu_principal():
    banniere()
    C2 = get_C()
    nom = session.get("nom", "")
    num = session.get("numero", "")
    nl = session.get("non_lus", 0)
    st = STATUTS_ICONS.get(session.get("statut", "disponible"), "")
    badge = f" {R}[{nl} non lus]{Z}" if nl > 0 else ""
    admin = f" {J}[ADMIN]{Z}" if session.get("est_admin") else ""
    print(f"{C2}{B}┌─────────────────────────────────────────┐")
    print(f"│  👤  {nom:<15} {num:<20}│")
    print(f"└─────────────────────────────────────────┘{Z} {st}{badge}{admin}\n")
    print(f"  {C2}1{Z} — 💬  Messages")
    print(f"  {C2}2{Z} — 👥  Groupes")
    print(f"  {C2}3{Z} — ⭐  Favoris")
    if session.get("premium"):
        print(f"  {C2}4{Z} — 📎  Envoyer un fichier")
    print(f"  {C2}6{Z} — 🌐  En ligne")
    print(f"  {C2}7{Z} — 👤  Mon profil")
    print(f"  {C2}8{Z} — 😊  Statut")
    print(f"  {C2}9{Z} — 🎨  Couleur")
    print(f"  {C2}f{Z} — 💌  Feedback au développeur")
    print(f"  {C2}s{Z} — 🛡️   Sécurité")
    if session.get("est_admin"):
        print(f"  {C2}0{Z} — ⚙️   Panel Admin")
    print(f"  {C2}q{Z} — 🚪  Déconnecter\n")
    return input(f"{J}Choix: {Z}").strip().lower()


def inscrire():
    titre("🆕 CRÉER UN COMPTE")
    nom = input("Ton nom (2-20 car.): ").strip()
    if not nom:
        erreur("Nom requis.")
        entree()
        return
    pseudo = input(
        "Choisis un pseudo unique @ (3-20 car., lettre puis lettres/chiffres/_): "
    ).strip().lstrip("@")
    if not pseudo:
        erreur("Pseudo requis.")
        entree()
        return
    email = input(
        "Email (optionnel, pour te connecter aussi par email - Entrée pour passer): "
    ).strip()
    mdp = input("Mot de passe (min 12 car., 3 classes parmi minuscule/majuscule/chiffre/symbole): ").strip()
    if not mdp:
        erreur("Mot de passe requis.")
        entree()
        return
    mdp2 = input("Confirmer: ").strip()
    if mdp != mdp2:
        erreur("Les mots de passe ne correspondent pas.")
        entree()
        return
    print(f"\n{B}Choisis ton pays:{Z}\n")
    for k, (flag_nom, prefixe) in PAYS.items():
        print(f"  {k} — {flag_nom}  ({prefixe})")
    choix_pays = input("\nNuméro du pays: ").strip()
    if choix_pays not in PAYS:
        choix_pays = "1"
    _, prefixe = PAYS[choix_pays]
    envoyer_cli(
        {
            "action": "inscrire",
            "nom": nom,
            "mdp": mdp,
            "prefixe": prefixe,
            "pseudo": pseudo,
            "email": email,
        }
    )
    rep = attendre()
    if rep and rep.get("ok"):
        numero = rep.get("numero")
        pays = rep.get("pays", "")
        pseudo_ok = rep.get("pseudo", "")
        print(
            f"""
 {V}{B}╔══════════════════════════════════════════╗
 ║   ✅  Compte créé avec succès!           ║
 ╠══════════════════════════════════════════╣
 ║   👤  {nom:<36}║
 ║   @   {pseudo_ok:<36}║
 ║   📱  {numero:<36}║
 ║   🌍  {pays:<36}║
 ╚══════════════════════════════════════════╝{Z}
 {J}⚠️  Note bien ton numéro et ton pseudo — ce sont tes identifiants!{Z}
 """
        )
    else:
        erreur(rep.get("msg", "Erreur") if rep else "Pas de réponse.")
    entree()


def connecter_par_numero():
    titre("📱 CONNEXION PAR NUMÉRO")
    numero = input("Ton numéro: ").strip()
    mdp = input("Mot de passe: ").strip()
    envoyer_cli({"action": "connecter_numero", "numero": numero, "mdp": mdp})
    rep = attendre()
    if rep and rep.get("ok") and rep.get("totp_requis"):
        _demander_code_totp()
        return
    if rep and rep.get("ok"):
        _finaliser_connexion(rep)
        return
    erreur(rep.get("msg", "Erreur") if rep else "Pas de réponse.")
    entree()


def _demander_code_totp():
    print(f"\n{J}🔐 Authentification a deux facteurs requise.{Z}")
    tentatives = 0
    while tentatives < 3:
        code = input("Code TOTP (ou code de recuperation): ").strip()
        envoyer_cli({"action": "totp_verifier_connexion", "code": code})
        rep2 = attendre()
        if rep2 and rep2.get("ok"):
            _finaliser_connexion(rep2)
            return
        erreur(rep2.get("msg", "Erreur") if rep2 else "Pas de réponse.")
        tentatives += 1
    erreur("Trop de tentatives.")
    entree()


def connecter_par_email():
    titre("📧 CONNEXION PAR EMAIL")
    email = input("Ton email: ").strip()
    mdp = input("Mot de passe: ").strip()
    envoyer_cli({"action": "connecter_email", "email": email, "mdp": mdp})
    rep = attendre()
    if rep and rep.get("ok") and rep.get("totp_requis"):
        _demander_code_totp()
        return
    if rep and rep.get("ok"):
        _finaliser_connexion(rep)
        return
    erreur(rep.get("msg", "Erreur") if rep else "Pas de réponse.")
    entree()


def _finaliser_connexion(rep):
    if "nom" not in rep or "numero" not in rep:
        erreur("Réponse serveur incomplète. Réessaie de te connecter.")
        return
    session.update(
        {
            "connecte": True,
            "nom": rep.get("nom"),
            "numero": rep.get("numero"),
            "pays": rep.get("pays", ""),
            "bio": rep.get("bio", ""),
            "couleur": rep.get("couleur", "cyan"),
            "statut": rep.get("statut", "disponible"),
            "est_admin": rep.get("est_admin", False),
            "non_lus": rep.get("non_lus", 0),
            "a_pin": rep.get("a_pin", False),
            "pseudo": rep.get("pseudo", ""),
            "premium": rep.get("premium", False),
            "premium_type": rep.get("premium_type"),
            "role": rep.get("role"),
        }
    )
    global ma_cle_privee
    ma_cle_privee = charger_ou_creer_identite(session.get("numero"))
    try:
        envoyer_cli(
            {
                "action": "publier_cle_publique",
                "cle_publique": cle_publique_b64(ma_cle_privee),
            }
        )
    except Exception:
        pass
    attendre(3)

    if session.get("a_pin"):
        tentatives = 0
        while tentatives < 3:
            pin = input(f"\n{J}🔢 Code PIN requis: {Z}").strip()
            envoyer_cli({"action": "verifier_pin", "pin": pin})
            rep_pin = attendre()
            if rep_pin and rep_pin.get("ok"):
                break
            erreur("PIN incorrect.")
            tentatives += 1
        else:
            erreur("Trop de tentatives.")
            session["connecte"] = False
            return

    if not session.get("pseudo"):
        print(f"\n{J}⚠️  Ton compte n'a pas encore de pseudo (@handle).{Z}")
        print(
            f"{J}   C'est désormais requis pour que les autres puissent te trouver facilement.{Z}"
        )
        while True:
            pseudo = input(
                f"\n{J}Choisis ton pseudo @ (3-20 car., lettre puis lettres/chiffres/_): {Z}"
            ).strip().lstrip("@")
            if not pseudo:
                info("Tu pourras le définir plus tard depuis 'Mon profil'.")
                break
            envoyer_cli({"action": "definir_pseudo", "pseudo": pseudo})
            rep_p = attendre()
            if rep_p and rep_p.get("ok"):
                session["pseudo"] = rep_p.get("pseudo", pseudo)
                succes(rep_p.get("msg", "Pseudo enregistré!"))
                break
            else:
                erreur(rep_p.get("msg", "Erreur") if rep_p else "Pas de réponse.")

    nl = session.get("non_lus", 0)
    print(f"\n{V}{B}✅ Bienvenue {rep.get('nom')}!{Z}")
    if nl > 0:
        print(f"{J}📬 {nl} message(s) non lu(s)!{Z}")
    time.sleep(1)


def menu_messages():
    while en_cours and session.get("connecte"):
        titre("💬 MESSAGES")
        C2 = get_C()
        envoyer_cli({"action": "mes_conversations"})
        rep = attendre(8)
        convs = rep.get("conversations", []) if rep and rep.get("ok") else []
        if convs:
            print(f"{B}Conversations récentes:{Z}\n")
            for i, c in enumerate(convs, 1):
                badge = (
                    f" {R}[{c.get('non_lus', 0)}]{Z}" if c.get("non_lus", 0) > 0 else ""
                )
                dm = c.get("dernier_msg", "")
                print(
                    f"  {C2}{i}{Z} — {B}{c.get('nom', '?')}{Z}{G} ({c.get('numero', '')}){Z}{badge}"
                )
                print(f"     {G}{dm[:35]}  {c.get('heure', '')}{Z}")
            print()
        print(f"  {C2}n{Z} — ✏️   Nouvelle conversation")
        print(f"  {C2}r{Z} — 🔙  Retour\n")
        choix = input(f"{J}Choix: {Z}").strip().lower()
        if choix == "r":
            break
        elif choix == "n":
            nd = input("Numéro ou @pseudo du destinataire: ").strip()
            if nd:
                _ouvrir_chat(nd)
        elif choix.isdigit():
            idx = int(choix) - 1
            if 0 <= idx < len(convs):
                _ouvrir_chat(convs[idx].get("numero"))


def _ouvrir_chat(nd):
    if nd.startswith("@"):
        envoyer_cli({"action": "chercher", "pseudo": nd[1:]})
        rep = attendre()
        if not rep or not rep.get("ok"):
            erreur(rep.get("msg", "Introuvable.") if rep else "?")
            entree()
            return
        nd = rep.get("user", {}).get("numero")
        u = rep.get("user", {})
    else:
        envoyer_cli({"action": "chercher", "numero": nd})
        rep = attendre()
        if not rep or not rep.get("ok"):
            erreur(rep.get("msg", "Introuvable.") if rep else "?")
            entree()
            return
        u = rep.get("user", {})
        nd = u.get("numero", nd)

    st = STATUTS_ICONS.get(u.get("statut", "disponible"), "")
    chiffrer_msgs = False
    cle_chat = None
    cle_pub_pair = u.get("cle_publique")

    if cle_pub_pair and ma_cle_privee:
        try:
            cle_chat = deriver_cle_partagee(
                ma_cle_privee, cle_pub_pair, session.get("numero", ""), nd
            )
            cles_partagees_cache[nd] = cle_chat
            chiffrer_msgs = True
            succes("Chiffrement de bout en bout activé automatiquement 🔐")
        except Exception:
            chiffrer_msgs = False

    if not chiffrer_msgs:
        info(
            f"{u.get('nom', '?')} n'a pas encore de clé de chiffrement publiée "
            f"(ancienne version de TermChat)."
        )
        if (
            input(f"{J}Activer un chiffrement manuel de secours? (o/n): {Z}")
            .strip()
            .lower()
            == "o"
        ):
            phrase = input(
                f"{J}Phrase secrète partagée avec {u.get('nom', '?')} "
                f"(à se transmettre hors TermChat): {Z}"
            ).strip()
            if phrase:
                chiffrer_msgs = True
                cle_chat = generer_cle(session.get("numero", ""), nd, phrase)
                phrases_secretes[nd] = phrase
                succes("Chiffrement manuel activé 🔐")
            else:
                info("Phrase vide, chiffrement désactivé.")

    envoyer_cli({"action": "historique", "avec": nd, "limite": 20})
    rep_h = attendre(8)
    if rep_h and rep_h.get("ok"):
        hist = rep_h.get("historique", [])
        if hist:
            print(f"\n{G}── Historique récent ──────────────{Z}")
            for msg in hist:
                dt = msg.get("heure", "")[:16].replace("T", " ")
                moi_ = msg.get("de") == session.get("numero")
                col = get_C() if moi_ else V
                nom_s = "[Toi]" if moi_ else f"[{msg.get('nom_de', '?')}]"
                lu = " ✓✓" if (moi_ and msg.get("lu")) else (" ✓" if moi_ else "")
                texte = msg.get("texte", "")
                reply = msg.get("reply_to")
                if msg.get("chiffre") and msg.get("type") != "fichier":
                    if cle_chat:
                        texte = dechiffrer(texte, cle_chat) + " 🔐"
                    else:
                        texte = "🔒 [Chiffré — active le chiffrement pour lire]"
                if reply:
                    print(f"  {G}↩️  {reply[:30]}{Z}")
                print(f"{G}{dt}{Z} {col}{B}{nom_s}{Z}{lu} {texte}")

    print(f"\n{V}✅ {u.get('nom', '?')} — {st}{Z}")
    dernier_msg_id = None
    expire_prochain = None
    print(
        f"\n{G}exit | /fichier | /vocal | /auto N | /repondre | /reaction "
        f"| /rechercher | /effacer | /favori | /empreinte{Z}\n"
    )

    while en_cours and session.get("connecte"):
        try:
            texte = input(f"{B}[→ {u.get('nom', '?')}] > {Z}").strip()
        except Exception:
            break
        if texte.lower() == "exit":
            break
        if not texte:
            continue

        if texte.startswith("/fichier "):
            mid = _envoyer_fichier(nd, texte[9:].strip())
            if mid:
                dernier_msg_id = mid
            continue

        if texte.startswith("/vocal "):
            mid = _envoyer_vocal(nd, texte[7:].strip())
            if mid:
                dernier_msg_id = mid
            continue

        if texte.startswith("/payer "):
            parts = texte[7:].strip().split()
            if len(parts) < 2:
                erreur("Usage: /payer <code_transaction> <montant>")
            else:
                code_t, montant = parts[0], parts[1]
                envoyer_cli(
                    {
                        "action": "soumettre_paiement",
                        "code_transaction": code_t,
                        "montant": montant,
                    }
                )
                rep = attendre()
                if rep and rep.get("ok"):
                    succes(rep.get("msg", ""))
                else:
                    erreur(rep.get("msg", "?") if rep else "?")
            continue

        if texte == "/empreinte":
            if not cle_pub_pair or not ma_cle_privee:
                erreur("Chiffrement non actif pour cette conversation.")
            else:
                ma_pub = cle_publique_b64(ma_cle_privee)
                emp = calculer_empreinte_verification(ma_pub, cle_pub_pair)
                print(f"\n{J}🔐 Empreinte de verification (compare-la avec {nd} par un autre moyen):{Z}")
                print(f"{B}{emp}{Z}\n")
            continue

        if texte.startswith("/auto "):
            try:
                expire_prochain = int(texte.split()[1])
                info(f"Prochain message auto-détruit dans {expire_prochain}s.")
            except Exception:
                erreur("Usage: /auto 30")
            continue

        if texte == "/repondre":
            if not dernier_msg_id:
                info("Aucun message à répondre.")
                continue
            rt = input("Ta réponse: ").strip()
            if not rt:
                continue
            te = chiffrer(rt, cle_chat) if chiffrer_msgs else rt
            envoyer_cli(
                {
                    "action": "message",
                    "dest": nd,
                    "texte": te,
                    "chiffre": chiffrer_msgs,
                    "reply_to": dernier_msg_id,
                }
            )
            rep2 = attendre(3)
            if rep2 and rep2.get("ok"):
                dernier_msg_id = rep2.get("msg_id")
            elif rep2:
                erreur(rep2.get("msg", ""))
            continue

        if texte == "/reaction":
            if not dernier_msg_id:
                info("Aucun message.")
                continue
            emoji = input("Réaction (👍❤️😂😮😢): ").strip() or "👍"
            envoyer_cli(
                {
                    "action": "reaction",
                    "dest": nd,
                    "msg_id": dernier_msg_id,
                    "emoji": emoji,
                }
            )
            attendre(3)
            continue

        if texte == "/rechercher":
            mot = input("Mot clé: ").strip()
            envoyer_cli({"action": "rechercher_msg", "avec": nd, "mot": mot})
            rep2 = attendre(8)
            if rep2 and rep2.get("ok"):
                res = rep2.get("resultats", [])
                if not res:
                    info("Aucun résultat.")
                else:
                    for m in res:
                        print(
                            f"{G}{m.get('heure', '')[:16].replace('T', ' ')}{Z} "
                            f"{m.get('texte', '')}"
                        )
            continue

        if texte == "/effacer":
            envoyer_cli({"action": "effacer_historique", "avec": nd})
            rep2 = attendre()
            if rep2 and rep2.get("ok"):
                succes("Historique effacé.")
            continue

        if texte == "/favori":
            envoyer_cli({"action": "ajouter_favori", "numero": nd})
            rep2 = attendre()
            if rep2 and rep2.get("ok"):
                succes(rep2.get("msg", "Ajouté!"))
            continue

        if texte.startswith("/signaler"):
            raison = input(f"{R}🚩 Raison du signalement (harcelement, fraude, menace...): {Z}").strip()
            if raison:
                envoyer_cli({"action": "signaler", "numero": nd, "raison": raison, "msg_id": dernier_msg_id or ""})
                rep2 = attendre()
                if rep2 and rep2.get("ok"):
                    succes("Signalement envoyé à l'administration.")
                else:
                    erreur(rep2.get("msg", "Erreur") if rep2 else "?")
            continue

        envoyer_cli({"action": "typing", "dest": nd, "actif": True})
        te = chiffrer(texte, cle_chat) if chiffrer_msgs else texte
        paquet = {
            "action": "message",
            "dest": nd,
            "texte": te,
            "chiffre": chiffrer_msgs,
        }
        if expire_prochain:
            paquet["expire_secondes"] = expire_prochain
            print(f"{G}  ⏱️  Auto-destruction dans {expire_prochain}s{Z}")
            expire_prochain = None
        envoyer_cli(paquet)
        envoyer_cli({"action": "typing", "dest": nd, "actif": False})
        rep2 = attendre(3)
        if rep2 and rep2.get("ok"):
            dernier_msg_id = rep2.get("msg_id")
        elif rep2 and not rep2.get("ok"):
            erreur(rep2.get("msg", ""))
        envoyer_cli({"action": "marquer_lu", "avec": nd})


def envoyer_fichier_menu():
    titre("📎 ENVOYER UN FICHIER")
    nd = input("Numéro ou @pseudo du destinataire: ").strip()
    if nd.startswith("@"):
        envoyer_cli({"action": "chercher", "pseudo": nd[1:]})
    else:
        envoyer_cli({"action": "chercher", "numero": nd})
    rep = attendre()
    if not rep or not rep.get("ok"):
        erreur("Introuvable.")
        entree()
        return
    nd = rep.get("user", {}).get("numero")
    chemin = input("Chemin du fichier: ").strip()
    _envoyer_fichier(nd, chemin)
    entree()


def _envoyer_fichier(nd, chemin):
    chemin = os.path.expanduser(chemin)
    if not os.path.isfile(chemin):
        erreur(f"Introuvable: {chemin}")
        return None
    taille = os.path.getsize(chemin)
    if taille > MAX_FILE_SEND:
        erreur(f"Max {fmt(MAX_FILE_SEND)}.")
        return None
    nom_f = os.path.basename(chemin)
    print(f"{G}📤 Envoi {nom_f} ({fmt(taille)})...{Z}")
    cle = obtenir_cle_partagee(nd)
    try:
        with open(chemin, "rb") as f:
            raw = f.read()
        if cle:
            c64 = chiffrer_bytes(raw, cle).decode()
            chiffre = True
        else:
            c64 = base64.b64encode(raw).decode()
            chiffre = False
    except Exception as e:
        erreur(f"Lecture: {e}")
        return None
    envoyer_cli(
        {
            "action": "envoyer_fichier",
            "dest": nd,
            "nom_fichier": nom_f,
            "contenu": c64,
            "taille": len(base64.b64decode(c64)),
            "chiffre": chiffre,
        }
    )
    rep = attendre(20)
    if rep and rep.get("ok"):
        succes(rep.get("msg", "Envoyé!"))
        return rep.get("msg_id")
    else:
        erreur(rep.get("msg", "Erreur") if rep else "?")
        return None


def _envoyer_vocal(nd, chemin):
    chemin = os.path.expanduser(chemin)
    if not os.path.isfile(chemin):
        erreur(f"Introuvable: {chemin}")
        return None
    taille = os.path.getsize(chemin)
    if taille > MAX_FILE_SEND:
        erreur(f"Max {fmt(MAX_FILE_SEND)}.")
        return None
    print(f"{G}🎙️  Envoi vocal ({fmt(taille)})...{Z}")
    cle = obtenir_cle_partagee(nd)
    try:
        with open(chemin, "rb") as f:
            raw = f.read()
        if cle:
            c64 = chiffrer_bytes(raw, cle).decode()
            chiffre = True
        else:
            c64 = base64.b64encode(raw).decode()
            chiffre = False
    except Exception as e:
        erreur(f"Lecture: {e}")
        return None
    envoyer_cli(
        {
            "action": "envoyer_vocal",
            "dest": nd,
            "contenu": c64,
            "taille": len(base64.b64decode(c64)),
            "duree": 0,
            "chiffre": chiffre,
        }
    )
    rep = attendre(20)
    if rep and rep.get("ok"):
        succes(rep.get("msg", "Vocal envoyé!"))
        return rep.get("msg_id")
    else:
        erreur(rep.get("msg", "Erreur") if rep else "?")
        return None


def voir_favoris():
    titre("⭐ CONTACTS FAVORIS")
    envoyer_cli({"action": "mes_favoris"})
    rep = attendre()
    if not rep or not rep.get("ok"):
        erreur("Erreur.")
        entree()
        return
    favoris = rep.get("favoris", [])
    if not favoris:
        info("Aucun favori.")
    else:
        for f in favoris:
            st = STATUTS_ICONS.get(f.get("statut", "disponible"), "")
            print(f"  ⭐ {f.get('nom', '?')}  {G}{f.get('numero', '')}{Z}  {st}")
    entree()


def menu_groupes():
    while en_cours and session.get("connecte"):
        titre("👥 GROUPES")
        C2 = get_C()
        print(f"  {C2}1{Z} — 📋  Mes groupes")
        print(f"  {C2}2{Z} — ➕  Créer un groupe")
        print(f"  {C2}3{Z} — 💬  Entrer dans un groupe")
        print(f"  {C2}4{Z} — 👤  Ajouter un membre")
        print(f"  {C2}r{Z} — 🔙  Retour\n")
        choix = input(f"{J}Choix: {Z}").strip().lower()
        if choix == "1":
            envoyer_cli({"action": "mes_groupes"})
            rep = attendre()
            titre("📋 MES GROUPES")
            if not rep or not rep.get("ok"):
                erreur("Erreur.")
                entree()
                continue
            groupes = rep.get("groupes", [])
            if not groupes:
                info("Aucun groupe.")
            else:
                for g in groupes:
                    adm = f" {J}[Admin]{Z}" if g.get("createur") else ""
                    print(
                        f"  • {g.get('nom', '?')}{adm}  "
                        f"{G}{g.get('membres', 0)} membres — ID:{g.get('id', '')}{Z}"
                    )
            entree()
        elif choix == "2":
            nom = input("Nom du groupe: ").strip()
            if not nom:
                continue
            envoyer_cli({"action": "creer_groupe", "nom": nom})
            rep = attendre()
            if rep and rep.get("ok"):
                succes(f"Groupe '{nom}' créé!")
                print(f"   {G}ID: {rep.get('id_groupe')}{Z}")
                distribuer_cle_groupe(rep.get("id_groupe"), [session.get("numero", "")])
            else:
                erreur(rep.get("msg", "?") if rep else "?")
            entree()
        elif choix == "3":
            id_g = input("ID du groupe: ").strip()
            if not id_g:
                continue
            reply_id = None
            obtenir_cle_groupe(id_g)
            print(f"\n{G}exit | /epingler | /repondre{Z}\n")
            while True:
                try:
                    texte = input(f"{B}[Groupe] > {Z}").strip()
                except Exception:
                    break
                if texte.lower() == "exit":
                    break
                if not texte:
                    continue
                if texte == "/epingler":
                    msg = input("Message à épingler: ").strip()
                    envoyer_cli(
                        {
                            "action": "epingler_groupe",
                            "id_groupe": id_g,
                            "texte": msg,
                        }
                    )
                    attendre(3)
                    continue
                if texte == "/repondre":
                    rt = input("Répondre à (texte): ").strip()
                    reply_id = rt
                    info(f"Tu répondras à: {rt[:30]}")
                    continue
                epoch_g, cle_g = obtenir_cle_groupe(id_g)
                if cle_g:
                    texte_env = chiffrer(texte, cle_g)
                    chiffre_g = True
                else:
                    texte_env = texte
                    chiffre_g = False
                envoyer_cli(
                    {
                        "action": "msg_groupe",
                        "id_groupe": id_g,
                        "texte": texte_env,
                        "reply_to": reply_id,
                        "chiffre": chiffre_g,
                        "epoch": epoch_g,
                    }
                )
                reply_id = None
                rep = attendre(3)
                if rep and not rep.get("ok"):
                    erreur(rep.get("msg", ""))
        elif choix == "4":
            id_g = input("ID du groupe: ").strip()
            numero = input("Numéro du membre: ").strip()
            envoyer_cli(
                {"action": "ajouter_groupe", "id_groupe": id_g, "numero": numero}
            )
            rep = attendre()
            if rep and rep.get("ok"):
                succes(rep.get("msg", "Ajouté!"))
                envoyer_cli({"action": "membres_groupe", "id_groupe": id_g})
                rep_m = attendre()
                if rep_m and rep_m.get("ok"):
                    distribuer_cle_groupe(id_g, rep_m.get("membres", []))
            else:
                erreur(rep.get("msg", "?") if rep else "?")
            entree()
        elif choix == "r":
            break


def voir_en_ligne():
    titre("🌐 UTILISATEURS EN LIGNE")
    envoyer_cli({"action": "en_ligne"})
    rep = attendre()
    if not rep or not rep.get("ok"):
        erreur("Erreur.")
        entree()
        return
    users = rep.get("users", [])
    if not users:
        info("Personne d'autre en ligne.")
    else:
        print(f"{V}  {len(users)} en ligne:{Z}\n")
        for u in users:
            st = STATUTS_ICONS.get(u.get("statut", "disponible"), "")
            print(
                f"  🟢  {u.get('nom', '?')}  {G}{u.get('numero', '')}{Z}  {st}"
            )
    entree()


def mon_profil():
    titre("👤 MON PROFIL")
    st = STATUTS_ICONS.get(session.get("statut", "disponible"), "")
    print(f"  👤  Nom:    {B}{session.get('nom', '')}{Z}")
    pseudo_aff = (
        f"@{session.get('pseudo')}"
        if session.get("pseudo")
        else f"{J}(non défini){Z}"
    )
    print(f"  🏷️   Pseudo: {pseudo_aff}")
    print(f"  📱  N°:     {session.get('numero', '')} {V}✓{Z}")
    print(f"  🌍  Pays:   {G}{session.get('pays', '—')}{Z}")
    print(f"  📝  Bio:    {G}{session.get('bio', '—')}{Z}")
    print(f"  😊  Statut: {st}\n")

    if not session.get("pseudo"):
        if input("Définir ton pseudo maintenant? (o/n): ").strip().lower() == "o":
            pseudo = input(
                "Pseudo @ (3-20 car., lettre puis lettres/chiffres/_): "
            ).strip().lstrip("@")
            envoyer_cli({"action": "definir_pseudo", "pseudo": pseudo})
            rep = attendre()
            if rep and rep.get("ok"):
                session["pseudo"] = rep.get("pseudo", pseudo)
                succes(rep.get("msg", ""))
            else:
                erreur(rep.get("msg", "?") if rep else "?")

    if input("Modifier ta bio? (o/n): ").strip().lower() == "o":
        bio = input("Nouvelle bio (max 150): ").strip()[:150]
        envoyer_cli({"action": "modifier_bio", "bio": bio})
        rep = attendre()
        if rep and rep.get("ok"):
            session["bio"] = bio
            succes(rep.get("msg"))
        else:
            erreur(rep.get("msg", "?") if rep else "?")
    entree()


def changer_statut():
    titre("😊 CHANGER MON STATUT")
    statuts = [
        ("disponible", "🟢 Disponible"),
        ("occupe", "🟡 Occupe"),
        ("ne_pas_deranger", "🔴 Ne pas deranger"),
        ("absent", "⚫ Absent"),
    ]
    for i, (s, label) in enumerate(statuts, 1):
        print(f"  {i} — {label}")
    choix = input("\nChoix: ").strip()
    try:
        statut = statuts[int(choix) - 1][0]
        envoyer_cli({"action": "changer_statut", "statut": statut})
        rep = attendre()
        if rep and rep.get("ok"):
            session["statut"] = statut
            succes(rep.get("msg"))
        else:
            erreur(rep.get("msg", "?") if rep else "?")
    except Exception:
        erreur("Choix invalide.")
    entree()


def personnalisation():
    titre("🎨 PERSONNALISATION")
    couleurs = list(COULEURS.items())
    for i, (nom_c, code) in enumerate(couleurs, 1):
        print(f"  {code}{B}{i}{Z} — {code}{nom_c}{Z}")
    choix = input(f"\nChoix (1-{len(couleurs)}): ").strip()
    try:
        nom_c, _ = couleurs[int(choix) - 1]
        envoyer_cli({"action": "changer_couleur", "couleur": nom_c})
        rep = attendre()
        if rep and rep.get("ok"):
            session["couleur"] = nom_c
            succes(f"Couleur → {nom_c}!")
        else:
            erreur(rep.get("msg", "?") if rep else "?")
    except Exception:
        erreur("Choix invalide.")
    entree()


def envoyer_feedback():
    titre("💌 FEEDBACK AU DÉVELOPPEUR")
    print(f"{G}Un bug, une idée, une remarque ? Écris-la ici, elle sera{Z}")
    print(f"{G}transmise directement au développeur de TermChat.{Z}\n")
    texte = input("Ton message (max 500 car.): ").strip()
    if not texte:
        info("Message vide, annulé.")
        entree()
        return
    envoyer_cli({"action": "envoyer_feedback", "texte": texte})
    rep = attendre()
    if rep and rep.get("ok"):
        succes(rep.get("msg", "Envoyé!"))
    else:
        erreur(rep.get("msg", "Erreur") if rep else "Pas de réponse.")
    entree()


def menu_securite():
    while en_cours and session.get("connecte"):
        titre("🛡️  SÉCURITÉ")
        C2 = get_C()
        print(f"  {C2}1{Z} — 🔑  Changer mot de passe")
        print(f"  {C2}2{Z} — 🚫  Bloquer un utilisateur")
        print(f"  {C2}3{Z} — ✅  Débloquer un utilisateur")
        print(f"  {C2}4{Z} — 🔢  Code PIN")
        print(f"  {C2}5{Z} — 🗑️   Supprimer mon compte")
        print(f"  {C2}6{Z} — ⭐  Mon abonnement")
        print(f"  {C2}7{Z} — 🔓  Oublier ce serveur (reinitialiser la confiance TLS)")
        print(f"  {C2}8{Z} — 🔐  Authentification a deux facteurs (TOTP)")
        print(f"  {C2}r{Z} — 🔙  Retour\n")
        choix = input(f"{J}Choix: {Z}").strip().lower()

        if choix == "7":
            print(f"\n{J}⚠️  Ceci supprime les empreintes de certificats memorisees.{Z}")
            print(f"{J}   La prochaine connexion fera confiance au nouveau certificat sans avertissement.{Z}")
            conf = input(f"{R}Confirmer ? (oui/non): {Z}").strip().lower()
            if conf == "oui":
                try:
                    if os.path.exists(TLS_PIN_FILE):
                        os.remove(TLS_PIN_FILE)
                    succes("Confiance reinitialisee. Reconnecte-toi pour reenregistrer le certificat actuel.")
                except Exception as e:
                    erreur(f"Erreur: {e}")
            else:
                print(f"{G}Annule.{Z}")
            entree()
        elif choix == "1":
            ancien = input("Ancien mdp: ").strip()
            nouveau = input("Nouveau mdp: ").strip()
            confirm = input("Confirmer: ").strip()
            if nouveau != confirm:
                erreur("Ne correspondent pas.")
                entree()
                continue
            if len(nouveau) < 4:
                erreur("Min 4 caractères.")
                entree()
                continue
            envoyer_cli(
                {"action": "changer_mdp", "ancien": ancien, "nouveau": nouveau}
            )
            rep = attendre()
            if rep and rep.get("ok"):
                succes(rep.get("msg"))
            else:
                erreur(rep.get("msg", "?") if rep else "?")
            entree()

        elif choix == "2":
            numero = input("Numéro à bloquer: ").strip()
            envoyer_cli({"action": "bloquer", "numero": numero, "bloquer": True})
            rep = attendre()
            if rep and rep.get("ok"):
                succes(rep.get("msg"))
            else:
                erreur(rep.get("msg", "?") if rep else "?")
            entree()

        elif choix == "3":
            numero = input("Numéro à débloquer: ").strip()
            envoyer_cli({"action": "bloquer", "numero": numero, "bloquer": False})
            rep = attendre()
            if rep and rep.get("ok"):
                succes(rep.get("msg"))
            else:
                erreur(rep.get("msg", "?") if rep else "?")
            entree()

        elif choix == "4":
            print("  1 — Activer PIN  |  2 — Désactiver PIN")
            c2 = input("Choix: ").strip()
            if c2 == "1":
                pin = input("PIN (4 chiffres): ").strip()
                pin2 = input("Confirmer: ").strip()
                if pin != pin2:
                    erreur("Ne correspondent pas.")
                    entree()
                    continue
                envoyer_cli({"action": "definir_pin", "pin": pin})
                rep = attendre()
                if rep and rep.get("ok"):
                    session["a_pin"] = True
                    succes(rep.get("msg"))
                else:
                    erreur(rep.get("msg", "?") if rep else "?")
            elif c2 == "2":
                envoyer_cli({"action": "supprimer_pin"})
                rep = attendre()
                if rep and rep.get("ok"):
                    session["a_pin"] = False
                    succes(rep.get("msg"))
                else:
                    erreur(rep.get("msg", "?") if rep else "?")
            entree()

        elif choix == "8":
            print("  1 — Activer TOTP  |  2 — Desactiver TOTP")
            c2 = input("Choix: ").strip()
            if c2 == "1":
                envoyer_cli({"action": "totp_setup_demarrer"})
                rep = attendre()
                if not (rep and rep.get("ok")):
                    erreur(rep.get("msg", "?") if rep else "?")
                    entree()
                    continue
                secret = rep.get("secret", "")
                print(f"\n{J}🔐 Entre ce secret dans Google Authenticator (ou une app TOTP):{Z}")
                print(f"\n   {B}{secret}{Z}\n")
                print(f"{G}Une fois ajoute, l'app affichera un code a 6 chiffres.{Z}")
                code_confirm = input("Code de confirmation: ").strip()
                envoyer_cli({"action": "totp_setup_confirmer", "code": code_confirm})
                rep2 = attendre()
                if rep2 and rep2.get("ok"):
                    succes(rep2.get("msg", "TOTP active."))
                    codes_recup = rep2.get("codes_recuperation", [])
                    if codes_recup:
                        print(f"\n{R}{B}⚠️  NOTE CES CODES DE RECUPERATION MAINTENANT (usage unique, affiches une seule fois):{Z}\n")
                        for c in codes_recup:
                            print(f"   {B}{c}{Z}")
                        print()
                else:
                    erreur(rep2.get("msg", "?") if rep2 else "?")
            elif c2 == "2":
                mdp = input("Mot de passe: ").strip()
                code_totp = input("Code TOTP actuel: ").strip()
                envoyer_cli({"action": "totp_desactiver", "mdp": mdp, "code": code_totp})
                rep = attendre()
                if rep and rep.get("ok"):
                    succes(rep.get("msg"))
                else:
                    erreur(rep.get("msg", "?") if rep else "?")
            entree()

        elif choix == "5":
            print(f"{R}{B}⚠️  Action irréversible!{Z}\n")
            if input("Tape 'SUPPRIMER': ").strip() != "SUPPRIMER":
                info("Annulé.")
                entree()
                continue
            mdp = input("Mot de passe: ").strip()
            envoyer_cli({"action": "supprimer_compte", "mdp": mdp})
            rep = attendre()
            if rep and rep.get("ok"):
                succes("Compte supprimé.")
                session["connecte"] = False
                session["nom"] = None
                entree()
                break
            else:
                erreur(rep.get("msg", "?") if rep else "?")
                entree()

        elif choix == "6":
            envoyer_cli({"action": "verifier_mon_abonnement"})
            rep = attendre()
            titre("⭐ MON ABONNEMENT")
            if rep and rep.get("ok"):
                if rep.get("premium"):
                    pt = rep.get("premium_type", "?")
                    if pt == "fondateur":
                        print(f"  {J}🏆 Fondateur — premium à vie{Z}")
                    elif pt == "beta":
                        print(f"  {V}🧪 Bêta Testeur — premium à vie (merci !){Z}")
                    else:
                        exp = (rep.get("premium_expire") or "")[:10]
                        print(f"  {V}✅ Premium actif ({pt}){Z}")
                        print(f"  Expire le : {B}{exp}{Z}")
                else:
                    print(
                        f"  {G}Compte gratuit — limites: 5 contacts, pas de fichiers,{Z}"
                    )
                    print(
                        f"  {G}150 caractères max par message, groupes à 5 membres.{Z}"
                    )
                    print()
                    print(
                        f"  {J}Pour passer premium (500 FCFA/mois ou 8000 FCFA/an):{Z}"
                    )
                    print(
                        f"  1. Envoie le paiement via {B}Wave ou Moov{Z} au {B}+2250170404109{Z}"
                    )
                    print(
                        f"  2. Tape: {B}/payer <code_transaction> <montant>{Z} dans une conversation"
                    )
                    print(
                        f"  3. L'admin vérifie et active ton premium sous peu."
                    )
            else:
                erreur("Erreur.")
            entree()

        elif choix == "r":
            break


def panel_admin():
    if not session.get("est_admin"):
        titre("⚙️  ACCÈS ADMIN")
        code = input("Code admin: ").strip()
        envoyer_cli({"action": "admin_login", "code": code})
        rep = attendre()
        if not rep or not rep.get("ok"):
            erreur(rep.get("msg", "Code incorrect.") if rep else "?")
            entree()
            return
        session["est_admin"] = True
        session["role"] = rep.get("role")
        succes("Accès accordé!")

    OPTIONS_ADMIN = [
        ("1", "📊  Statistiques", {"moderator"}),
        ("2", "👥  Tous les utilisateurs", {"moderator"}),
        ("3", "📢  Broadcast", {"moderator"}),
        ("4", "⛔  Kick utilisateur", {"moderator"}),
        ("5", "💌  Feedback reçus", {"moderator"}),
        ("6", "⭐  Gérer premium (activer/désactiver)", {"payment_admin"}),
        ("7", "📩  Message à un utilisateur", {"moderator"}),
        ("8", "💰  Paiements en attente", {"payment_admin"}),
        ("9", "📜  Journal d'audit", set()),
        ("s", "🛡️  Surveillance connexions", set()),
        ("a", "🚨  Alertes sécurité", set()),
        ("c", "💬  Voir une conversation (modération)", set()),
        ("f", "📎  Fichiers uploadés", set()),
        ("g", "🚩  Signalements", {"moderator"}),
        ("p", "🔑  Gérer les rôles admin", set()),
    ]

    def _admin_a_acces(roles_autorises):
        role = session.get("role")
        return role == "super_admin" or role in roles_autorises

    while en_cours and session.get("connecte"):
        titre("⚙️  PANEL ADMIN")
        C2 = get_C()
        for cle, label, roles in OPTIONS_ADMIN:
            if _admin_a_acces(roles):
                print(f"  {C2}{cle}{Z} — {label}")
        print(f"  {C2}r{Z} — 🔙  Retour\n")
        choix = input(f"{J}Choix: {Z}").strip().lower()

        if choix == "1":
            envoyer_cli({"action": "admin_stats"})
            rep = attendre(10)
            if rep and rep.get("ok") and "stats" in rep:
                s = rep["stats"]
                titre("📊 STATISTIQUES")
                print(f"  👤 Utilisateurs  : {B}{s.get('utilisateurs', 0)}{Z}")
                print(f"  🟢 En ligne      : {B}{s.get('en_ligne', 0)}{Z}")
                print(f"  💬 Conversations : {B}{s.get('conversations', 0)}{Z}")
                print(f"  👥 Groupes       : {B}{s.get('groupes', 0)}{Z}")
            else:
                erreur(rep.get("msg", "Erreur") if rep else "Pas de réponse.")
            entree()

        elif choix == "2":
            envoyer_cli({"action": "admin_users"})
            rep = attendre(15)
            if rep and rep.get("ok"):
                titre("👥 UTILISATEURS")
                for u in rep.get("users", []):
                    st = f"{V}🟢{Z}" if u.get("en_ligne") else f"{G}⚫{Z}"
                    alerte = f" {R}⚠️  pays incoherent{Z}" if u.get("pays_incoherent") else ""
                    print(
                        f"  {st} {u.get('nom', '?'):<12} {u.get('numero', '')}  "
                        f"{G}{u.get('pays', '')}{Z}{alerte}"
                    )
                    print(f"     {G}Inscrit: {u.get('inscription', '')}{Z}")
            else:
                erreur("Erreur.")
            entree()

        elif choix == "3":
            msg = input("Message: ").strip()
            if not msg:
                continue
            envoyer_cli({"action": "admin_broadcast", "msg": msg})
            rep = attendre()
            if rep and rep.get("ok"):
                succes(rep.get("msg", "Envoyé!"))
            entree()

        elif choix == "4":
            numero = input("Numéro à kick: ").strip()
            envoyer_cli({"action": "admin_kick", "numero": numero})
            rep = attendre()
            if rep and rep.get("ok"):
                succes(rep.get("msg", ""))
            else:
                erreur(rep.get("msg", "?") if rep else "?")
            entree()

        elif choix == "7":
            numero = input("Numéro du destinataire: ").strip()
            texte = input("Message: ").strip()
            if not texte:
                continue
            envoyer_cli(
                {"action": "admin_message", "numero": numero, "texte": texte}
            )
            rep = attendre()
            if rep and rep.get("ok"):
                succes(rep.get("msg", ""))
            else:
                erreur(rep.get("msg", "?") if rep else "?")
            entree()

        elif choix == "8":
            envoyer_cli({"action": "admin_paiements_attente"})
            rep = attendre(10)
            if rep and rep.get("ok"):
                paie = rep.get("paiements", [])
                titre(f"💰 PAIEMENTS EN ATTENTE ({len(paie)})")
                if not paie:
                    print(f"  {G}Aucun paiement en attente.{Z}")
                else:
                    for pmt in paie:
                        print(
                            f"  {C2}[{pmt.get('id')}]{Z} {pmt.get('nom', '?')} "
                            f"({pmt.get('numero', '')})"
                        )
                        print(
                            f"     Code: {pmt.get('code_transaction', '')}  "
                            f"Montant: {pmt.get('montant', '')} FCFA  "
                            f"{G}{pmt.get('heure', '')}{Z}"
                        )
                    print()
                    pid = input("ID à traiter (vide pour annuler): ").strip()
                    if pid:
                        action_p = input(
                            "c = confirmer / r = rejeter: "
                        ).strip().lower()
                        if action_p == "c":
                            cible_p = input(
                                "Numéro de l'utilisateur: "
                            ).strip()
                            type_p = (
                                input("Type (mensuel/annuel/fondateur): ").strip()
                                or "mensuel"
                            )
                            envoyer_cli(
                                {
                                    "action": "admin_confirmer_paiement",
                                    "id": pid,
                                    "numero": cible_p,
                                    "type": type_p,
                                }
                            )
                            rep2 = attendre()
                            if rep2 and rep2.get("ok"):
                                succes(rep2.get("msg", ""))
                            else:
                                erreur(rep2.get("msg", "?") if rep2 else "?")
                        elif action_p == "r":
                            envoyer_cli(
                                {"action": "admin_rejeter_paiement", "id": pid}
                            )
                            rep2 = attendre()
                            if rep2 and rep2.get("ok"):
                                succes(rep2.get("msg", ""))
                            else:
                                erreur(rep2.get("msg", "?") if rep2 else "?")
            else:
                erreur("Erreur.")
            entree()

        elif choix == "9":
            envoyer_cli({"action": "admin_audit_log"})
            rep = attendre(10)
            if rep and rep.get("ok"):
                entries = rep.get("entries", [])
                titre(f"📜 JOURNAL D'AUDIT (30 dernieres actions)")
                if not entries:
                    print(f"  {G}Aucune action enregistree.{Z}")
                else:
                    for e in entries:
                        print(f"  {G}{e.get('heure','?')}{Z} — {C2}{e.get('admin','?')}{Z}")
                        print(f"     Action: {e.get('action','?')}  Cible: {e.get('cible','') or '-'}  {e.get('details','')}")
            else:
                erreur("Erreur.")
            entree()

        elif choix == "5":
            envoyer_cli({"action": "admin_feedback"})
            rep = attendre(10)
            if rep and rep.get("ok"):
                fb = rep.get("feedback", [])
                titre(f"💌 FEEDBACK REÇUS ({len(fb)})")
                if not fb:
                    print(f"  {G}Aucun feedback pour le moment.{Z}")
                for f in fb:
                    dt = f.get("heure", "")[:16].replace("T", " ")
                    print(
                        f"\n  {G}{dt}{Z} — {B}{f.get('nom', '?')}{Z} "
                        f"({f.get('numero', '?')})"
                    )
                    print(f"  {f.get('texte', '')}")
            else:
                erreur("Erreur.")
            entree()

        elif choix == "6":
            numero = input("Numéro du compte: ").strip()
            print(
                "  1 — Activer premium mensuel  |  2 — Activer premium annuel  |  3 — Désactiver"
            )
            c2 = input("Choix: ").strip()
            if c2 == "1":
                envoyer_cli(
                    {
                        "action": "admin_activer_premium",
                        "numero": numero,
                        "type": "mensuel",
                    }
                )
                rep = attendre()
                if rep and rep.get("ok"):
                    succes(rep.get("msg", ""))
                else:
                    erreur(rep.get("msg", "?") if rep else "?")
            elif c2 == "2":
                envoyer_cli(
                    {
                        "action": "admin_activer_premium",
                        "numero": numero,
                        "type": "annuel",
                    }
                )
                rep = attendre()
                if rep and rep.get("ok"):
                    succes(rep.get("msg", ""))
                else:
                    erreur(rep.get("msg", "?") if rep else "?")
            elif c2 == "3":
                envoyer_cli(
                    {"action": "admin_desactiver_premium", "numero": numero}
                )
                rep = attendre()
                if rep and rep.get("ok"):
                    succes(rep.get("msg", ""))
                else:
                    erreur(rep.get("msg", "?") if rep else "?")
            entree()

        elif choix == "s":
            envoyer_cli({"action": "admin_surveillance"})
            rep = attendre(8)
            titre("🛡️ SURVEILLANCE CONNEXIONS")
            if rep and rep.get("ok"):
                conns = rep.get("connexions", [])
                if not conns:
                    print(f"  {G}Aucune connexion active.{Z}")
                else:
                    print(f"  {B}{len(conns)} utilisateur(s) connecte(s):{Z}")
                    print()
                    for c in conns:
                        st = STATUTS_ICONS.get(c.get("statut","disponible"), "")
                        print(f"  🟢 {B}{c.get('nom','?')}{Z} {G}{c.get('numero','')}{Z}")
                        print(f"     IP: {J}{c.get('ip','?')}{Z}  Pays: {c.get('pays','?')}  Connecte: {c.get('heure_connexion','')}")
                        print(f"     {st}")
                        print()
            else:
                erreur("Erreur.")
            entree()

        elif choix == "a":
            envoyer_cli({"action": "admin_alertes_securite"})
            rep = attendre(10)
            titre("🚨 ALERTES SECURITE")
            if rep and rep.get("ok"):
                alerts = rep.get("alertes", [])
                if not alerts:
                    print(f"  {G}Aucune alerte recente.{Z}")
                else:
                    for a in alerts:
                        sev_color = R if a.get("severite") == "CRITIQUE" else J if a.get("severite") == "MOYEN" else G
                        print(f"  {sev_color}[{a.get('severite','?')}]{Z} {G}{a.get('heure','?')}{Z}")
                        print(f"     Type: {a.get('type','?')}  IP: {J}{a.get('ip','?')}{Z}")
                        print(f"     {a.get('details','')}")
                        print()
            else:
                erreur("Erreur.")
            entree()

        elif choix == "c":
            n1 = input("Numero 1: ").strip()
            n2 = input("Numero 2: ").strip()
            envoyer_cli({"action": "admin_voir_conversation", "numero1": n1, "numero2": n2})
            rep = attendre(10)
            titre("💬 CONVERSATION (MODERATION)")
            if rep and rep.get("ok"):
                print(f"  {R}⚠️ Accès reserve — donnees sensibles{Z}")
                entre_txt = rep.get('entre','')
                print(f"  Entre: {entre_txt}")
                print()
                for m in rep.get("historique", []):
                    dt = m.get("heure", "")[:16].replace("T", " ")
                    nom = m.get("nom_de", "?")
                    texte = m.get("texte", "")
                    chiffre = " 🔐" if m.get("chiffre") else ""
                    print(f"  {G}{dt}{Z} [{nom}]: {texte}{chiffre}")
            else:
                erreur(rep.get("msg", "Erreur") if rep else "?")
            entree()

        elif choix == "f":
            envoyer_cli({"action": "admin_voir_fichiers"})
            rep = attendre(8)
            titre("📎 FICHIERS UPLOADES")
            if rep and rep.get("ok"):
                fichiers = rep.get("fichiers", [])
                if not fichiers:
                    print(f"  {G}Aucun fichier recent.{Z}")
                else:
                    for f in fichiers:
                        taille = f"{f.get('taille',0)//1024} Ko" if f.get('taille',0) < 1024*1024 else f"{f.get('taille',0)//1024//1024} Mo"
                        print(f"  📎 {f.get('nom','?')}  {G}{taille}{Z}  {f.get('date','')}")
            else:
                erreur("Erreur.")
            entree()

        elif choix == "p":
            numero = input("Numéro du compte à gérer: ").strip()
            print(
                "  1 — super_admin  |  2 — moderator  |  3 — payment_admin  |  4 — Retirer l'accès admin"
            )
            c2 = input("Choix: ").strip()
            roles_map = {"1": "super_admin", "2": "moderator", "3": "payment_admin", "4": ""}
            if c2 in roles_map:
                envoyer_cli(
                    {"action": "admin_gerer_role", "numero": numero, "role": roles_map[c2]}
                )
                rep = attendre()
                if rep and rep.get("ok"):
                    succes(rep.get("msg", ""))
                else:
                    erreur(rep.get("msg", "?") if rep else "?")
            entree()

        elif choix == "g":
            envoyer_cli({"action": "admin_signalements"})
            rep = attendre(10)
            titre("🚩 SIGNALEMENTS UTILISATEURS")
            if rep and rep.get("ok"):
                sigs = rep.get("signalements", [])
                if not sigs:
                    print(f"  {G}Aucun signalement en attente.{Z}")
                else:
                    for s in sigs:
                        print(f"  {R}🚩{Z} {B}{s.get('signaleur','?')}{Z} signale {R}{s.get('cible','?')}{Z}")
                        print(f"     Raison: {s.get('raison','')}")
                        print(f"     {G}{s.get('heure','')}{Z}  IP: {s.get('ip','?')}")
                        print()
                    sid = input("ID a traiter (vide pour passer): ").strip()
                    if sid:
                        dec = input("Decision (archive/kick): ").strip()
                        envoyer_cli({"action": "admin_traiter_signalement", "id": sid, "decision": dec})
                        rep2 = attendre()
                        if rep2 and rep2.get("ok"):
                            succes(rep2.get("msg"))
                        else:
                            erreur(rep2.get("msg","?") if rep2 else "?")
            else:
                erreur("Erreur.")
            entree()

        elif choix == "r":
            break


def quitter(sig=None, frame=None):
    global en_cours
    en_cours = False
    if session.get("connecte"):
        try:
            envoyer_cli({"action": "deconnecter"})
        except Exception:
            pass
    try:
        sock_cli.close()
    except Exception:
        pass
    print(f"\n{get_C()}{B}À bientôt! 👋{Z}\n")
    sys.exit(0)

def main():
    global sock_cli, en_cours, ma_cle_privee

    banniere()

    host = sys.argv[1] if len(sys.argv) >= 2 else "altaria.proxy.rlwy.net"
    port = int(sys.argv[2]) if len(sys.argv) >= 3 else 20022

    print(f"{G}🔌 Connexion à {host}:{port}...{Z}")

    try:
        sock_cli = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock_cli.settimeout(10)
        sock_cli.connect((host, port))

        USE_TLS = os.environ.get("REQUIRE_TLS", "1") != "0"

        if USE_TLS:
            # TLS avec pinning TOFU + minimum TLS 1.2
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.minimum_version = ssl.TLSVersion.TLSv1_2
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            sock_tls = ctx.wrap_socket(sock_cli, server_hostname=host)
            empreinte = empreinte_certificat(sock_tls)

            if not verifier_confiance_tls(host, port, empreinte):
                erreur("Connexion refusée : empreinte du certificat non validée.")
                try:
                    sock_tls.close()
                except Exception:
                    pass
                sys.exit(1)

            sock_cli = sock_tls
            print(f"{G}🔐 Connexion chiffrée (TLS 1.2+ · certificat vérifié par pinning){Z}")

        else:
            print(f"{J}⚠️ Connexion TCP simple (TLS désactivé){Z}")

        sock_cli.settimeout(None)
        succes("Connecté !")
        print(f"{G}   📥 Fichiers → ~/termchat_downloads/{Z}\n")

    except SystemExit:
        raise

    except Exception as e:
        erreur(f"Impossible de se connecter : {e}")
        try:
            if sock_cli:
                sock_cli.close()
        except Exception:
            pass
        sys.exit(1)

    threading.Thread(target=recevoir, daemon=True).start()

    signal.signal(signal.SIGINT, quitter)
    try:
        signal.signal(signal.SIGTERM, quitter)
    except Exception:
        pass

    time.sleep(0.3)

    try:
        while en_cours:
            if not session["connecte"]:
                choix = menu_accueil()

                if choix == "1":
                    inscrire()
                elif choix == "2":
                    connecter_par_numero()
                elif choix == "3":
                    connecter_par_email()
                elif choix == "q":
                    quitter()
            else:
                # Rafraichir le statut premium a chaque retour au menu principal
                # (corrige l'affichage qui restait fige apres expiration)
                try:
                    envoyer_cli({"action": "verifier_mon_abonnement"})
                    rep_abo = attendre(4)
                    if rep_abo and rep_abo.get("ok"):
                        session["premium"] = rep_abo.get("premium", False)
                        session["premium_type"] = rep_abo.get("premium_type")
                except Exception:
                    pass
                choix = menu_principal()

                if choix == "1":
                    menu_messages()
                elif choix == "2":
                    menu_groupes()
                elif choix == "3":
                    voir_favoris()
                elif choix == "4":
                    envoyer_fichier_menu()
                elif choix == "6":
                    voir_en_ligne()
                elif choix == "7":
                    mon_profil()
                elif choix == "8":
                    changer_statut()
                elif choix == "9":
                    personnalisation()
                elif choix == "f":
                    envoyer_feedback()
                elif choix == "s":
                    menu_securite()
                elif choix == "0":
                    panel_admin()
                elif choix == "q":
                    quitter()

    except KeyboardInterrupt:
        quitter()

if __name__ == "__main__":
    main()
