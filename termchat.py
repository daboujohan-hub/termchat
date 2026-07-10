#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TermChat v6.0 — Client — by Aboudev Labs CI"""

import socket, threading, json, os, base64, ssl
import datetime, time, sys, signal, hashlib
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

R="\033[91m";B="\033[1m";Z="\033[0m";G="\033[90m";V="\033[92m";J="\033[93m";M="\033[95m"
COULEURS={"cyan":"\033[96m","vert":"\033[92m","jaune":"\033[93m","magenta":"\033[95m","bleu":"\033[94m","rouge":"\033[91m","blanc":"\033[97m"}
STATUTS_ICONS={"disponible":f"{V}🟢 Disponible{Z}","occupe":f"{J}🟡 Occupe{Z}","ne_pas_deranger":f"{R}🔴 Ne pas deranger{Z}","absent":f"{G}⚫ Absent{Z}"}

DOWNLOADS=os.path.join(os.path.expanduser("~"),"termchat_downloads")
os.makedirs(DOWNLOADS,exist_ok=True)

PAYS={"1":("🇨🇮 Cote d'Ivoire","+225"),"2":("🇸🇳 Senegal","+221"),"3":("🇬🇳 Guinee","+224"),"4":("🇧🇫 Burkina Faso","+226"),"5":("🇬🇭 Ghana","+233")}

session={"connecte":False,"nom":None,"numero":None,"pays":None,"bio":"","couleur":"cyan","statut":"disponible","est_admin":False,"non_lus":0,"a_pin":False,"pseudo":""}
sock_cli=None;en_cours=True;reponses=[];rep_lock=threading.Lock()
phrases_secretes={}  # numero_contact -> phrase secrete (en memoire seulement, jamais envoyee au serveur)

def generer_cle(n1, n2, phrase_secrete):
    """Derive une cle Fernet (AES) a partir d'une phrase secrete que SEULS
    les deux interlocuteurs connaissent (a se transmettre par un canal a
    part, jamais via TermChat). Le sel (numeros, publics) sert uniquement
    a rendre la cle unique par conversation, pas a la proteger."""
    sel = "".join(sorted([n1, n2])).encode()
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=sel, iterations=200_000)
    return base64.urlsafe_b64encode(kdf.derive(phrase_secrete.encode()))

def chiffrer(t, cle):
    try: return Fernet(cle).encrypt(t.encode()).decode()
    except Exception: return t

def dechiffrer(t64, cle):
    try: return Fernet(cle).decrypt(t64.encode()).decode()
    except (InvalidToken, Exception): return "🔒 [Message illisible - phrase secrete incorrecte]"

def clear(): os.system("clear" if os.name!="nt" else "cls")
def beep(): print("\a",end="",flush=True)
def get_C(): return COULEURS.get(session.get("couleur","cyan"),"\033[96m")
def fmt(o):
    if o<1024: return f"{o} o"
    elif o<1024**2: return f"{o//1024} Ko"
    else: return f"{o//1024//1024} Mo"
def titre(t):
    C2=get_C()
    print(f"\n{C2}{B}{'─'*46}{Z}\n{C2}{B}  {t}{Z}\n{C2}{B}{'─'*46}{Z}\n")
def succes(m): print(f"{V}{B}✅  {m}{Z}")
def erreur(m): print(f"{R}❌  {m}{Z}")
def info(m):   print(f"{J}ℹ️   {m}{Z}")
def entree():  input(f"\n{G}[Entree pour continuer]{Z}")

def banniere():
    clear();C2=get_C()
    print(f"""{C2}{B}
╔══════════════════════════════════════════════╗
║                                              ║
║   💬   T E R M C H A T   v6.0              ║
║   Messagerie Mondiale pour Developpeurs      ║
║   by Aboudev Labs 🇨🇮                        ║
║                                              ║
╚══════════════════════════════════════════════╝{Z}
""")

def envoyer_cli(p):
    try: sock_cli.sendall((json.dumps(p,ensure_ascii=False)+"\n").encode())
    except Exception as e: erreur(f"Reseau: {e}")

def attendre(timeout=6):
    debut=time.time()
    while time.time()-debut<timeout:
        with rep_lock:
            if reponses: return reponses.pop(0)
        time.sleep(0.05)
    return None

def recevoir():
    global en_cours;buf=""
    while en_cours:
        try:
            chunk=sock_cli.recv(8192).decode("utf-8",errors="replace")
            if not chunk: en_cours=False;break
            buf+=chunk
            while "\n" in buf:
                ligne,buf=buf.split("\n",1);ligne=ligne.strip()
                if not ligne: continue
                try: p=json.loads(ligne)
                except: continue
                if "type" in p: afficher_entrant(p)
                else:
                    with rep_lock: reponses.append(p)
        except Exception:
            if en_cours: print(f"\n{R}Connexion perdue.{Z}")
            en_cours=False;break

