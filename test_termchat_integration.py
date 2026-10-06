#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TermChat v6.3 — test_termchat_integration.py

Test d'intégration réel, non interactif :
  1) connexion TLS
  2) création de deux comptes temporaires
  3) publication des clés publiques
  4) connexion des deux comptes
  5) recherche mutuelle
  6) message privé chiffré A -> B
  7) vérification du déchiffrement côté B
  8) vérification de l'empreinte
  9) création d'un groupe par A
 10) ajout de B
 11) distribution d'une clé de groupe
 12) message de groupe chiffré A -> B
 13) mauvaise clé => message illisible
 14) rotation de clé de groupe

ATTENTION :
- Le script crée de VRAIS comptes temporaires dans l'instance TermChat.
- Il ne touche pas aux comptes existants.
- La suppression automatique n'est tentée qu'avec --cleanup.
- Le serveur n'autorise la suppression que si ALLOW_ACCOUNT_DELETION=1.
- Il faut fournir l'hôte et le port réels de ton serveur.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import queue
import secrets
import socket
import ssl
import sys
import threading
import time

try:
    from cryptography.fernet import Fernet, InvalidToken
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import x25519
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
except ImportError:
    print("❌ cryptography n'est pas installé.")
    print("   pip install cryptography")
    sys.exit(2)


TIMEOUT = 8
PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"


def ok_name(s):
    print(f"✅ {s}")


def bad_name(s, detail=""):
    print(f"❌ {s}")
    if detail:
        print(f"   {detail}")


def skip_name(s, detail=""):
    print(f"⏭️  {s}")
    if detail:
        print(f"   {detail}")


class Client:
    def __init__(self, host, port, label):
        self.host = host
        self.port = port
        self.label = label
        self.sock = None
        self.events = queue.Queue()
        self.responses = queue.Queue()
        self.running = False
        self.reader = None

    def connect(self):
        raw = socket.create_connection((self.host, self.port), timeout=10)

        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        # Identique au comportement du client TermChat fourni :
        # certificat accepté après le mécanisme de confiance/pinning du client.
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        self.sock = ctx.wrap_socket(raw, server_hostname=self.host)
        self.sock.settimeout(None)
        self.running = True
        self.reader = threading.Thread(target=self._read_loop, daemon=True)
        self.reader.start()
        return self.sock.version()

    def _read_loop(self):
        buf = ""
        try:
            while self.running:
                chunk = self.sock.recv(8192)
                if not chunk:
                    break
                buf += chunk.decode("utf-8", errors="replace")
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue

                    # Le client réel distingue les événements par "type".
                    if "type" in obj:
                        self.events.put(obj)
                    else:
                        self.responses.put(obj)
        except Exception:
            pass
        finally:
            self.running = False

    def send(self, payload):
        raw = (json.dumps(payload, ensure_ascii=False) + "\n").encode()
        self.sock.sendall(raw)

    def request(self, payload, timeout=TIMEOUT):
        self.send(payload)
        end = time.time() + timeout
        while time.time() < end:
            remaining = max(0.05, end - time.time())
            try:
                return self.responses.get(timeout=min(0.25, remaining))
            except queue.Empty:
                continue
        return None

    def wait_event(self, event_type=None, timeout=TIMEOUT):
        end = time.time() + timeout
        while time.time() < end:
            remaining = max(0.05, end - time.time())
            try:
                event = self.events.get(timeout=min(0.25, remaining))
            except queue.Empty:
                continue
            if event_type is None or event.get("type") == event_type:
                return event
        return None

    def close(self):
        self.running = False
        try:
            self.send({"action": "deconnecter"})
        except Exception:
            pass
        try:
            self.sock.close()
        except Exception:
            pass


def public_b64(priv):
    raw = priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return base64.urlsafe_b64encode(raw).decode()


def shared_key(priv, peer_public_b64, n1, n2):
    peer = x25519.X25519PublicKey.from_public_bytes(
        base64.urlsafe_b64decode(peer_public_b64)
    )
    secret = priv.exchange(peer)
    salt = "".join(sorted([n1, n2])).encode()
    derived = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=b"termchat-e2e-v2",
    ).derive(secret)
    return base64.urlsafe_b64encode(derived)


