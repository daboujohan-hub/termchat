#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════╗
║         TERMCHAT v4.1  — CLIENT                         ║
║         by Aboudev Labs 🇨🇮                              ║
║  Nouveautés : Indicateurs, Notifs, Sécurité, Admin      ║
╚══════════════════════════════════════════════════════════╝
"""

import socket, threading, json, os, base64
import datetime, time, sys, signal, hashlib

# ══════════════════════════════════════════════════════════
#  COULEURS DISPONIBLES
# ══════════════════════════════════════════════════════════
COULEURS = {
    "cyan":    "\033[96m",
    "vert":    "\033[92m",
    "jaune":   "\033[93m",
    "magenta": "\033[95m",
    "bleu":    "\033[94m",
    "rouge":   "\033[91m",
    "blanc":   "\033[97m",
}
R  = "\033[91m"
B  = "\033[1m"
Z  = "\033[0m"
G  = "\033[90m"
V  = "\033[92m"
J  = "\033[93m"
M  = "\033[95m"

# ══════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════
DOWNLOADS = os.path.join(os.path.expanduser("~"), "termchat_downloads")
os.makedirs(DOWNLOADS, exist_ok=True)

PAYS = {
    "1":  ("🇨🇮  Côte d'Ivoire", "+225"), "2":  ("🇸🇳  Sénégal",      "+221"),
    "3":  ("🇲🇱  Mali",          "+223"), "4":  ("🇧🇫  Burkina Faso",  "+226"),
    "5":  ("🇬🇳  Guinée",        "+224"), "6":  ("🇹🇬  Togo",          "+228"),
    "7":  ("🇧🇯  Bénin",         "+229"), "8":  ("🇳🇪  Niger",         "+227"),
    "9":  ("🇨🇲  Cameroun",      "+237"), "10": ("🇨🇬  Congo",         "+242"),
    "11": ("🇬🇦  Gabon",         "+241"), "12": ("🇬🇭  Ghana",         "+233"),
    "13": ("🇳🇬  Nigeria",       "+234"), "14": ("🇫🇷  France",        "+33"),
    "15": ("🇧🇪  Belgique",      "+32"),  "16": ("🇨🇦  Canada",        "+1"),
    "17": ("🇺🇸  USA",           "+1"),   "18": ("🇲🇦  Maroc",         "+212"),
    "19": ("🇩🇿  Algérie",       "+213"), "20": ("🇹🇳  Tunisie",       "+216"),
}

# ══════════════════════════════════════════════════════════
#  SESSION
# ══════════════════════════════════════════════════════════
session = {
    "connecte": False, "nom": None, "numero": None,
    "pays": None, "bio": "", "couleur": "cyan",
    "est_admin": False, "non_lus": 0
}
sock_cli  = None
en_cours  = True
reponses  = []
rep_lock  = threading.Lock()
C         = "\033[96m"   # couleur dynamique (mise à jour au login)

# ══════════════════════════════════════════════════════════
#  CHIFFREMENT
# ══════════════════════════════════════════════════════════
def generer_cle(n1, n2):
    base = "".join(sorted([n1, n2]))
    return hashlib.sha256(base.encode()).hexdigest()

def chiffrer(texte, cle):
    try:
        octets = texte.encode("utf-8")
        cle_b  = (cle * ((len(octets) // len(cle)) + 1)).encode("utf-8")
        xored  = bytes(a ^ b for a, b in zip(octets, cle_b))
        return base64.b64encode(xored).decode("utf-8")
    except: return texte

def dechiffrer(texte_b64, cle):
    try:
        octets = base64.b64decode(texte_b64.encode("utf-8"))
        cle_b  = (cle * ((len(octets) // len(cle)) + 1)).encode("utf-8")
        xored  = bytes(a ^ b for a, b in zip(octets, cle_b))
        return xored.decode("utf-8")
    except: return texte_b64

# ══════════════════════════════════════════════════════════
#  UTILITAIRES
# ══════════════════════════════════════════════════════════
def clear():   os.system("clear" if os.name != "nt" else "cls")
def beep():    print("\a", end="", flush=True)   # son notification

def get_C():   return COULEURS.get(session.get("couleur","cyan"), "\033[96m")

def fmt(o):
    if o < 1024:      return f"{o} o"
    elif o < 1024**2: return f"{o//1024} Ko"
    else:             return f"{o//1024//1024} Mo"

def ligne(n=46): return "─" * n

def titre(texte):
    C2 = get_C()
    print(f"\n{C2}{B}{ligne()}{Z}")
    print(f"{C2}{B}  {texte}{Z}")
    print(f"{C2}{B}{ligne()}{Z}\n")

def succes(msg): print(f"{V}{B}✅  {msg}{Z}")
def erreur(msg): print(f"{R}❌  {msg}{Z}")
def info(msg):   print(f"{J}ℹ️   {msg}{Z}")
def entree():    input(f"\n{G}[Entrée pour continuer]{Z}")

# ══════════════════════════════════════════════════════════
#  BANNIÈRE
# ══════════════════════════════════════════════════════════
def banniere():
    clear()
    C2 = get_C()
    print(f"""
{C2}{B}╔══════════════════════════════════════════════╗
║                                              ║
║   💬   T E R M C H A T   v4.1              ║
║   Messagerie Mondiale pour Développeurs      ║
║   by Aboudev Labs 🇨🇮                        ║
║                                              ║
╚══════════════════════════════════════════════╝{Z}
""")

# ══════════════════════════════════════════════════════════
#  RÉSEAU
# ══════════════════════════════════════════════════════════
def envoyer_cli(paquet):
    try: sock_cli.sendall((json.dumps(paquet, ensure_ascii=False)+"\n").encode())
    except Exception as e: erreur(f"Réseau : {e}")

def attendre(timeout=6):
    debut = time.time()
    while time.time()-debut < timeout:
        with rep_lock:
            if reponses: return reponses.pop(0)
        time.sleep(0.05)
    return None

def recevoir():
    global en_cours
    buf = ""
    while en_cours:
        try:
            chunk = sock_cli.recv(8192).decode("utf-8", errors="replace")
            if not chunk: en_cours=False; break
            buf += chunk
            while "\n" in buf:
                ligne_r, buf = buf.split("\n",1)
                ligne_r = ligne_r.strip()
                if not ligne_r: continue
                try:    p = json.loads(ligne_r)
                except: continue
                if "type" in p: afficher_entrant(p)
                else:
                    with rep_lock: reponses.append(p)
        except:
            if en_cours: print(f"\n{R}Connexion perdue.{Z}")
            en_cours=False; break

def afficher_entrant(p):
    C2 = get_C()
    t  = p.get("type","")
    h  = p.get("heure","")

    if t == "message":
        num_exp = p.get("numero","")
        texte   = p.get("texte","")
        # Déchiffrer si nécessaire
        if p.get("chiffre") and session.get("numero"):
            cle    = generer_cle(session["numero"], num_exp)
            texte  = dechiffrer(texte, cle)
        beep()
        print(f"\n{V}{B}[{h}] 💬 {p.get('de','?')} ({num_exp}){Z}")
        print(f"     {texte}")
        if p.get("chiffre"): print(f"{G}     🔐 Chiffré{Z}")
        print(f"{G}> {Z}", end="", flush=True)

    elif t == "typing":
        if p.get("actif"):
            print(f"\r{G}  ✍️  {p.get('de','?')} est en train d'écrire...{Z}    ", end="", flush=True)
        else:
            print(f"\r{' '*50}\r", end="", flush=True)

    elif t == "livre":
        print(f"\r{G}  ✓ Livré{Z}  ", end="", flush=True)

    elif t == "lu":
        print(f"\r{G}  ✓✓ Lu{Z}  ", end="", flush=True)

    elif t == "fichier":
        nom_f  = p.get("nom_fichier","fichier")
        taille = p.get("taille",0)
        beep()
        print(f"\n{M}{B}[{h}] 📎 {p.get('de','?')} → {nom_f} ({fmt(taille)}){Z}")
        chemin = os.path.join(DOWNLOADS, nom_f)
        base_, ext = os.path.splitext(nom_f); c=1
        while os.path.exists(chemin):
            chemin=os.path.join(DOWNLOADS,f"{base_}_{c}{ext}"); c+=1
        try:
            with open(chemin,"wb") as f: f.write(base64.b64decode(p.get("contenu","")))
            print(f"{V}     ✅ Sauvegardé : {chemin}{Z}")
        except Exception as e:
            print(f"{R}     ❌ {e}{Z}")
        print(f"{G}> {Z}", end="", flush=True)

    elif t == "msg_groupe":
        beep()
        print(f"\n{C2}{B}[{h}] 👥 [{p.get('groupe','?')}] {p.get('de','?')}{Z}")
        print(f"     {p.get('texte','')}")
        print(f"{G}> {Z}", end="", flush=True)

    elif t == "invitation_groupe":
        beep()
        print(f"\n{J}{B}📩 Tu as été ajouté au groupe '{p.get('groupe','?')}' !{Z}")
        print(f"{G}> {Z}", end="", flush=True)

    elif t == "statut":
        en_ligne = p.get("en_ligne",False)
        icone    = f"{V}🟢{Z}" if en_ligne else f"{G}⚫{Z}"
        print(f"\n{G}  {icone} {p.get('nom','?')} {'en ligne' if en_ligne else 'hors ligne'}{Z}")
        print(f"{G}> {Z}", end="", flush=True)

    elif t == "annonce":
        beep(); beep()
        print(f"\n{J}{B}📢 ANNONCE [{h}] : {p.get('msg','')}{Z}")
        print(f"{G}> {Z}", end="", flush=True)

    elif t == "timeout":
        print(f"\n{J}⏱️  {p.get('msg','Déconnecté pour inactivité.')}{Z}")
        en_cours = False

    elif t == "kick":
        print(f"\n{R}{B}⛔ {p.get('msg','Déconnecté par l\'admin.')}{Z}")
        en_cours = False

# ══════════════════════════════════════════════════════════
#  MENUS
# ══════════════════════════════════════════════════════════
def menu_accueil():
    banniere()
    C2 = get_C()
    print(f"  {C2}1{Z} — 🆕  Créer un compte")
    print(f"  {C2}2{Z} — 🔑  Se connecter")
    print(f"  {C2}q{Z} — 🚪  Quitter\n")
    return input(f"{J}Choix : {Z}").strip().lower()

def menu_principal():
    banniere()
    C2  = get_C()
    num = session.get("numero","")
    nom = session.get("nom","")
    nl  = session.get("non_lus",0)
    badge = f" {R}[{nl} non lus]{Z}" if nl > 0 else ""
    admin = f" {J}[ADMIN]{Z}" if session.get("est_admin") else ""
    print(f"{C2}{B}┌─────────────────────────────────────────┐")
    print(f"│  👤  {nom:<15} 🟢  En ligne          │")
    print(f"│  📱  {num:<39}│")
    print(f"└─────────────────────────────────────────┘{Z}{badge}{admin}\n")
    print(f"  {C2}1{Z} — 💬  Messages privés")
    print(f"  {C2}2{Z} — 👥  Groupes")
    print(f"  {C2}3{Z} — 📎  Envoyer un fichier")
    print(f"  {C2}4{Z} — 🔍  Chercher un utilisateur")
    print(f"  {C2}5{Z} — 🌐  Utilisateurs en ligne")
    print(f"  {C2}6{Z} — 👤  Mon profil")
    print(f"  {C2}7{Z} — 🎨  Personnalisation")
    print(f"  {C2}8{Z} — 🔑  Changer mot de passe")
    print(f"  {C2}9{Z} — 🛡️   Sécurité")
    if session.get("est_admin"):
        print(f"  {C2}0{Z} — ⚙️   Panel Admin")
    print(f"  {C2}q{Z} — 🚪  Déconnecter\n")
    return input(f"{J}Choix : {Z}").strip().lower()

# ══════════════════════════════════════════════════════════
#  INSCRIPTION
# ══════════════════════════════════════════════════════════
def inscrire():
    titre("🆕 CRÉER UN COMPTE")
    nom = input(f"Ton nom (2-20 car.)   : ").strip()
    if not nom: erreur("Nom requis."); return
    mdp = input(f"Mot de passe (min 4)  : ").strip()
    if not mdp: erreur("Mot de passe requis."); return

    print(f"\n{B}Choisis ton pays :{Z}\n")
    for k,(flag_nom,prefixe) in PAYS.items():
        print(f"  {k:>2} — {flag_nom}  ({prefixe})")
    choix_pays = input(f"\nNuméro du pays : ").strip()
    if choix_pays not in PAYS: choix_pays = "1"
    flag_nom, prefixe = PAYS[choix_pays]

    envoyer_cli({"action":"inscrire","nom":nom,"mdp":mdp,"prefixe":prefixe})
    rep = attendre()
    if rep and rep.get("ok"):
        numero = rep["numero"]
        pays   = rep.get("pays","")
        C2 = get_C()
        print(f"""
{V}{B}╔══════════════════════════════════════════╗
║   ✅  Compte créé avec succès !          ║
╠══════════════════════════════════════════╣
║                                          ║
║   👤  {nom:<36}║
║   📱  {numero:<36}║
║   ✓   Compte vérifié                     ║
║   🌍  {pays:<36}║
║                                          ║
╚══════════════════════════════════════════╝{Z}