def afficher_entrant(p):
    C2=get_C();t=p.get("type","");h=p.get("heure","")
    if t=="message":
        num_exp=p.get("numero","");texte=p.get("texte","")
        if p.get("chiffre") and session.get("numero"):
            phrase=phrases_secretes.get(num_exp)
            texte=dechiffrer(texte,generer_cle(session["numero"],num_exp,phrase)) if phrase else "🔒 [Chiffre - phrase secrete non definie dans cette session]"
        beep();reply=p.get("reply_to")
        print(f"\n{V}{B}[{h}] 💬 {p.get('de','?')} ({num_exp}){Z}")
        if reply: print(f"{G}     ↩️  {reply[:40]}{Z}")
        print(f"     {texte}")
        if p.get("chiffre"): print(f"{G}     🔐 Chiffre{Z}")
        print(f"{G}> {Z}",end="",flush=True)
    elif t=="typing":
        if p.get("actif"): print(f"\r{G}  ✍️  {p.get('de','?')} ecrit...{Z}    ",end="",flush=True)
        else: print(f"\r{' '*50}\r",end="",flush=True)
    elif t=="livre": print(f"\r{G}  ✓ Livre{Z}  ",end="",flush=True)
    elif t=="lu": print(f"\r{G}  ✓✓ Lu{Z}  ",end="",flush=True)
    elif t=="reaction":
        print(f"\n{J}  {p.get('emoji','👍')} {p.get('de','?')} a reagi{Z}")
        print(f"{G}> {Z}",end="",flush=True)
    elif t=="fichier":
        nom_f=p.get("nom_fichier","fichier");taille=p.get("taille",0);beep()
        print(f"\n{M}{B}[{h}] 📎 {p.get('de','?')} → {nom_f} ({fmt(taille)}){Z}")
        chemin=os.path.join(DOWNLOADS,nom_f);base_,ext=os.path.splitext(nom_f);c=1
        while os.path.exists(chemin): chemin=os.path.join(DOWNLOADS,f"{base_}_{c}{ext}");c+=1
        try:
            with open(chemin,"wb") as f: f.write(base64.b64decode(p.get("contenu","")))
            print(f"{V}     ✅ {chemin}{Z}")
        except Exception as e: print(f"{R}     ❌ {e}{Z}")
        print(f"{G}> {Z}",end="",flush=True)
    elif t=="vocal":
        nom_f=p.get("nom_fichier","vocal.ogg");duree=p.get("duree",0);beep()
        print(f"\n{M}{B}[{h}] 🎙️  {p.get('de','?')} → Message vocal ({duree}s){Z}")
        chemin=os.path.join(DOWNLOADS,nom_f)
        try:
            with open(chemin,"wb") as f: f.write(base64.b64decode(p.get("contenu","")))
            print(f"{V}     ✅ {chemin}{Z}")
            print(f"{G}     ▶️  termux-media-player play {chemin}{Z}")
        except Exception as e: print(f"{R}     ❌ {e}{Z}")
        print(f"{G}> {Z}",end="",flush=True)
    elif t=="msg_groupe":
        beep();reply=p.get("reply_to")
        print(f"\n{C2}{B}[{h}] 👥 [{p.get('groupe','?')}] {p.get('de','?')}{Z}")
        if reply: print(f"{G}     ↩️  {reply[:40]}{Z}")
        print(f"     {p.get('texte','')}")
        print(f"{G}> {Z}",end="",flush=True)
    elif t=="invitation_groupe":
        beep();print(f"\n{J}{B}📩 Ajoute au groupe '{p.get('groupe','?')}' !{Z}")
        print(f"{G}> {Z}",end="",flush=True)
    elif t=="epingle":
        print(f"\n{J}{B}📌 [{p.get('groupe','?')}] Epingle: {p.get('texte','')}{Z}")
        print(f"{G}> {Z}",end="",flush=True)
    elif t=="statut":
        icone=f"{V}🟢{Z}" if p.get("en_ligne") else f"{G}⚫{Z}"
        print(f"\n{G}  {icone} {p.get('nom','?')} {'en ligne' if p.get('en_ligne') else 'hors ligne'}{Z}")
        print(f"{G}> {Z}",end="",flush=True)
    elif t=="statut_change":
        st=STATUTS_ICONS.get(p.get("statut",""),"")
        print(f"\n{G}  {p.get('nom','?')} → {st}{Z}")
        print(f"{G}> {Z}",end="",flush=True)
    elif t=="annonce":
        beep();beep()
        print(f"\n{J}{B}📢 ANNONCE [{h}]: {p.get('msg','')}{Z}")
        print(f"{G}> {Z}",end="",flush=True)
    elif t=="timeout":
        print(f"\n{J}⏱️  {p.get('msg','Deconnecte.')}{Z}")
        en_cours=False
    elif t=="kick":
        print(f"\n{R}{B}⛔ {p.get('msg','Deconnecte par admin.')}{Z}")
        en_cours=False

def menu_accueil():
    banniere();C2=get_C()
    print(f"  {C2}1{Z} — 🆕  Creer un compte")
    print(f"  {C2}2{Z} — 🔑  Se connecter")
    print(f"  {C2}3{Z} — 📱  Se connecter par numero")
    print(f"  {C2}4{Z} — 📧  Se connecter par email")
    print(f"  {C2}q{Z} — 🚪  Quitter\n")
    return input(f"{J}Choix: {Z}").strip().lower()

def menu_principal():
    banniere();C2=get_C()
    nom=session.get("nom","");num=session.get("numero","")
    nl=session.get("non_lus",0);st=STATUTS_ICONS.get(session.get("statut","disponible"),"")
    badge=f" {R}[{nl} non lus]{Z}" if nl>0 else ""
    admin=f" {J}[ADMIN]{Z}" if session.get("est_admin") else ""
    print(f"{C2}{B}┌─────────────────────────────────────────┐")
    print(f"│  👤  {nom:<15} {num:<20}│")
    print(f"└─────────────────────────────────────────┘{Z} {st}{badge}{admin}\n")
    print(f"  {C2}1{Z} — 💬  Messages")
    print(f"  {C2}2{Z} — 👥  Groupes")
    print(f"  {C2}3{Z} — ⭐  Favoris")
    print(f"  {C2}4{Z} — 📎  Envoyer un fichier")
    print(f"  {C2}6{Z} — 🌐  En ligne")
    print(f"  {C2}7{Z} — 👤  Mon profil")
    print(f"  {C2}8{Z} — 😊  Statut")
    print(f"  {C2}9{Z} — 🎨  Couleur")
    print(f"  {C2}f{Z} — 💌  Feedback au developpeur")
    print(f"  {C2}s{Z} — 🛡️   Securite")
    if session.get("est_admin"): print(f"  {C2}0{Z} — ⚙️   Panel Admin")
    print(f"  {C2}q{Z} — 🚪  Deconnecter\n")
    return input(f"{J}Choix: {Z}").strip().lower()

