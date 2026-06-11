#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════╗
║         TERMCHAT v4.0  — CLIENT                         ║
║         Messagerie Mondiale pour Développeurs            ║
║         by Aboudev Labs 🇨🇮                              ║
╚══════════════════════════════════════════════════════════╝

  Usage :
    python termchat.py                        → serveur local
    python termchat.py <host> <port>          → serveur distant (Render)

  Exemple Render :
    python termchat.py termchat.onrender.com 9999
"""

import socket, threading, json, os, base64
import datetime, time, sys, signal

# ══════════════════════════════════════════════════════════
#  COULEURS TERMINAL
# ══════════════════════════════════════════════════════════
V  = "\033[92m"   # vert
R  = "\033[91m"   # rouge
C  = "\033[96m"   # cyan
J  = "\033[93m"   # jaune
B  = "\033[1m"    # gras
Z  = "\033[0m"    # reset
G  = "\033[90m"   # gris
M  = "\033[95m"   # magenta
W  = "\033[97m"   # blanc
BL = "\033[94m"   # bleu

# ══════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════
DOWNLOADS = os.path.join(os.path.expanduser("~"), "termchat_downloads")
os.makedirs(DOWNLOADS, exist_ok=True)

# ══════════════════════════════════════════════════════════
#  PAYS SUPPORTÉS
# ══════════════════════════════════════════════════════════
PAYS = {
    "1":  ("🇨🇮  Côte d'Ivoire", "+225"),
    "2":  ("🇸🇳  Sénégal",       "+221"),
    "3":  ("🇲🇱  Mali",          "+223"),
    "4":  ("🇧🇫  Burkina Faso",  "+226"),
    "5":  ("🇬🇳  Guinée",        "+224"),
    "6":  ("🇹🇬  Togo",          "+228"),
    "7":  ("🇧🇯  Bénin",         "+229"),
    "8":  ("🇳🇪  Niger",         "+227"),
    "9":  ("🇨🇲  Cameroun",      "+237"),
    "10": ("🇨🇬  Congo",         "+242"),
    "11": ("🇬🇦  Gabon",         "+241"),
    "12": ("🇬🇭  Ghana",         "+233"),
    "13": ("🇳🇬  Nigeria",       "+234"),
    "14": ("🇫🇷  France",        "+33"),
    "15": ("🇧🇪  Belgique",      "+32"),
    "16": ("🇨🇦  Canada",        "+1"),
    "17": ("🇺🇸  USA",           "+1"),
    "18": ("🇲🇦  Maroc",         "+212"),
    "19": ("🇩🇿  Algérie",       "+213"),
    "20": ("🇹🇳  Tunisie",       "+216"),
}

# ══════════════════════════════════════════════════════════
#  ÉTAT DE SESSION
# ══════════════════════════════════════════════════════════
session = {
    "connecte": False,
    "nom":      None,
    "numero":   None,
    "pays":     None,
    "bio":      ""
}
sock_cli  = None
en_cours  = True
reponses  = []
rep_lock  = threading.Lock()

# ══════════════════════════════════════════════════════════
#  UTILITAIRES
# ══════════════════════════════════════════════════════════
def clear():
    os.system("clear" if os.name != "nt" else "cls")

def fmt_taille(o):
    if o < 1024:       return f"{o} o"
    elif o < 1024**2:  return f"{o//1024} Ko"
    else:              return f"{o//1024//1024} Mo"

def ligne(car="─", n=45):
    return car * n

def titre(texte):
    print(f"\n{C}{B}{ligne()}{Z}")
    print(f"{C}{B}  {texte}{Z}")
    print(f"{C}{B}{ligne()}{Z}\n")

def succes(msg):
    print(f"{V}{B}✅  {msg}{Z}")

def erreur(msg):
    print(f"{R}❌  {msg}{Z}")

def info(msg):
    print(f"{J}ℹ️   {msg}{Z}")

def entree(msg=""):
    input(f"\n{G}[Entrée pour continuer]{Z}")

# ══════════════════════════════════════════════════════════
#  BANNIÈRE
# ══════════════════════════════════════════════════════════
def banniere():
    clear()
    print(f"""
{C}{B}╔══════════════════════════════════════════════╗
║                                              ║
║   💬   T E R M C H A T   v4.0              ║
║   Messagerie Mondiale pour Développeurs      ║
║   by Aboudev Labs 🇨🇮                        ║
║                                              ║
╚══════════════════════════════════════════════╝{Z}
""")

# ══════════════════════════════════════════════════════════
#  COMMUNICATION RÉSEAU
# ══════════════════════════════════════════════════════════
def envoyer_cli(paquet):
    """Envoie un paquet JSON au serveur."""
    try:
        sock_cli.sendall((json.dumps(paquet, ensure_ascii=False) + "\n").encode())
    except Exception as e:
        erreur(f"Erreur réseau : {e}")

def attendre(timeout=6):
    """Attend une réponse du serveur."""
    debut = time.time()
    while time.time() - debut < timeout:
        with rep_lock:
            if reponses:
                return reponses.pop(0)
        time.sleep(0.05)
    return None

def recevoir():
    """Thread de réception des paquets du serveur."""
    global en_cours
    buf = ""
    while en_cours:
        try:
            chunk = sock_cli.recv(8192).decode("utf-8", errors="replace")
            if not chunk:
                en_cours = False; break
            buf += chunk
            while "\n" in buf:
                ligne_r, buf = buf.split("\n", 1)
                ligne_r = ligne_r.strip()
                if not ligne_r:
                    continue
                try:
                    p = json.loads(ligne_r)
                except:
                    continue
                if "type" in p:
                    afficher_entrant(p)   # message entrant en temps réel
                else:
                    with rep_lock:
                        reponses.append(p)
        except:
            if en_cours:
                print(f"\n{R}Connexion perdue.{Z}")
            en_cours = False
            break

def afficher_entrant(p):
    """Affiche un message/fichier reçu en temps réel."""
    t = p.get("type", "")
    h = p.get("heure", "")

    if t == "message":
        print(f"\n{V}{B}[{h}] 💬 {p.get('de','?')} ({p.get('numero','')}){Z}")
        print(f"     {p.get('texte','')}")
        print(f"{G}> {Z}", end="", flush=True)

    elif t == "fichier":
        nom_f  = p.get("nom_fichier", "fichier")
        taille = p.get("taille", 0)
        print(f"\n{M}{B}[{h}] 📎 {p.get('de','?')} → {nom_f} ({fmt_taille(taille)}){Z}")
        # Sauvegarde automatique
        chemin = os.path.join(DOWNLOADS, nom_f)
        base, ext = os.path.splitext(nom_f); c = 1
        while os.path.exists(chemin):
            chemin = os.path.join(DOWNLOADS, f"{base}_{c}{ext}"); c += 1
        try:
            with open(chemin, "wb") as f:
                f.write(base64.b64decode(p.get("contenu", "")))
            print(f"{V}     ✅ Sauvegardé : {chemin}{Z}")
        except Exception as e:
            print(f"{R}     ❌ Erreur : {e}{Z}")
        print(f"{G}> {Z}", end="", flush=True)

    elif t == "msg_groupe":
        print(f"\n{BL}{B}[{h}] 👥 [{p.get('groupe','?')}] {p.get('de','?')}{Z}")
        print(f"     {p.get('texte','')}")
        print(f"{G}> {Z}", end="", flush=True)

    elif t == "invitation_groupe":
        print(f"\n{J}{B}📩 Tu as été ajouté au groupe '{p.get('groupe','?')}' !{Z}")
        print(f"{G}> {Z}", end="", flush=True)

    elif t == "statut":
        nom      = p.get("nom", "?")
        en_ligne = p.get("en_ligne", False)
        icone    = f"{V}🟢{Z}" if en_ligne else f"{G}⚫{Z}"
        print(f"\n{G}  {icone} {nom} {'est en ligne' if en_ligne else 'est hors ligne'}{Z}")
        print(f"{G}> {Z}", end="", flush=True)

# ══════════════════════════════════════════════════════════
#  MENUS
# ══════════════════════════════════════════════════════════
def menu_accueil():
    banniere()
    print(f"  {C}1{Z} — 🆕  Créer un compte")
    print(f"  {C}2{Z} — 🔑  Se connecter")
    print(f"  {C}q{Z} — 🚪  Quitter\n")
    return input(f"{J}Choix : {Z}").strip().lower()

def menu_principal():
    banniere()
    num = session.get("numero", "")
    nom = session.get("nom", "")
    print(f"{C}{B}┌─────────────────────────────────────────┐")
    print(f"│  👤  {nom:<15}  {num}  🟢  │")
    print(f"└─────────────────────────────────────────┘{Z}\n")
    print(f"  {C}1{Z} — 💬  Messages privés")
    print(f"  {C}2{Z} — 👥  Groupes")
    print(f"  {C}3{Z} — 📎  Envoyer un fichier")
    print(f"  {C}4{Z} — 🔍  Chercher un utilisateur")
    print(f"  {C}5{Z} — 🌐  Utilisateurs en ligne")
    print(f"  {C}6{Z} — 👤  Mon profil")
    print(f"  {C}7{Z} — 🔑  Changer mot de passe")
    print(f"  {C}8{Z} — 🗑️   Supprimer mon compte")
    print(f"  {C}q{Z} — 🚪  Déconnecter\n")
    return input(f"{J}Choix : {Z}").strip().lower()

# ══════════════════════════════════════════════════════════
#  INSCRIPTION
# ══════════════════════════════════════════════════════════
def inscrire():
    titre("🆕 CRÉER UN COMPTE")

    nom = input(f"{W}Ton nom (2-20 car.)   : {Z}").strip()
    if not nom:
        erreur("Nom requis."); return
    mdp = input(f"{W}Mot de passe (min 4)  : {Z}").strip()
    if not mdp:
        erreur("Mot de passe requis."); return

    # Choix du pays
    print(f"\n{B}Choisis ton pays :{Z}\n")
    for k, (flag_nom, prefixe) in PAYS.items():
        print(f"  {C}{k:>2}{Z} — {flag_nom}  ({prefixe})")

    print()
    choix_pays = input(f"{W}Numéro du pays : {Z}").strip()
    if choix_pays not in PAYS:
        erreur("Choix invalide. Côte d'Ivoire par défaut.")
        choix_pays = "1"

    flag_nom, prefixe = PAYS[choix_pays]

    envoyer_cli({"action": "inscrire", "nom": nom, "mdp": mdp, "prefixe": prefixe})
    rep = attendre()

    if rep and rep.get("ok"):
        numero = rep["numero"]
        pays   = rep.get("pays", "")
        print(f"""
{V}{B}╔══════════════════════════════════════════╗
║   ✅  Compte créé avec succès !          ║
╠══════════════════════════════════════════╣
║                                          ║
║   👤  Nom    : {nom:<26}║
║   📱  N°     : {numero:<26}║
║   ✓   Statut : Compte vérifié            ║
║   🌍  Pays   : {pays:<26}║
║                                          ║
╚══════════════════════════════════════════╝{Z}