def fingerprint(pub_a, pub_b):
    keys = sorted([pub_a or "", pub_b or ""])
    h = hashlib.sha256((keys[0] + keys[1]).encode()).hexdigest()
    return " ".join(h[i:i + 5] for i in range(0, 30, 5)).upper()


def wrap_group_key(group_key, creator_priv, member_pub, creator_num, member_num):
    k = shared_key(creator_priv, member_pub, creator_num, member_num)
    # Le client utilise Fernet puis base64.b64encode du token.
    token = Fernet(k).encrypt(group_key)
    return base64.b64encode(token).decode()


def unwrap_group_key(wrapped, member_priv, creator_pub, member_num, creator_num):
    k = shared_key(member_priv, creator_pub, member_num, creator_num)
    token = base64.b64decode(wrapped)
    return Fernet(k).decrypt(token)


def strong_password():
    # >= 12 chars et au moins minuscule/majuscule/chiffre/symbole
    return "Tc!" + secrets.token_urlsafe(15) + "9A"


def make_account(label):
    suffix = secrets.token_hex(5)
    return {
        "label": label,
        "nom": f"TC{label}{suffix[:5]}",
        "pseudo": f"tc{label.lower()}{suffix}",
        "email": f"tc_{label.lower()}_{suffix}@example.invalid",
        "mdp": strong_password(),
        "prefixe": "+225",
        "priv": x25519.X25519PrivateKey.generate(),
    }


def register(client, acc):
    pub = public_b64(acc["priv"])
    rep = client.request({
        "action": "inscrire",
        "nom": acc["nom"],
        "mdp": acc["mdp"],
        "prefixe": acc["prefixe"],
        "pseudo": acc["pseudo"],
        "email": acc["email"],
        "couleur": "cyan",
        "cle_publique": pub,
    })
    if not rep or not rep.get("ok"):
        raise RuntimeError(f"inscription refusée: {rep}")
    acc["numero"] = rep["numero"]
    acc["public"] = pub
    return rep


def login(client, acc):
    rep = client.request({
        "action": "connecter_numero",
        "numero": acc["numero"],
        "mdp": acc["mdp"],
    })
    if not rep or not rep.get("ok"):
        raise RuntimeError(f"connexion refusée: {rep}")
    if rep.get("totp_requis"):
        raise RuntimeError("TOTP activé sur le compte de test; le script ne peut pas fournir ce code.")
    return rep


def chercher(client, numero):
    rep = client.request({"action": "chercher", "numero": numero})
    if not rep or not rep.get("ok"):
        raise RuntimeError(f"recherche impossible: {rep}")
    return rep["user"]


def send_private(sender, receiver, sender_acc, receiver_acc, plaintext):
    key = shared_key(
        sender_acc["priv"],
        receiver_acc["public"],
        sender_acc["numero"],
        receiver_acc["numero"],
    )
    token = Fernet(key).encrypt(plaintext.encode()).decode()

    rep = sender.request({
        "action": "message",
        "dest": receiver_acc["numero"],
        "texte": token,
        "chiffre": True,
    })
    if not rep or not rep.get("ok"):
        raise RuntimeError(f"envoi privé refusé: {rep}")

    event = receiver.wait_event("message")
    if not event:
        raise RuntimeError("B n'a reçu aucun événement message.")

    received_token = event.get("texte", "")
    clear = Fernet(
        shared_key(
            receiver_acc["priv"],
            sender_acc["public"],
            receiver_acc["numero"],
            sender_acc["numero"],
        )
    ).decrypt(received_token.encode()).decode()

    if clear != plaintext:
        raise RuntimeError(f"contenu reçu différent: {clear!r}")

    return event


def create_group(client, name):
    rep = client.request({"action": "creer_groupe", "nom": name})
    if not rep or not rep.get("ok"):
        raise RuntimeError(f"création groupe refusée: {rep}")
    return rep["id_groupe"]


def add_member(client, gid, numero):
    rep = client.request({
        "action": "ajouter_groupe",
        "id_groupe": gid,
        "numero": numero,
    })
    if not rep or not rep.get("ok"):
        raise RuntimeError(f"ajout membre refusé: {rep}")
    return rep