def inscrire():
    titre("🆕 CREER UN COMPTE")
    nom=input("Ton nom (2-20 car.): ").strip()
    if not nom: erreur("Nom requis."); entree(); return
    pseudo=input("Choisis un pseudo unique @ (3-20 car., lettre puis lettres/chiffres/_): ").strip().lstrip("@")
    if not pseudo: erreur("Pseudo requis."); entree(); return
    email=input("Email (optionnel, pour te connecter aussi par email - Entree pour passer): ").strip()
    mdp=input("Mot de passe (min 4): ").strip()
    if not mdp: erreur("Mot de passe requis."); entree(); return
    mdp2=input("Confirmer: ").strip()
    if mdp!=mdp2: erreur("Les mots de passe ne correspondent pas."); entree(); return
    print(f"\n{B}Choisis ton pays:{Z}\n")
    for k,(flag_nom,prefixe) in PAYS.items(): print(f"  {k} — {flag_nom}  ({prefixe})")
    choix_pays=input("\nNumero du pays: ").strip()
    if choix_pays not in PAYS: choix_pays="1"
    _,prefixe=PAYS[choix_pays]
    envoyer_cli({"action":"inscrire","nom":nom,"mdp":mdp,"prefixe":prefixe,"pseudo":pseudo,"email":email})
    rep=attendre()
    if rep and rep.get("ok"):
        numero=rep["numero"];pays=rep.get("pays","");pseudo_ok=rep.get("pseudo","")
        print(f"""
{V}{B}╔══════════════════════════════════════════╗
║   ✅  Compte cree avec succes!           ║
╠══════════════════════════════════════════╣
║   👤  {nom:<36}║
║   @   {pseudo_ok:<36}║
║   📱  {numero:<36}║
║   🌍  {pays:<36}║
╚══════════════════════════════════════════╝{Z}
{J}⚠️  Note bien ton numero et ton pseudo - ce sont tes identifiants!{Z}
""")
    else: erreur(rep.get("msg","Erreur") if rep else "Pas de reponse.")
    entree()

def connecter():
    titre("🔑 SE CONNECTER")
    nom=input("Ton nom: ").strip();mdp=input("Mot de passe: ").strip()
    envoyer_cli({"action":"connecter","nom":nom,"mdp":mdp});rep=attendre()
    if rep and rep.get("ok"): _finaliser_connexion(rep);return
    if rep and rep.get("utiliser_numero"): info("Plusieurs comptes. Connecte-toi par numero."); entree(); connecter_par_numero();return
    erreur(rep.get("msg","Erreur") if rep else "Pas de reponse.");entree()

def connecter_par_numero():
    titre("📱 CONNEXION PAR NUMERO")
    numero=input("Ton numero: ").strip();mdp=input("Mot de passe: ").strip()
    envoyer_cli({"action":"connecter_numero","numero":numero,"mdp":mdp});rep=attendre()
    if rep and rep.get("ok"): _finaliser_connexion(rep);return
    erreur(rep.get("msg","Erreur") if rep else "Pas de reponse.");entree()

def connecter_par_email():
    titre("📧 CONNEXION PAR EMAIL")
    email=input("Ton email: ").strip();mdp=input("Mot de passe: ").strip()
    envoyer_cli({"action":"connecter_email","email":email,"mdp":mdp});rep=attendre()
    if rep and rep.get("ok"): _finaliser_connexion(rep);return
    erreur(rep.get("msg","Erreur") if rep else "Pas de reponse.");entree()

def _finaliser_connexion(rep):
    session.update({"connecte":True,"nom":rep["nom"],"numero":rep["numero"],
        "pays":rep.get("pays",""),"bio":rep.get("bio",""),"couleur":rep.get("couleur","cyan"),
        "statut":rep.get("statut","disponible"),"est_admin":rep.get("est_admin",False),
        "non_lus":rep.get("non_lus",0),"a_pin":rep.get("a_pin",False),"pseudo":rep.get("pseudo","")})
    if session["a_pin"]:
        tentatives=0
        while tentatives<3:
            pin=input(f"\n{J}🔢 Code PIN requis: {Z}").strip()
            envoyer_cli({"action":"verifier_pin","pin":pin});rep_pin=attendre()
            if rep_pin and rep_pin.get("ok"): break
            erreur("PIN incorrect.");tentatives+=1
        else: erreur("Trop de tentatives."); session["connecte"]=False;return
    if not session["pseudo"]:
        print(f"\n{J}⚠️  Ton compte n'a pas encore de pseudo (@handle).{Z}")
        print(f"{J}   C'est desormais requis pour que les autres puissent te trouver facilement.{Z}")
        while True:
            pseudo=input(f"\n{J}Choisis ton pseudo @ (3-20 car., lettre puis lettres/chiffres/_): {Z}").strip().lstrip("@")
            if not pseudo:
                info("Tu pourras le definir plus tard depuis 'Mon profil'.");break
            envoyer_cli({"action":"definir_pseudo","pseudo":pseudo});rep_p=attendre()
            if rep_p and rep_p.get("ok"):
                session["pseudo"]=rep_p.get("pseudo",pseudo)
                succes(rep_p.get("msg","Pseudo enregistre!"));break
            else:
                erreur(rep_p.get("msg","Erreur") if rep_p else "Pas de reponse.")
    nl=session["non_lus"]
    print(f"\n{V}{B}✅ Bienvenue {rep['nom']}!{Z}")
    if nl>0: print(f"{J}📬 {nl} message(s) non lu(s)!{Z}")
    time.sleep(1)