{J}⚠️  Partage ce numéro à tes amis !{Z}
{J}    Ils pourront te trouver avec ce numéro.{Z}
""")
        entree()
    else:
        erreur(rep.get("msg", "Erreur inconnue") if rep else "Pas de réponse du serveur.")
        entree()

# ══════════════════════════════════════════════════════════
#  CONNEXION
# ══════════════════════════════════════════════════════════
def connecter():
    titre("🔑 SE CONNECTER")
    nom = input(f"{W}Ton nom      : {Z}").strip()
    mdp = input(f"{W}Mot de passe : {Z}").strip()

    envoyer_cli({"action": "connecter", "nom": nom, "mdp": mdp})
    rep = attendre()

    if rep and rep.get("ok"):
        session.update({
            "connecte": True,
            "nom":      rep["nom"],
            "numero":   rep["numero"],
            "pays":     rep.get("pays", ""),
            "bio":      rep.get("bio", "")
        })
        print(f"\n{V}{B}✅ Bienvenue {rep['nom']} ! 🎉{Z}")
        print(f"{C}   Ton numéro : {rep['numero']}{Z}")
        time.sleep(1)
        return True
    else:
        erreur(rep.get("msg", "Erreur") if rep else "Pas de réponse.")
        entree()
        return False

# ══════════════════════════════════════════════════════════
#  CHERCHER UN UTILISATEUR
# ══════════════════════════════════════════════════════════
def chercher_user(retourner_user=False):
    titre("🔍 CHERCHER UN UTILISATEUR")
    numero = input(f"{W}Numéro à chercher : {Z}").strip()

    envoyer_cli({"action": "chercher", "numero": numero})
    rep = attendre()

    if rep and rep.get("ok"):
        u  = rep["user"]
        st = f"{V}🟢 En ligne{Z}" if u.get("en_ligne") else f"{G}⚫ Hors ligne{Z}"
        signe = f"{V}✓{Z}" if True else f"{R}✗{Z}"
        print(f"""
  👤  Nom    : {C}{B}{u['nom']}{Z}
  📱  N°     : {C}{u['numero']} {signe}{Z}
  🌍  Pays   : {G}{u.get('pays','—')}{Z}
  📝  Bio    : {G}{u.get('bio','—')}{Z}
  🔘  Statut : {st}