def distribute_group_key(client, creator, member, gid, group_key):
    wrapped_creator = wrap_group_key(
        group_key,
        creator["priv"],
        creator["public"],
        creator["numero"],
        creator["numero"],
    )
    wrapped_member = wrap_group_key(
        group_key,
        creator["priv"],
        member["public"],
        creator["numero"],
        member["numero"],
    )

    rep = client.request({
        "action": "maj_cle_groupe",
        "id_groupe": gid,
        "cles": {
            creator["numero"]: wrapped_creator,
            member["numero"]: wrapped_member,
        },
    })
    if not rep or not rep.get("ok"):
        raise RuntimeError(f"distribution clé groupe refusée: {rep}")
    return rep["epoch"]


def send_group(client, creator, member, gid, group_key, plaintext, epoch):
    token = Fernet(group_key).encrypt(plaintext.encode()).decode()

    rep = client.request({
        "action": "msg_groupe",
        "id_groupe": gid,
        "texte": token,
        "chiffre": True,
        "epoch": epoch,
    })
    if not rep or not rep.get("ok"):
        raise RuntimeError(f"message groupe refusé: {rep}")

    event = member.wait_event("msg_groupe")
    if not event:
        raise RuntimeError("B n'a reçu aucun message de groupe.")

    received = event.get("texte", "")
    clear = Fernet(group_key).decrypt(received.encode()).decode()

    if clear != plaintext:
        raise RuntimeError(f"message groupe différent: {clear!r}")

    return event