def menu_messages():
    while True:
        titre("💬 MESSAGES"); C2=get_C()
        envoyer_cli({"action":"mes_conversations"});rep=attendre(8)
        convs=rep.get("conversations",[]) if rep and rep.get("ok") else []
        if convs:
            print(f"{B}Conversations recentes:{Z}\n")
            for i,c in enumerate(convs,1):
                badge=f" {R}[{c['non_lus']}]{Z}" if c['non_lus']>0 else ""
                dm=c['dernier_msg']
                print(f"  {C2}{i}{Z} — {B}{c['nom']}{Z}{G} ({c['numero']}){Z}{badge}")
                print(f"     {G}{dm[:35]}  {c['heure']}{Z}")
            print()
        print(f"  {C2}n{Z} — ✏️   Nouvelle conversation")
        print(f"  {C2}r{Z} — 🔙  Retour\n")
        choix=input(f"{J}Choix: {Z}").strip().lower()
        if choix=="r": break
        elif choix=="n":
            nd=input("Numero ou @pseudo du destinataire: ").strip()
            if nd: _ouvrir_chat(nd)
        elif choix.isdigit():
            idx=int(choix)-1
            if 0<=idx<len(convs): _ouvrir_chat(convs[idx]["numero"])

def _ouvrir_chat(nd):
    if nd.startswith("@"):
        envoyer_cli({"action":"chercher","pseudo":nd[1:]});rep=attendre()
        if not rep or not rep.get("ok"): erreur(rep.get("msg","Introuvable.") if rep else "?");entree();return
        nd=rep["user"]["numero"]  # on bascule sur le vrai numero pour tout le reste
        u=rep["user"]
    else:
        envoyer_cli({"action":"chercher","numero":nd});rep=attendre()
        if not rep or not rep.get("ok"): erreur(rep.get("msg","Introuvable.") if rep else "?");entree();return
        u=rep["user"]
    st=STATUTS_ICONS.get(u.get("statut","disponible"),"")
    chiffrer_msgs=False;cle_chat=None
    if input(f"\n{J}Activer chiffrement? (o/n): {Z}").strip().lower()=="o":
        phrase=input(f"{J}Phrase secrete partagee avec {u['nom']} (a se transmettre hors TermChat): {Z}").strip()
        if phrase:
            chiffrer_msgs=True;cle_chat=generer_cle(session["numero"],nd,phrase)
            phrases_secretes[nd]=phrase
            succes("Chiffrement active 🔐")
        else:
            info("Phrase vide, chiffrement desactive.")
    envoyer_cli({"action":"historique","avec":nd,"limite":20});rep_h=attendre(8)
    if rep_h and rep_h.get("ok"):
        hist=rep_h.get("historique",[])
        if hist:
            print(f"\n{G}── Historique recent ──────────────{Z}")
            for msg in hist:
                dt=msg.get("heure","")[:16].replace("T"," ")
                moi_=msg.get("de")==session["numero"]
                col=get_C() if moi_ else V
                nom_s="[Toi]" if moi_ else f"[{msg.get('nom_de','?')}]"
                lu=" ✓✓" if (moi_ and msg.get("lu")) else (" ✓" if moi_ else "")
                texte=msg.get("texte","");reply=msg.get("reply_to")
                if msg.get("chiffre") and msg.get("type")!="fichier":
                    texte=(dechiffrer(texte,cle_chat)+" 🔐") if cle_chat else "🔒 [Chiffre - active le chiffrement pour lire]"
                if reply: print(f"  {G}↩️  {reply[:30]}{Z}")
                print(f"{G}{dt}{Z} {col}{B}{nom_s}{Z}{lu} {texte}")
    print(f"\n{V}✅ {u['nom']} — {st}{Z}")
    dernier_msg_id=None;expire_prochain=None
    print(f"\n{G}exit | /fichier | /vocal | /auto N | /repondre | /reaction | /rechercher | /effacer | /favori{Z}\n")
    while True:
        try: texte=input(f"{B}[→ {u['nom']}] > {Z}").strip()
        except: break
        if texte.lower()=="exit": break
        if not texte: continue
        if texte.startswith("/fichier "):
            mid=_envoyer_fichier(nd,texte[9:].strip())
            if mid: dernier_msg_id=mid
            continue
        if texte.startswith("/vocal "):
            mid=_envoyer_vocal(nd,texte[7:].strip())
            if mid: dernier_msg_id=mid
            continue
        if texte.startswith("/auto "):
            try: expire_prochain=int(texte.split()[1]);info(f"Prochain message auto-detruit dans {expire_prochain}s.")
            except: erreur("Usage: /auto 30")
            continue
        if texte=="/repondre":
            if not dernier_msg_id: info("Aucun message a repondre.");continue
            rt=input("Ta reponse: ").strip()
            if not rt: continue
            te=chiffrer(rt,cle_chat) if chiffrer_msgs else rt
            envoyer_cli({"action":"message","dest":nd,"texte":te,"chiffre":chiffrer_msgs,"reply_to":dernier_msg_id})
            rep2=attendre(3)
            if rep2 and rep2.get("ok"): dernier_msg_id=rep2.get("msg_id")
            elif rep2: erreur(rep2.get("msg",""))
            continue
        if texte=="/reaction":
            if not dernier_msg_id: info("Aucun message.");continue
            emoji=input("Reaction (👍❤️😂😮😢): ").strip() or "👍"
            envoyer_cli({"action":"reaction","dest":nd,"msg_id":dernier_msg_id,"emoji":emoji});attendre(3);continue
        if texte=="/rechercher":
            mot=input("Mot cle: ").strip()
            envoyer_cli({"action":"rechercher_msg","avec":nd,"mot":mot});rep2=attendre(8)
            if rep2 and rep2.get("ok"):
                res=rep2.get("resultats",[])
                if not res: info("Aucun resultat.")
                else:
                    for m in res: print(f"{G}{m.get('heure','')[:16].replace('T',' ')}{Z} {m.get('texte','')}")
            continue
        if texte=="/effacer":
            envoyer_cli({"action":"effacer_historique","avec":nd});rep2=attendre()
            if rep2 and rep2.get("ok"): succes("Historique efface.")
            continue
        if texte=="/favori":
            envoyer_cli({"action":"ajouter_favori","numero":nd});rep2=attendre()
            if rep2 and rep2.get("ok"): succes(rep2.get("msg","Ajoute!"))
            continue
        envoyer_cli({"action":"typing","dest":nd,"actif":True})
        te=chiffrer(texte,cle_chat) if chiffrer_msgs else texte
        paquet={"action":"message","dest":nd,"texte":te,"chiffre":chiffrer_msgs}
        if expire_prochain:
            paquet["expire_secondes"]=expire_prochain
            print(f"{G}  ⏱️  Auto-destruction dans {expire_prochain}s{Z}")
            expire_prochain=None
        envoyer_cli(paquet);envoyer_cli({"action":"typing","dest":nd,"actif":False})
        rep2=attendre(3)
        if rep2 and rep2.get("ok"): dernier_msg_id=rep2.get("msg_id")
        elif rep2 and not rep2.get("ok"): erreur(rep2.get("msg",""))
        envoyer_cli({"action":"marquer_lu","avec":nd})