""")
        if retourner_user:
            return u
        entree()
    else:
        erreur(rep.get("msg", "Introuvable.") if rep else "Pas de réponse.")
        entree()
    return None

# ══════════════════════════════════════════════════════════
#  CHAT PRIVÉ
# ══════════════════════════════════════════════════════════
def chat_prive():
    titre("💬 MESSAGE PRIVÉ")
    nd = input(f"{W}Numéro du destinataire : {Z}").strip()

    envoyer_cli({"action": "chercher", "numero": nd})
    rep = attendre()
    if not rep or not rep.get("ok"):
        erreur(rep.get("msg", "Introuvable.") if rep else "?"); entree(); return

    u  = rep["user"]
    st = f"{V}🟢 En ligne{Z}" if u.get("en_ligne") else f"{G}⚫ Hors ligne{Z}"

    # Afficher l'historique récent
    envoyer_cli({"action": "historique", "avec": nd, "limite": 20})
    rep_hist = attendre(5)
    if rep_hist and rep_hist.get("ok"):
        hist = rep_hist.get("historique", [])
        if hist:
            print(f"\n{G}── Historique récent ──────────────────{Z}")
            for msg in hist:
                dt  = msg.get("heure", "")[:16].replace("T", " ")
                moi = msg.get("de") == session["numero"]
                nom_src = f"{C}[Toi]{Z}" if moi else f"{V}[{msg.get('nom_de','?')}]{Z}"
                ico = "📎 " if msg.get("type") == "fichier" else ""
                print(f"{G}{dt}{Z} {nom_src} {ico}{msg.get('texte','')}")

    print(f"\n{V}✅ {u['nom']} — {st}{Z}")
    if u.get("bio"):
        print(f"{G}   Bio : {u['bio']}{Z}")
    print(f"\n{G}  Commandes : 'exit' = retour | '/fichier chemin' = envoyer fichier{Z}\n")

    while True:
        try:
            texte = input(f"{B}[→ {u['nom']}] > {Z}").strip()
        except (KeyboardInterrupt, EOFError):
            break
        if texte.lower() == "exit":
            break
        if not texte:
            continue
        if texte.startswith("/fichier "):
            _envoyer_fichier(nd, texte[9:].strip()); continue

        envoyer_cli({"action": "message", "dest": nd, "texte": texte})
        rep = attendre(3)
        if rep and not rep.get("ok"):
            erreur(rep.get("msg", ""))

# ══════════════════════════════════════════════════════════
#  ENVOYER UN FICHIER
# ══════════════════════════════════════════════════════════
def envoyer_fichier_menu():
    titre("📎 ENVOYER UN FICHIER")
    nd = input(f"{W}Numéro du destinataire : {Z}").strip()
    envoyer_cli({"action": "chercher", "numero": nd})
    rep = attendre()
    if not rep or not rep.get("ok"):
        erreur("Destinataire introuvable."); entree(); return

    chemin = input(f"{W}Chemin du fichier      : {Z}").strip()
    _envoyer_fichier(nd, chemin)
    entree()

def _envoyer_fichier(nd, chemin):
    chemin = os.path.expanduser(chemin)
    if not os.path.isfile(chemin):
        erreur(f"Fichier introuvable : {chemin}"); return

    taille = os.path.getsize(chemin)
    if taille > 10 * 1024 * 1024:
        erreur(f"Max 10 MB. Taille : {fmt_taille(taille)}"); return

    nom_f = os.path.basename(chemin)
    print(f"{G}📤 Envoi de {nom_f} ({fmt_taille(taille)})...{Z}")

    try:
        with open(chemin, "rb") as f:
            c64 = base64.b64encode(f.read()).decode()
    except Exception as e:
        erreur(f"Lecture impossible : {e}"); return

    envoyer_cli({
        "action":       "envoyer_fichier",
        "dest":         nd,
        "nom_fichier":  nom_f,
        "contenu":      c64,
        "taille":       taille
    })
    rep = attendre(20)
    if rep and rep.get("ok"):
        succes(rep.get("msg", "Fichier envoyé !"))
    else:
        erreur(rep.get("msg", "Erreur") if rep else "Pas de réponse.")

# ══════════════════════════════════════════════════════════
#  GROUPES
# ══════════════════════════════════════════════════════════
def menu_groupes():
    while True:
        titre("👥 GROUPES")
        print(f"  {C}1{Z} — 📋  Mes groupes")
        print(f"  {C}2{Z} — ➕  Créer un groupe")
        print(f"  {C}3{Z} — 💬  Entrer dans un groupe")
        print(f"  {C}4{Z} — 👤  Ajouter un membre")
        print(f"  {C}r{Z} — 🔙  Retour\n")
        choix = input(f"{J}Choix : {Z}").strip().lower()

        if choix == "1":   mes_groupes()
        elif choix == "2": creer_groupe()
        elif choix == "3": chat_groupe()
        elif choix == "4": ajouter_membre()
        elif choix == "r": break

def mes_groupes():
    envoyer_cli({"action": "mes_groupes"})
    rep = attendre()
    if not rep or not rep.get("ok"):
        erreur("Impossible de charger les groupes."); entree(); return

    groupes = rep.get("groupes", [])
    titre("📋 MES GROUPES")
    if not groupes:
        info("Tu n'as aucun groupe pour l'instant.")
    else:
        for g in groupes:
            admin = f" {J}[Admin]{Z}" if g.get("createur") else ""
            print(f"  {C}•{Z} {g['nom']}{admin}  —  {G}{g['membres']} membres{Z}")
            print(f"    {G}ID : {g['id']}{Z}")
    entree()

def creer_groupe():
    titre("➕ CRÉER UN GROUPE")
    nom = input(f"{W}Nom du groupe : {Z}").strip()
    if not nom:
        erreur("Nom requis."); return

    envoyer_cli({"action": "creer_groupe", "nom": nom})
    rep = attendre()
    if rep and rep.get("ok"):
        succes(f"Groupe '{nom}' créé !")
        print(f"{C}   ID du groupe : {rep['id_groupe']}{Z}")
        info("Partage cet ID à tes amis pour qu'ils rejoignent le groupe.")
    else:
        erreur(rep.get("msg", "Erreur") if rep else "?")
    entree()

def chat_groupe():
    titre("💬 ENTRER DANS UN GROUPE")
    id_g = input(f"{W}ID du groupe : {Z}").strip()
    if not id_g:
        return

    print(f"\n{G}Tape tes messages. 'exit' pour revenir.{Z}\n")
    while True:
        try:
            texte = input(f"{B}[Groupe] > {Z}").strip()
        except (KeyboardInterrupt, EOFError):
            break
        if texte.lower() == "exit":
            break
        if not texte:
            continue

        envoyer_cli({"action": "msg_groupe", "id_groupe": id_g, "texte": texte})
        rep = attendre(3)
        if rep and not rep.get("ok"):
            erreur(rep.get("msg", ""))

def ajouter_membre():
    titre("👤 AJOUTER UN MEMBRE")
    id_g   = input(f"{W}ID du groupe    : {Z}").strip()
    numero = input(f"{W}Numéro du membre : {Z}").strip()

    envoyer_cli({"action": "ajouter_groupe", "id_groupe": id_g, "numero": numero})
    rep = attendre()
    if rep and rep.get("ok"):
        succes(rep.get("msg", "Membre ajouté !"))
    else:
        erreur(rep.get("msg", "Erreur") if rep else "?")
    entree()

# ══════════════════════════════════════════════════════════
#  UTILISATEURS EN LIGNE
# ══════════════════════════════════════════════════════════
def voir_en_ligne():
    titre("🌐 UTILISATEURS EN LIGNE")
    envoyer_cli({"action": "en_ligne"})
    rep = attendre()
    if not rep or not rep.get("ok"):
        erreur("Impossible de charger."); entree(); return

    users = rep.get("users", [])
    if not users:
        info("Aucun autre utilisateur en ligne.")
    else:
        print(f"{V}  {len(users)} utilisateur(s) en ligne :{Z}\n")
        for u in users:
            print(f"  {V}🟢{Z}  {C}{u['nom']}{Z}  —  {G}{u['numero']}{Z}")
    entree()

# ══════════════════════════════════════════════════════════
#  PROFIL
# ══════════════════════════════════════════════════════════
def mon_profil():
    titre("👤 MON PROFIL")
    num = session.get("numero", "")
    print(f"  👤  Nom    : {C}{B}{session.get('nom','')}{Z}")
    print(f"  📱  N°     : {C}{num} {V}✓{Z}")
    print(f"  🌍  Pays   : {G}{session.get('pays','—')}{Z}")
    print(f"  📝  Bio    : {G}{session.get('bio','—')}{Z}\n")

    if input(f"{W}Modifier ta bio ? (o/n) : {Z}").strip().lower() == "o":
        bio = input(f"{W}Nouvelle bio (max 150 car.) : {Z}").strip()[:150]
        envoyer_cli({"action": "modifier_bio", "bio": bio})
        rep = attendre()
        if rep and rep.get("ok"):
            session["bio"] = bio
            succes(rep["msg"])
        else:
            erreur(rep.get("msg", "?") if rep else "?")
    entree()

# ══════════════════════════════════════════════════════════
#  CHANGER MOT DE PASSE
# ══════════════════════════════════════════════════════════
def changer_mdp():
    titre("🔑 CHANGER MOT DE PASSE")
    ancien  = input(f"{W}Ancien mot de passe  : {Z}").strip()
    nouveau = input(f"{W}Nouveau mot de passe : {Z}").strip()
    confirm = input(f"{W}Confirmer            : {Z}").strip()

    if nouveau != confirm:
        erreur("Les mots de passe ne correspondent pas."); entree(); return
    if len(nouveau) < 4:
        erreur("Minimum 4 caractères."); entree(); return

    envoyer_cli({"action": "changer_mdp", "ancien": ancien, "nouveau": nouveau})
    rep = attendre()
    if rep and rep.get("ok"):
        succes(rep["msg"])
    else:
        erreur(rep.get("msg", "?") if rep else "?")
    entree()

# ══════════════════════════════════════════════════════════
#  SUPPRIMER COMPTE
# ══════════════════════════════════════════════════════════
def supprimer_compte():
    titre("🗑️  SUPPRIMER MON COMPTE")
    print(f"{R}{B}⚠️  Cette action est irréversible !{Z}\n")

    confirm = input(f"{R}Tape 'SUPPRIMER' pour confirmer : {Z}").strip()
    if confirm != "SUPPRIMER":
        info("Annulé."); entree(); return

    mdp = input(f"{W}Mot de passe : {Z}").strip()
    envoyer_cli({"action": "supprimer_compte", "mdp": mdp})
    rep = attendre()
    if rep and rep.get("ok"):
        succes("Compte supprimé définitivement.")
        session.update({"connecte": False, "nom": None, "numero": None})
    else:
        erreur(rep.get("msg", "?") if rep else "?")
    entree()

# ══════════════════════════════════════════════════════════
#  QUITTER
# ══════════════════════════════════════════════════════════
def quitter(sig=None, frame=None):
    global en_cours
    en_cours = False
    if session.get("connecte"):
        try:
            envoyer_cli({"action": "deconnecter"})
        except:
            pass
    try:
        sock_cli.close()
    except:
        pass
    print(f"\n{C}{B}À bientôt ! 👋{Z}\n")
    sys.exit(0)

# ══════════════════════════════════════════════════════════
#  POINT D'ENTRÉE
# ══════════════════════════════════════════════════════════
def main():
    global sock_cli, en_cours

    banniere()

    # Adresse du serveur
    host = sys.argv[1] if len(sys.argv) >= 2 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) >= 3 else 9999

    print(f"{G}🔌 Connexion au serveur {host}:{port}...{Z}")
    try:
        sock_cli = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock_cli.settimeout(10)
        sock_cli.connect((host, port))
        sock_cli.settimeout(None)
        succes(f"Connecté au serveur !")
        print(f"{G}   📥 Fichiers reçus → ~/termchat_downloads/{Z}\n")
    except Exception as e:
        erreur(f"Impossible de se connecter : {e}")
        print(f"\n{J}Usage : python termchat.py <host> <port>{Z}")
        sys.exit(1)

    # Lancer le thread de réception
    threading.Thread(target=recevoir, daemon=True).start()

    # Signaux
    signal.signal(signal.SIGINT, quitter)
    try:
        signal.signal(signal.SIGTERM, quitter)
    except:
        pass

    time.sleep(0.3)

    # Boucle principale
    try:
        while en_cours:
            if not session["connecte"]:
                choix = menu_accueil()
                if choix == "1":   inscrire()
                elif choix == "2": connecter()
                elif choix == "q": quitter()
            else:
                choix = menu_principal()
                if choix == "1":   chat_prive()
                elif choix == "2": menu_groupes()
                elif choix == "3": envoyer_fichier_menu()
                elif choix == "4": chercher_user()
                elif choix == "5": voir_en_ligne()
                elif choix == "6": mon_profil()
                elif choix == "7": changer_mdp()
                elif choix == "8": supprimer_compte()
                elif choix == "q": quitter()
    except KeyboardInterrupt:
        quitter()

if __name__ == "__main__":
    main()