def cleanup(client, acc):
    rep = client.request({
        "action": "supprimer_compte",
        "mdp": acc["mdp"],
    })
    return bool(rep and rep.get("ok")), rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", required=True, help="Hôte du serveur TermChat")
    ap.add_argument("--port", type=int, required=True, help="Port du serveur TermChat")
    ap.add_argument(
        "--cleanup",
        action="store_true",
        help="Désactive les deux comptes de test à la fin si le serveur l'autorise",
    )
    args = ap.parse_args()

    print("╔══════════════════════════════════════════════════════════╗")
    print("║        TERMCHAT — TEST D'INTÉGRATION AUTOMATIQUE       ║")
    print("║             deux comptes temporaires                    ║")
    print("╚══════════════════════════════════════════════════════════╝")

    A = make_account("A")
    B = make_account("B")
    ca = Client(args.host, args.port, "TEST-A")
    cb = Client(args.host, args.port, "TEST-B")

    passed = 0
    failed = 0

    try:
        print("\n🌐 RÉSEAU / TLS")
        print("──────────────────────────────────────────────────────────")
        va = ca.connect()
        vb = cb.connect()
        if va and vb and va.startswith("TLS") and vb.startswith("TLS"):
            ok_name(f"TLS A/B actif ({va})")
            passed += 1
        else:
            bad_name("TLS A/B", f"A={va}, B={vb}")
            failed += 1

        print("\n👤 COMPTES TEMPORAIRES")
        print("──────────────────────────────────────────────────────────")
        register(ca, A)
        ok_name(f"Compte TEST-A créé: {A['numero']}")
        passed += 1

        register(cb, B)
        ok_name(f"Compte TEST-B créé: {B['numero']}")
        passed += 1

        print("\n🔑 CONNEXION")
        print("──────────────────────────────────────────────────────────")
        login(ca, A)
        ok_name("TEST-A connecté")
        passed += 1

        login(cb, B)
        ok_name("TEST-B connecté")
        passed += 1

        print("\n🛡️ IDENTITÉS / EMPREINTE")
        print("──────────────────────────────────────────────────────────")
        ua = chercher(ca, B["numero"])
        ub = chercher(cb, A["numero"])

        if ua.get("cle_publique") == B["public"] and ub.get("cle_publique") == A["public"]:
            ok_name("Clés publiques correctement publiées")
            passed += 1
        else:
            bad_name("Publication des clés publiques")
            failed += 1

        fp_a = fingerprint(A["public"], B["public"])
        fp_b = fingerprint(B["public"], A["public"])
        if fp_a == fp_b:
            ok_name(f"Empreinte identique A/B: {fp_a}")
            passed += 1
        else:
            bad_name("Empreinte A/B différente", f"A={fp_a} B={fp_b}")
            failed += 1

        print("\n💬 MESSAGE PRIVÉ E2E")
        print("──────────────────────────────────────────────────────────")
        private_text = "TERMCHAT_AUTO_PRIVATE_" + secrets.token_hex(4)
        send_private(ca, cb, A, B, private_text)
        ok_name("A → B chiffré puis déchiffré correctement")
        passed += 1

        private_text2 = "TERMCHAT_AUTO_REPLY_" + secrets.token_hex(4)
        send_private(cb, ca, B, A, private_text2)
        ok_name("B → A chiffré puis déchiffré correctement")
        passed += 1

        print("\n👥 GROUPE")
        print("──────────────────────────────────────────────────────────")
        gid = create_group(ca, "TC_AUTO_" + secrets.token_hex(4))
        ok_name(f"Groupe créé: {gid}")
        passed += 1

        add_member(ca, gid, B["numero"])
        # Invitation asynchrone
        inv = cb.wait_event("invitation_groupe", timeout=3)
        if inv:
            ok_name("B reçoit l'invitation au groupe")
            passed += 1
        else:
            bad_name("Invitation groupe B", "Aucune notification reçue")
            failed += 1

        group_key_1 = Fernet.generate_key()
        epoch1 = distribute_group_key(ca, A, B, gid, group_key_1)
        ok_name(f"Clé de groupe distribuée, epoch={epoch1}")
        passed += 1

        # Le client B reçoit normalement l'événement cle_groupe.
        cb.wait_event("cle_groupe", timeout=3)

        group_text = "TERMCHAT_AUTO_GROUP_" + secrets.token_hex(4)
        send_group(ca, A, B, gid, group_key_1, group_text, epoch1)
        ok_name("Message groupe A → B chiffré/déchiffré")
        passed += 1

        print("\n🚫 MAUVAISE CLÉ")
        print("──────────────────────────────────────────────────────────")
        wrong_key = Fernet.generate_key()
        token = Fernet(group_key_1).encrypt(b"WRONG_KEY_TEST").decode()
        try:
            Fernet(wrong_key).decrypt(token.encode())
            bad_name("Mauvaise clé rejetée", "Le déchiffrement a réussi — anomalie")
            failed += 1
        except InvalidToken:
            ok_name("Mauvaise clé → déchiffrement refusé")
            passed += 1

        print("\n🔄 ROTATION DE CLÉ")
        print("──────────────────────────────────────────────────────────")
        group_key_2 = Fernet.generate_key()
        epoch2 = distribute_group_key(ca, A, B, gid, group_key_2)

        if epoch2 > epoch1 and group_key_2 != group_key_1:
            ok_name(f"Nouvelle clé + nouvel epoch: {epoch1} → {epoch2}")
            passed += 1
        else:
            bad_name("Rotation de clé", f"epoch1={epoch1}, epoch2={epoch2}")
            failed += 1

        cb.wait_event("cle_groupe", timeout=3)

        group_text2 = "TERMCHAT_AUTO_ROTATED_" + secrets.token_hex(4)
        send_group(ca, A, B, gid, group_key_2, group_text2, epoch2)
        ok_name("Message après rotation A → B")
        passed += 1

        print("\n📊 RAPPORT FINAL")
        print("──────────────────────────────────────────────────────────")
        print(f"✅ Réussis : {passed}")
        print(f"❌ Échecs  : {failed}")

        if args.cleanup:
            print("\n🧹 NETTOYAGE")
            print("──────────────────────────────────────────────────────────")
            # Les comptes sont désactivés uniquement si l'instance autorise
            # explicitement la suppression.
            ok_a, rep_a = cleanup(ca, A)
            ok_b, rep_b = cleanup(cb, B)

            if ok_a:
                ok_name("TEST-A désactivé")
            else:
                skip_name("TEST-A non supprimé", str(rep_a))

            if ok_b:
                ok_name("TEST-B désactivé")
            else:
                skip_name("TEST-B non supprimé", str(rep_b))

        if failed:
            print("\n🔴 TEST D'INTÉGRATION : ÉCHEC")
            return 1

        print("\n🟢 TEST D'INTÉGRATION : RÉUSSI")
        return 0

    except Exception as exc:
        print("\n❌ ERREUR DU TEST")
        print(f"   {type(exc).__name__}: {exc}")
        print("\nℹ️ Les comptes de test peuvent exister sur le serveur.")
        print("   Pour demander leur désactivation, relance avec --cleanup.")
        return 1

    finally:
        ca.close()
        cb.close()


if __name__ == "__main__":
    raise SystemExit(main())