def envoyer_fichier_menu():
    titre("📎 ENVOYER UN FICHIER")
    nd=input("Numero ou @pseudo du destinataire: ").strip()
    if nd.startswith("@"): envoyer_cli({"action":"chercher","pseudo":nd[1:]})
    else: envoyer_cli({"action":"chercher","numero":nd})
    rep=attendre()
    if not rep or not rep.get("ok"): erreur("Introuvable.");entree();return
    nd=rep["user"]["numero"]  # on bascule sur le vrai numero pour l'envoi
    chemin=input("Chemin du fichier: ").strip();_envoyer_fichier(nd,chemin);entree()

def _envoyer_fichier(nd,chemin):
    chemin=os.path.expanduser(chemin)
    if not os.path.isfile(chemin): erreur(f"Introuvable: {chemin}");return None
    taille=os.path.getsize(chemin)
    if taille>50*1024*1024: erreur("Max 50 MB.");return None
    nom_f=os.path.basename(chemin);print(f"{G}📤 Envoi {nom_f} ({fmt(taille)})...{Z}")
    try:
        with open(chemin,"rb") as f: c64=base64.b64encode(f.read()).decode()
    except Exception as e: erreur(f"Lecture: {e}");return None
    envoyer_cli({"action":"envoyer_fichier","dest":nd,"nom_fichier":nom_f,"contenu":c64,"taille":taille})
    rep=attendre(20)
    if rep and rep.get("ok"): succes(rep.get("msg","Envoye!"));return rep.get("msg_id")
    else: erreur(rep.get("msg","Erreur") if rep else "?");return None

def _envoyer_vocal(nd,chemin):
    chemin=os.path.expanduser(chemin)
    if not os.path.isfile(chemin): erreur(f"Introuvable: {chemin}");return None
    taille=os.path.getsize(chemin)
    if taille>50*1024*1024: erreur("Max 50 MB.");return None
    print(f"{G}🎙️  Envoi vocal ({fmt(taille)})...{Z}")
    try:
        with open(chemin,"rb") as f: c64=base64.b64encode(f.read()).decode()
    except Exception as e: erreur(f"Lecture: {e}");return None
    envoyer_cli({"action":"envoyer_vocal","dest":nd,"contenu":c64,"taille":taille,"duree":0})
    rep=attendre(20)
    if rep and rep.get("ok"): succes(rep.get("msg","Vocal envoye!"));return rep.get("msg_id")
    else: erreur(rep.get("msg","Erreur") if rep else "?");return None

def voir_favoris():
    titre("⭐ CONTACTS FAVORIS");envoyer_cli({"action":"mes_favoris"});rep=attendre()
    if not rep or not rep.get("ok"): erreur("Erreur.");entree();return
    favoris=rep.get("favoris",[])
    if not favoris: info("Aucun favori.")
    else:
        for f in favoris:
            st=STATUTS_ICONS.get(f.get("statut","disponible"),"")
            print(f"  ⭐ {f['nom']}  {G}{f['numero']}{Z}  {st}")
    entree()