{J}⚠️  Partage ce numéro à tes amis !{Z}
""")
    else:
        erreur(rep.get("msg","Erreur") if rep else "Pas de réponse.")
    entree()

# ══════════════════════════════════════════════════════════
#  CONNEXION
# ══════════════════════════════════════════════════════════
def connecter():
    global C
    titre("🔑 SE CONNECTER")
    nom = input(f"Ton nom      : ").strip()
    mdp = input(f"Mot de passe : ").strip()
    envoyer_cli({"action":"connecter","nom":nom,"mdp":mdp})
    rep = attendre()
    if rep and rep.get("ok"):
        session.update({
            "connecte":  True, "nom": rep["nom"],
            "numero":    rep["numero"], "pays": rep.get("pays",""),
            "bio":       rep.get("bio",""), "couleur": rep.get("couleur","cyan"),
            "est_admin": rep.get("est_admin",False),
            "non_lus":   rep.get("non_lus",0)
        })
        C = get_C()
        nl = session["non_lus"]
        print(f"\n{V}{B}✅ Bienvenue {rep['nom']} !{Z}")
        if nl > 0: print(f"{J}📬 Tu as {nl} message(s) non lu(s) !{Z}")
        time.sleep(1)
        return True
    erreur(rep.get("msg","Erreur") if rep else "Pas de réponse.")
    entree()
    return False

# ══════════════════════════════════════════════════════════
#  CHAT PRIVÉ
# ══════════════════════════════════════════════════════════
def chat_prive():
    titre("💬 MESSAGE PRIVÉ")
    nd = input(f"Numéro du destinataire : ").strip()
    envoyer_cli({"action":"chercher","numero":nd})
    rep = attendre()
    if not rep or not rep.get("ok"):
        erreur(rep.get("msg","Introuvable.") if rep else "?"); entree(); return

    u  = rep["user"]
    st = f"{V}🟢 En ligne{Z}" if u.get("en_ligne") else f"{G}⚫ Hors ligne{Z}"

    # Historique
    envoyer_cli({"action":"historique","avec":nd,"limite":20})
    rep_h = attendre(5)
    if rep_h and rep_h.get("ok"):
        hist = rep_h.get("historique",[])
        if hist:
            print(f"\n{G}── Historique récent ──────────────{Z}")
            for msg in hist:
                dt  = msg.get("heure","")[:16].replace("T"," ")
                moi = msg.get("de") == session["numero"]
                nom_s = f"[Toi]" if moi else f"[{msg.get('nom_de','?')}]"
                col   = get_C() if moi else V
                ico   = "📎 " if msg.get("type")=="fichier" else ""
                lu    = " ✓✓" if (moi and msg.get("lu")) else (" ✓" if moi else "")
                texte = msg.get("texte","")
                if msg.get("chiffre") and not msg.get("type")=="fichier":
                    cle   = generer_cle(session["numero"], nd)
                    texte = dechiffrer(texte, cle) + " 🔐"
                print(f"{G}{dt}{Z} {col}{B}{nom_s}{Z}{lu} {ico}{texte}")

    print(f"\n{V}✅ {u['nom']} — {st}{Z}")
    if u.get("bio"): print(f"{G}   Bio : {u['bio']}{Z}")

    # Options chiffrement
    chiffrer_msgs = False
    if input(f"\n{J}Activer le chiffrement ? (o/n) : {Z}").strip().lower() == "o":
        chiffrer_msgs = True
        cle_chat = generer_cle(session["numero"], nd)
        succes("Chiffrement activé 🔐")

    print(f"\n{G}  exit = retour | /fichier chemin = envoyer | /effacer = supprimer historique | /bloquer = bloquer{Z}\n")

    typing_timer = None

    def envoyer_typing(actif):
        envoyer_cli({"action":"typing","dest":nd,"actif":actif})

    while True:
        try:    texte = input(f"{B}[→ {u['nom']}] > {Z}").strip()
        except: break
        if texte.lower() == "exit": break
        if not texte:               continue

        if texte.startswith("/fichier "):
            _envoyer_fichier(nd, texte[9:].strip()); continue
        if texte == "/effacer":
            envoyer_cli({"action":"effacer_historique","avec":nd})
            rep2 = attendre()
            if rep2 and rep2.get("ok"): succes("Historique effacé."); continue
        if texte == "/bloquer":
            envoyer_cli({"action":"bloquer","numero":nd,"bloquer":True})
            rep2 = attendre()
            if rep2 and rep2.get("ok"): succes(rep2["msg"]); break
            continue

        # Envoyer "en train d'écrire"
        envoyer_typing(True)

        # Chiffrer si activé
        texte_a_envoyer = texte
        if chiffrer_msgs:
            texte_a_envoyer = chiffrer(texte, cle_chat)

        envoyer_cli({"action":"message","dest":nd,"texte":texte_a_envoyer,"chiffre":chiffrer_msgs})
        envoyer_typing(False)

        rep2 = attendre(3)
        if rep2 and not rep2.get("ok"): erreur(rep2.get("msg",""))
        # Marquer comme lus après envoi
        envoyer_cli({"action":"marquer_lu","avec":nd})

# ══════════════════════════════════════════════════════════
#  FICHIERS
# ══════════════════════════════════════════════════════════
def envoyer_fichier_menu():
    titre("📎 ENVOYER UN FICHIER")
    nd = input(f"Numéro du destinataire : ").strip()
    envoyer_cli({"action":"chercher","numero":nd})
    rep = attendre()
    if not rep or not rep.get("ok"):
        erreur("Introuvable."); entree(); return
    chemin = input(f"Chemin du fichier      : ").strip()
    _envoyer_fichier(nd, chemin)
    entree()

def _envoyer_fichier(nd, chemin):
    chemin = os.path.expanduser(chemin)
    if not os.path.isfile(chemin): erreur(f"Fichier introuvable : {chemin}"); return
    taille = os.path.getsize(chemin)
    if taille > 10*1024*1024: erreur(f"Max 10 MB."); return
    nom_f = os.path.basename(chemin)
    print(f"{G}📤 Envoi de {nom_f} ({fmt(taille)})...{Z}")
    try:
        with open(chemin,"rb") as f: c64 = base64.b64encode(f.read()).decode()
    except Exception as e: erreur(f"Lecture : {e}"); return
    envoyer_cli({"action":"envoyer_fichier","dest":nd,"nom_fichier":nom_f,"contenu":c64,"taille":taille})
    rep = attendre(20)
    if rep and rep.get("ok"): succes(rep.get("msg","Envoyé !"))
    else: erreur(rep.get("msg","Erreur") if rep else "?")

# ══════════════════════════════════════════════════════════
#  GROUPES
# ══════════════════════════════════════════════════════════
def menu_groupes():
    while True:
        titre("👥 GROUPES")
        C2 = get_C()
        print(f"  {C2}1{Z} — 📋  Mes groupes")
        print(f"  {C2}2{Z} — ➕  Créer un groupe")
        print(f"  {C2}3{Z} — 💬  Entrer dans un groupe")
        print(f"  {C2}4{Z} — 👤  Ajouter un membre")
        print(f"  {C2}r{Z} — 🔙  Retour\n")
        choix = input(f"{J}Choix : {Z}").strip().lower()
        if choix=="1": mes_groupes()
        elif choix=="2": creer_groupe()
        elif choix=="3": chat_groupe()
        elif choix=="4": ajouter_membre()
        elif choix=="r": break

def mes_groupes():
    envoyer_cli({"action":"mes_groupes"})
    rep = attendre()
    titre("📋 MES GROUPES")
    if not rep or not rep.get("ok"): erreur("Erreur."); entree(); return
    groupes = rep.get("groupes",[])
    if not groupes: info("Aucun groupe.")
    else:
        for g in groupes:
            admin = f" {J}[Admin]{Z}" if g.get("createur") else ""
            print(f"  • {g['nom']}{admin}  —  {G}{g['membres']} membres{Z}")
            print(f"    {G}ID : {g['id']}{Z}")
    entree()

def creer_groupe():
    titre("➕ CRÉER UN GROUPE")
    nom = input(f"Nom du groupe : ").strip()
    if not nom: return
    envoyer_cli({"action":"creer_groupe","nom":nom})
    rep = attendre()
    if rep and rep.get("ok"):
        succes(f"Groupe '{nom}' créé !")
        print(f"   ID : {rep['id_groupe']}")
    else: erreur(rep.get("msg","?") if rep else "?")
    entree()

def chat_groupe():
    titre("💬 ENTRER DANS UN GROUPE")
    id_g = input(f"ID du groupe : ").strip()
    if not id_g: return
    print(f"\n{G}exit = retour{Z}\n")
    while True:
        try:    texte = input(f"{B}[Groupe] > {Z}").strip()
        except: break
        if texte.lower()=="exit": break
        if not texte: continue
        envoyer_cli({"action":"msg_groupe","id_groupe":id_g,"texte":texte})
        rep = attendre(3)
        if rep and not rep.get("ok"): erreur(rep.get("msg",""))

def ajouter_membre():
    titre("👤 AJOUTER UN MEMBRE")
    id_g   = input(f"ID du groupe     : ").strip()
    numero = input(f"Numéro du membre : ").strip()
    envoyer_cli({"action":"ajouter_groupe","id_groupe":id_g,"numero":numero})
    rep = attendre()
    if rep and rep.get("ok"): succes(rep.get("msg","Membre ajouté !"))
    else: erreur(rep.get("msg","?") if rep else "?")
    entree()

# ══════════════════════════════════════════════════════════
#  CHERCHER
# ══════════════════════════════════════════════════════════
def chercher_user():
    titre("🔍 CHERCHER UN UTILISATEUR")
    numero = input(f"Numéro : ").strip()
    envoyer_cli({"action":"chercher","numero":numero})
    rep = attendre()
    if rep and rep.get("ok"):
        u  = rep["user"]
        st = f"{V}🟢 En ligne{Z}" if u.get("en_ligne") else f"{G}⚫ Hors ligne{Z}"
        print(f"\n  👤 {u['nom']}  📱 {u['numero']} {V}✓{Z}")
        print(f"  🌍 {u.get('pays','—')}  📝 {u.get('bio','—')}")
        print(f"  {st}")
    else: erreur(rep.get("msg","Introuvable.") if rep else "?")
    entree()

def voir_en_ligne():
    titre("🌐 UTILISATEURS EN LIGNE")
    envoyer_cli({"action":"en_ligne"})
    rep = attendre()
    if not rep or not rep.get("ok"): erreur("Erreur."); entree(); return
    users = rep.get("users",[])
    if not users: info("Aucun autre utilisateur en ligne.")
    else:
        print(f"{V}  {len(users)} utilisateur(s) en ligne :{Z}\n")
        for u in users:
            print(f"  {V}🟢{Z}  {u['nom']}  —  {G}{u['numero']}{Z}")
    entree()

# ══════════════════════════════════════════════════════════
#  PROFIL
# ══════════════════════════════════════════════════════════
def mon_profil():
    titre("👤 MON PROFIL")
    print(f"  👤  Nom    : {B}{session.get('nom','')}{Z}")
    print(f"  📱  N°     : {session.get('numero','')} {V}✓{Z}")
    print(f"  🌍  Pays   : {G}{session.get('pays','—')}{Z}")
    print(f"  📝  Bio    : {G}{session.get('bio','—')}{Z}")
    print(f"  🎨  Couleur: {G}{session.get('couleur','cyan')}{Z}\n")
    if input(f"Modifier ta bio ? (o/n) : ").strip().lower()=="o":
        bio = input(f"Nouvelle bio (max 150) : ").strip()[:150]
        envoyer_cli({"action":"modifier_bio","bio":bio})
        rep = attendre()
        if rep and rep.get("ok"): session["bio"]=bio; succes(rep["msg"])
        else: erreur(rep.get("msg","?") if rep else "?")
    entree()

# ══════════════════════════════════════════════════════════
#  PERSONNALISATION
# ══════════════════════════════════════════════════════════
def personnalisation():
    titre("🎨 PERSONNALISATION")
    print(f"{B}Choisis ta couleur d'interface :{Z}\n")
    couleurs = list(COULEURS.items())
    for i,(nom_c,code) in enumerate(couleurs,1):
        print(f"  {code}{B}{i}{Z} — {code}{nom_c}{Z}")
    choix = input(f"\nChoix (1-{len(couleurs)}) : ").strip()
    try:
        idx     = int(choix)-1
        nom_c,_ = couleurs[idx]
        envoyer_cli({"action":"changer_couleur","couleur":nom_c})
        rep = attendre()
        if rep and rep.get("ok"):
            session["couleur"] = nom_c
            succes(f"Couleur changée → {nom_c} !")
        else: erreur(rep.get("msg","?") if rep else "?")
    except: erreur("Choix invalide.")
    entree()

# ══════════════════════════════════════════════════════════
#  SÉCURITÉ
# ══════════════════════════════════════════════════════════
def menu_securite():
    while True:
        titre("🛡️  SÉCURITÉ")
        C2 = get_C()
        print(f"  {C2}1{Z} — 🔑  Changer mot de passe")
        print(f"  {C2}2{Z} — 🚫  Bloquer un utilisateur")
        print(f"  {C2}3{Z} — ✅  Débloquer un utilisateur")
        print(f"  {C2}4{Z} — 🗑️   Supprimer mon compte")
        print(f"  {C2}r{Z} — 🔙  Retour\n")
        choix = input(f"{J}Choix : {Z}").strip().lower()
        if choix=="1":   changer_mdp()
        elif choix=="2": bloquer_user(True)
        elif choix=="3": bloquer_user(False)
        elif choix=="4": supprimer_compte(); break
        elif choix=="r": break

def changer_mdp():
    titre("🔑 CHANGER MOT DE PASSE")
    ancien  = input(f"Ancien mot de passe  : ").strip()
    nouveau = input(f"Nouveau mot de passe : ").strip()
    confirm = input(f"Confirmer            : ").strip()
    if nouveau != confirm: erreur("Ne correspondent pas."); entree(); return
    if len(nouveau)<4:     erreur("Min 4 caractères.");     entree(); return
    envoyer_cli({"action":"changer_mdp","ancien":ancien,"nouveau":nouveau})
    rep = attendre()
    if rep and rep.get("ok"): succes(rep["msg"])
    else: erreur(rep.get("msg","?") if rep else "?")
    entree()

def bloquer_user(bloquer=True):
    action = "BLOQUER" if bloquer else "DÉBLOQUER"
    titre(f"🚫 {action}")
    numero = input(f"Numéro à {action.lower()} : ").strip()
    envoyer_cli({"action":"bloquer","numero":numero,"bloquer":bloquer})
    rep = attendre()
    if rep and rep.get("ok"): succes(rep["msg"])
    else: erreur(rep.get("msg","?") if rep else "?")
    entree()

def supprimer_compte():
    titre("🗑️  SUPPRIMER MON COMPTE")
    print(f"{R}{B}⚠️  Action irréversible !{Z}\n")
    if input(f"Tape 'SUPPRIMER' : ").strip() != "SUPPRIMER":
        info("Annulé."); entree(); return
    mdp = input(f"Mot de passe : ").strip()
    envoyer_cli({"action":"supprimer_compte","mdp":mdp})
    rep = attendre()
    if rep and rep.get("ok"):
        succes("Compte supprimé.")
        session.update({"connecte":False,"nom":None,"numero":None})
    else: erreur(rep.get("msg","?") if rep else "?")
    entree()

# ══════════════════════════════════════════════════════════
#  PANEL ADMIN
# ══════════════════════════════════════════════════════════
def panel_admin():
    if not session.get("est_admin"):
        titre("⚙️  ACCÈS ADMIN")
        code = input(f"Code admin : ").strip()
        envoyer_cli({"action":"admin_login","code":code})
        rep = attendre()
        if not rep or not rep.get("ok"):
            erreur(rep.get("msg","Code incorrect.") if rep else "?"); entree(); return
        session["est_admin"] = True
        succes("Accès admin accordé !")

    while True:
        titre("⚙️  PANEL ADMIN")
        C2 = get_C()
        print(f"  {C2}1{Z} — 📊  Statistiques")
        print(f"  {C2}2{Z} — 👥  Liste des utilisateurs")
        print(f"  {C2}3{Z} — 📢  Broadcast (message à tous)")
        print(f"  {C2}4{Z} — ⛔  Déconnecter un utilisateur")
        print(f"  {C2}r{Z} — 🔙  Retour\n")
        choix = input(f"{J}Choix : {Z}").strip().lower()

        if choix=="1":
            envoyer_cli({"action":"admin_stats"})
            rep = attendre()
            if rep and rep.get("ok"):
                s = rep["stats"]
                titre("📊 STATISTIQUES")
                print(f"  👤 Utilisateurs inscrits : {B}{s.get('utilisateurs',0)}{Z}")
                print(f"  🟢 En ligne maintenant   : {B}{s.get('en_ligne',0)}{Z}")
                print(f"  💬 Messages total        : {B}{s.get('messages_total',0)}{Z}")
                print(f"  📎 Fichiers envoyés      : {B}{s.get('fichiers_total',0)}{Z}")
                print(f"  📝 Inscriptions total    : {B}{s.get('inscriptions_total',0)}{Z}")
                print(f"  👥 Groupes créés         : {B}{s.get('groupes',0)}{Z}")
                print(f"  💭 Conversations         : {B}{s.get('conversations',0)}{Z}")
            else: erreur("Erreur stats.")
            entree()

        elif choix=="2":
            envoyer_cli({"action":"admin_users"})
            rep = attendre(8)
            if rep and rep.get("ok"):
                titre("👥 TOUS LES UTILISATEURS")
                for u in rep.get("users",[]):
                    st = f"{V}🟢{Z}" if u.get("en_ligne") else f"{G}⚫{Z}"
                    print(f"  {st} {u['nom']:<15} {u['numero']}  {G}{u.get('pays','')}{Z}  {G}inscrit: {u.get('inscription','')}{Z}")
            else: erreur("Erreur.")
            entree()

        elif choix=="3":
            msg = input(f"Message à diffuser : ").strip()
            if not msg: continue
            envoyer_cli({"action":"admin_broadcast","msg":msg})
            rep = attendre()
            if rep and rep.get("ok"): succes(rep.get("msg","Envoyé !"))
            else: erreur("Erreur.")
            entree()

        elif choix=="4":
            numero = input(f"Numéro à déconnecter : ").strip()
            envoyer_cli({"action":"admin_kick","numero":numero})
            rep = attendre()
            if rep and rep.get("ok"): succes(rep.get("msg","Déconnecté."))
            else: erreur(rep.get("msg","?") if rep else "?")
            entree()

        elif choix=="r": break

# ══════════════════════════════════════════════════════════
#  QUITTER
# ══════════════════════════════════════════════════════════
def quitter(sig=None,frame=None):
    global en_cours
    en_cours = False
    if session.get("connecte"):
        try: envoyer_cli({"action":"deconnecter"})
        except: pass
    try: sock_cli.close()
    except: pass
    print(f"\n{get_C()}{B}À bientôt ! 👋{Z}\n")
    sys.exit(0)

# ══════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════
def main():
    global sock_cli, en_cours

    banniere()
    host = sys.argv[1] if len(sys.argv)>=2 else "junction.proxy.rlwy.net"
    port = int(sys.argv[2]) if len(sys.argv)>=3 else 35030

    print(f"{G}🔌 Connexion au serveur {host}:{port}...{Z}")
    try:
        sock_cli = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock_cli.settimeout(10)
        sock_cli.connect((host, port))
        sock_cli.settimeout(None)
        succes("Connecté au serveur !")
        print(f"{G}   📥 Fichiers → ~/termchat_downloads/{Z}\n")
    except Exception as e:
        erreur(f"Impossible de se connecter : {e}"); sys.exit(1)

    threading.Thread(target=recevoir, daemon=True).start()
    signal.signal(signal.SIGINT, quitter)
    try: signal.signal(signal.SIGTERM, quitter)
    except: pass
    time.sleep(0.3)

    try:
        while en_cours:
            if not session["connecte"]:
                choix = menu_accueil()
                if choix=="1":   inscrire()
                elif choix=="2": connecter()
                elif choix=="q": quitter()
            else:
                choix = menu_principal()
                if choix=="1":   chat_prive()
                elif choix=="2": menu_groupes()
                elif choix=="3": envoyer_fichier_menu()
                elif choix=="4": chercher_user()
                elif choix=="5": voir_en_ligne()
                elif choix=="6": mon_profil()
                elif choix=="7": personnalisation()
                elif choix=="8": changer_mdp()
                elif choix=="9": menu_securite()
                elif choix=="0": panel_admin()
                elif choix=="q": quitter()
    except KeyboardInterrupt:
        quitter()

if __name__ == "__main__":
    main()