def menu_groupes():
    while True:
        titre("👥 GROUPES");C2=get_C()
        print(f"  {C2}1{Z} — 📋  Mes groupes")
        print(f"  {C2}2{Z} — ➕  Creer un groupe")
        print(f"  {C2}3{Z} — 💬  Entrer dans un groupe")
        print(f"  {C2}4{Z} — 👤  Ajouter un membre")
        print(f"  {C2}r{Z} — 🔙  Retour\n")
        choix=input(f"{J}Choix: {Z}").strip().lower()
        if choix=="1":
            envoyer_cli({"action":"mes_groupes"});rep=attendre();titre("📋 MES GROUPES")
            if not rep or not rep.get("ok"): erreur("Erreur.");entree();continue
            groupes=rep.get("groupes",[])
            if not groupes: info("Aucun groupe.")
            else:
                for g in groupes:
                    adm=f" {J}[Admin]{Z}" if g.get("createur") else ""
                    print(f"  • {g['nom']}{adm}  {G}{g['membres']} membres — ID:{g['id']}{Z}")
            entree()
        elif choix=="2":
            nom=input("Nom du groupe: ").strip()
            if not nom: continue
            envoyer_cli({"action":"creer_groupe","nom":nom});rep=attendre()
            if rep and rep.get("ok"): succes(f"Groupe '{nom}' cree!"); print(f"   {G}ID: {rep['id_groupe']}{Z}")
            else: erreur(rep.get("msg","?") if rep else "?")
            entree()
        elif choix=="3":
            id_g=input("ID du groupe: ").strip()
            if not id_g: continue
            reply_id=None
            print(f"\n{G}exit | /epingler | /repondre{Z}\n")
            while True:
                try: texte=input(f"{B}[Groupe] > {Z}").strip()
                except: break
                if texte.lower()=="exit": break
                if not texte: continue
                if texte=="/epingler":
                    msg=input("Message a epingler: ").strip()
                    envoyer_cli({"action":"epingler_groupe","id_groupe":id_g,"texte":msg});attendre(3);continue
                if texte=="/repondre":
                    rt=input("Repondre a (texte): ").strip();reply_id=rt;info(f"Tu repondras a: {rt[:30]}");continue
                envoyer_cli({"action":"msg_groupe","id_groupe":id_g,"texte":texte,"reply_to":reply_id});reply_id=None
                rep=attendre(3)
                if rep and not rep.get("ok"): erreur(rep.get("msg",""))
        elif choix=="4":
            id_g=input("ID du groupe: ").strip();numero=input("Numero du membre: ").strip()
            envoyer_cli({"action":"ajouter_groupe","id_groupe":id_g,"numero":numero});rep=attendre()
            if rep and rep.get("ok"): succes(rep.get("msg","Ajoute!"))
            else: erreur(rep.get("msg","?") if rep else "?")
            entree()
        elif choix=="r": break

def voir_en_ligne():
    titre("🌐 UTILISATEURS EN LIGNE");envoyer_cli({"action":"en_ligne"});rep=attendre()
    if not rep or not rep.get("ok"): erreur("Erreur.");entree();return
    users=rep.get("users",[])
    if not users: info("Personne d'autre en ligne.")
    else:
        print(f"{V}  {len(users)} en ligne:{Z}\n")
        for u in users:
            st=STATUTS_ICONS.get(u.get("statut","disponible"),"")
            print(f"  🟢  {u['nom']}  {G}{u['numero']}{Z}  {st}")
    entree()

def mon_profil():
    titre("👤 MON PROFIL");st=STATUTS_ICONS.get(session.get("statut","disponible"),"")
    print(f"  👤  Nom:    {B}{session.get('nom','')}{Z}")
    pseudo_aff = f"@{session['pseudo']}" if session.get("pseudo") else f"{J}(non defini){Z}"
    print(f"  🏷️   Pseudo: {pseudo_aff}")
    print(f"  📱  N°:     {session.get('numero','')} {V}✓{Z}")
    print(f"  🌍  Pays:   {G}{session.get('pays','—')}{Z}")
    print(f"  📝  Bio:    {G}{session.get('bio','—')}{Z}")
    print(f"  😊  Statut: {st}\n")
    if not session.get("pseudo"):
        if input("Definir ton pseudo maintenant? (o/n): ").strip().lower()=="o":
            pseudo=input("Pseudo @ (3-20 car., lettre puis lettres/chiffres/_): ").strip().lstrip("@")
            envoyer_cli({"action":"definir_pseudo","pseudo":pseudo});rep=attendre()
            if rep and rep.get("ok"): session["pseudo"]=rep.get("pseudo",pseudo);succes(rep["msg"])
            else: erreur(rep.get("msg","?") if rep else "?")
    if input("Modifier ta bio? (o/n): ").strip().lower()=="o":
        bio=input("Nouvelle bio (max 150): ").strip()[:150]
        envoyer_cli({"action":"modifier_bio","bio":bio});rep=attendre()
        if rep and rep.get("ok"): session["bio"]=bio;succes(rep["msg"])
        else: erreur(rep.get("msg","?") if rep else "?")
    entree()

def changer_statut():
    titre("😊 CHANGER MON STATUT")
    statuts=[("disponible","🟢 Disponible"),("occupe","🟡 Occupe"),("ne_pas_deranger","🔴 Ne pas deranger"),("absent","⚫ Absent")]
    for i,(s,label) in enumerate(statuts,1): print(f"  {i} — {label}")
    choix=input("\nChoix: ").strip()
    try:
        statut=statuts[int(choix)-1][0]
        envoyer_cli({"action":"changer_statut","statut":statut});rep=attendre()
        if rep and rep.get("ok"): session["statut"]=statut;succes(rep["msg"])
        else: erreur(rep.get("msg","?") if rep else "?")
    except: erreur("Choix invalide.")
    entree()

def personnalisation():
    titre("🎨 PERSONNALISATION");couleurs=list(COULEURS.items())
    for i,(nom_c,code) in enumerate(couleurs,1): print(f"  {code}{B}{i}{Z} — {code}{nom_c}{Z}")
    choix=input(f"\nChoix (1-{len(couleurs)}): ").strip()
    try:
        nom_c,_=couleurs[int(choix)-1]
        envoyer_cli({"action":"changer_couleur","couleur":nom_c});rep=attendre()
        if rep and rep.get("ok"): session["couleur"]=nom_c;succes(f"Couleur → {nom_c}!")
        else: erreur(rep.get("msg","?") if rep else "?")
    except: erreur("Choix invalide.")
    entree()

def envoyer_feedback():
    titre("💌 FEEDBACK AU DEVELOPPEUR")
    print(f"{G}Un bug, une idee, une remarque ? Ecris-la ici, elle sera{Z}")
    print(f"{G}transmise directement au developpeur de TermChat.{Z}\n")
    texte=input("Ton message (max 500 car.): ").strip()
    if not texte:
        info("Message vide, annule.");entree();return
    envoyer_cli({"action":"envoyer_feedback","texte":texte});rep=attendre()
    if rep and rep.get("ok"): succes(rep.get("msg","Envoye!"))
    else: erreur(rep.get("msg","Erreur") if rep else "Pas de reponse.")
    entree()

def menu_securite():
    while True:
        titre("🛡️  SECURITE");C2=get_C()
        print(f"  {C2}1{Z} — 🔑  Changer mot de passe")
        print(f"  {C2}2{Z} — 🚫  Bloquer un utilisateur")
        print(f"  {C2}3{Z} — ✅  Debloquer un utilisateur")
        print(f"  {C2}4{Z} — 🔢  Code PIN")
        print(f"  {C2}5{Z} — 🗑️   Supprimer mon compte")
        print(f"  {C2}r{Z} — 🔙  Retour\n")
        choix=input(f"{J}Choix: {Z}").strip().lower()
        if choix=="1":
            ancien=input("Ancien mdp: ").strip();nouveau=input("Nouveau mdp: ").strip();confirm=input("Confirmer: ").strip()
            if nouveau!=confirm: erreur("Ne correspondent pas.");entree();continue
            if len(nouveau)<4: erreur("Min 4 caracteres.");entree();continue
            envoyer_cli({"action":"changer_mdp","ancien":ancien,"nouveau":nouveau});rep=attendre()
            if rep and rep.get("ok"): succes(rep["msg"])
            else: erreur(rep.get("msg","?") if rep else "?")
            entree()
        elif choix=="2":
            numero=input("Numero a bloquer: ").strip()
            envoyer_cli({"action":"bloquer","numero":numero,"bloquer":True});rep=attendre()
            if rep and rep.get("ok"): succes(rep["msg"])
            else: erreur(rep.get("msg","?") if rep else "?")
            entree()
        elif choix=="3":
            numero=input("Numero a debloquer: ").strip()
            envoyer_cli({"action":"bloquer","numero":numero,"bloquer":False});rep=attendre()
            if rep and rep.get("ok"): succes(rep["msg"])
            else: erreur(rep.get("msg","?") if rep else "?")
            entree()
        elif choix=="4":
            print("  1 — Activer PIN  |  2 — Desactiver PIN")
            c2=input("Choix: ").strip()
            if c2=="1":
                pin=input("PIN (4 chiffres): ").strip();pin2=input("Confirmer: ").strip()
                if pin!=pin2: erreur("Ne correspondent pas.");entree();continue
                envoyer_cli({"action":"definir_pin","pin":pin});rep=attendre()
                if rep and rep.get("ok"): session["a_pin"]=True;succes(rep["msg"])
                else: erreur(rep.get("msg","?") if rep else "?")
            elif c2=="2":
                envoyer_cli({"action":"supprimer_pin"});rep=attendre()
                if rep and rep.get("ok"): session["a_pin"]=False;succes(rep["msg"])
                else: erreur(rep.get("msg","?") if rep else "?")
            entree()
        elif choix=="5":
            print(f"{R}{B}⚠️  Action irreversible!{Z}\n")
            if input("Tape 'SUPPRIMER': ").strip()!="SUPPRIMER": info("Annule.");entree();continue
            mdp=input("Mot de passe: ").strip()
            envoyer_cli({"action":"supprimer_compte","mdp":mdp});rep=attendre()
            if rep and rep.get("ok"):
                succes("Compte supprime.");session["connecte"]=False;session["nom"]=None;entree();break
            else: erreur(rep.get("msg","?") if rep else "?");entree()
        elif choix=="r": break

def panel_admin():
    if not session.get("est_admin"):
        titre("⚙️  ACCES ADMIN");code=input("Code admin: ").strip()
        envoyer_cli({"action":"admin_login","code":code});rep=attendre()
        if not rep or not rep.get("ok"): erreur(rep.get("msg","Code incorrect.") if rep else "?");entree();return
        session["est_admin"]=True;succes("Acces accorde!")
    while True:
        titre("⚙️  PANEL ADMIN");C2=get_C()
        print(f"  {C2}1{Z} — 📊  Statistiques")
        print(f"  {C2}2{Z} — 👥  Tous les utilisateurs")
        print(f"  {C2}3{Z} — 📢  Broadcast")
        print(f"  {C2}4{Z} — ⛔  Kick utilisateur")
        print(f"  {C2}5{Z} — 💌  Feedback recus")
        print(f"  {C2}r{Z} — 🔙  Retour\n")
        choix=input(f"{J}Choix: {Z}").strip().lower()
        if choix=="1":
            envoyer_cli({"action":"admin_stats"});rep=attendre(10)
            if rep and rep.get("ok"):
                s=rep["stats"];titre("📊 STATISTIQUES")
                print(f"  👤 Utilisateurs  : {B}{s.get('utilisateurs',0)}{Z}")
                print(f"  🟢 En ligne      : {B}{s.get('en_ligne',0)}{Z}")
                print(f"  💬 Conversations : {B}{s.get('conversations',0)}{Z}")
                print(f"  👥 Groupes       : {B}{s.get('groupes',0)}{Z}")
            else: erreur("Erreur.")
            entree()
        elif choix=="2":
            envoyer_cli({"action":"admin_users"});rep=attendre(15)
            if rep and rep.get("ok"):
                titre("👥 UTILISATEURS")
                for u in rep.get("users",[]):
                    st=f"{V}🟢{Z}" if u.get("en_ligne") else f"{G}⚫{Z}"
                    print(f"  {st} {u['nom']:<12} {u['numero']}  {G}{u.get('pays','')}{Z}")
                    print(f"     {G}Inscrit: {u.get('inscription','')}{Z}")
            else: erreur("Erreur.")
            entree()
        elif choix=="3":
            msg=input("Message: ").strip()
            if not msg: continue
            envoyer_cli({"action":"admin_broadcast","msg":msg});rep=attendre()
            if rep and rep.get("ok"): succes(rep.get("msg","Envoye!"))
            entree()
        elif choix=="4":
            numero=input("Numero a kick: ").strip()
            envoyer_cli({"action":"admin_kick","numero":numero});rep=attendre()
            if rep and rep.get("ok"): succes(rep.get("msg",""))
            else: erreur(rep.get("msg","?") if rep else "?")
            entree()
        elif choix=="5":
            envoyer_cli({"action":"admin_feedback"});rep=attendre(10)
            if rep and rep.get("ok"):
                fb=rep.get("feedback",[])
                titre(f"💌 FEEDBACK RECUS ({len(fb)})")
                if not fb: print(f"  {G}Aucun feedback pour le moment.{Z}")
                for f in fb:
                    dt=f.get("heure","")[:16].replace("T"," ")
                    print(f"\n  {G}{dt}{Z} — {B}{f.get('nom','?')}{Z} ({f.get('numero','?')})")
                    print(f"  {f.get('texte','')}")
            else: erreur("Erreur.")
            entree()
        elif choix=="r": break

def quitter(sig=None,frame=None):
    global en_cours;en_cours=False
    if session.get("connecte"):
        try: envoyer_cli({"action":"deconnecter"})
        except Exception: pass
    try: sock_cli.close()
    except Exception: pass
    print(f"\n{get_C()}{B}A bientot! 👋{Z}\n");sys.exit(0)

def main():
    global sock_cli,en_cours
    banniere()
    host=sys.argv[1] if len(sys.argv)>=2 else "reseau.proxy.rlwy.net"
    port=int(sys.argv[2]) if len(sys.argv)>=3 else 29543
    print(f"{G}🔌 Connexion a {host}:{port}...{Z}")
    try:
        sock_cli=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        sock_cli.settimeout(10);sock_cli.connect((host,port))
        # TLS: le serveur utilise un certificat auto-signe (pas de CA reconnue),
        # on chiffre donc le transport sans verifier la chaine de confiance.
        # Ca protege contre l'ecoute passive sur le reseau, mais pas contre un
        # attaquant actif capable d'usurper le serveur (pas de pinning ici).
        try:
            ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.check_hostname=False;ctx.verify_mode=ssl.CERT_NONE
            sock_tls=ctx.wrap_socket(sock_cli,server_hostname=host)
            sock_cli=sock_tls
            print(f"{G}🔐 Connexion chiffree (TLS){Z}")
        except Exception as e:
            # wrap_socket() ferme le socket sous-jacent en cas d'echec: on en
            # recree un neuf pour le repli en clair, sinon la connexion plante.
            print(f"{J}⚠️  TLS indisponible, connexion en clair ({e}){Z}")
            try: sock_cli.close()
            except Exception: pass
            sock_cli=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
            sock_cli.settimeout(10);sock_cli.connect((host,port))
        sock_cli.settimeout(None)
        succes("Connecte!");print(f"{G}   📥 Fichiers → ~/termchat_downloads/{Z}\n")
    except Exception as e: erreur(f"Impossible de se connecter: {e}");sys.exit(1)
    threading.Thread(target=recevoir,daemon=True).start()
    signal.signal(signal.SIGINT,quitter)
    try: signal.signal(signal.SIGTERM,quitter)
    except Exception: pass
    time.sleep(0.3)
    try:
        while en_cours:
            if not session["connecte"]:
                choix=menu_accueil()
                if choix=="1": inscrire()
                elif choix=="2": connecter()
                elif choix=="3": connecter_par_numero()
                elif choix=="4": connecter_par_email()
                elif choix=="q": quitter()
            else:
                choix=menu_principal()
                if choix=="1": menu_messages()
                elif choix=="2": menu_groupes()
                elif choix=="3": voir_favoris()
                elif choix=="4": envoyer_fichier_menu()
                elif choix=="6": voir_en_ligne()
                elif choix=="7": mon_profil()
                elif choix=="8": changer_statut()
                elif choix=="9": personnalisation()
                elif choix=="f": envoyer_feedback()
                elif choix=="s": menu_securite()
                elif choix=="0": panel_admin()
                elif choix=="q": quitter()
    except KeyboardInterrupt: quitter()

if __name__=="__main__": main()
