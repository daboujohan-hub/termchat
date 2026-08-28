import json, os, re, subprocess, time, base64, urllib.request
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

ETAT_FICHIER = "dernier_sms_traite.json"
EXPEDITEURS_VALIDES = ("moovmoney", "wave")


# ─── Extraction (memes regles que extraire_paiement.py) ───
def extraire_paiement(texte_sms, expediteur):
    if "credit de communication" in texte_sms.lower():
        return None

    if "wave" in expediteur.lower():
        m = re.search(
            r"Vous avez recu\s+([\d.,]+)\s*F.*?"
            r"De\s+(.+?)\s*\((\d+)\).*?"
            r"([A-Z0-9]{10,})\s*$",
            texte_sms, re.IGNORECASE | re.DOTALL,
        )
        if m:
            return {
                "operateur": "wave",
                "montant": m.group(1).replace(".", "").replace(",", ""),
                "expediteur_nom": m.group(2).strip(),
                "expediteur_numero": m.group(3).strip(),
                "reference": m.group(4).strip(),
            }

    if "moov" in expediteur.lower():
        m = re.search(
            r"[Dd]epot de\s+([\d.,]+)\s*FCFA.*?"
            r"par\s+(.+?)\n.*?"
            r"Ref\s*:\s*([A-Z0-9]+)",
            texte_sms, re.IGNORECASE | re.DOTALL,
        )
        if m:
            return {
                "operateur": "moov",
                "montant": m.group(1).replace(".", "").replace(",", ""),
                "expediteur_nom": m.group(2).strip(),
                "reference": m.group(3).strip(),
            }
    return None


# ─── Lecture des SMS via Termux:API ───
def lire_sms(limite=50):
    out = subprocess.run(
        ["termux-sms-list", "-l", str(limite)],
        capture_output=True, text=True, check=True,
    )
    return json.loads(out.stdout)


def charger_dernier_id_traite():
    if os.path.exists(ETAT_FICHIER):
        with open(ETAT_FICHIER) as f:
            return json.load(f).get("dernier_id", 0)
    return 0


def sauver_dernier_id_traite(id_):
    with open(ETAT_FICHIER, "w") as f:
        json.dump({"dernier_id": id_}, f)


# ─── Auth Firestore (meme mecanisme que reset_mdp_leger.py) ───
def b64url(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

def obtenir_token_firestore():
    creds_env = os.environ.get("FIREBASE_CREDS", "")
    if creds_env:
        creds = json.loads(creds_env)
    else:
        with open("firebase-credentials.json", "r", encoding="utf-8") as f:
            creds = json.load(f)

    project_id = creds["project_id"]
    client_email = creds["client_email"]
    private_key = serialization.load_pem_private_key(
        creds["private_key"].encode(), password=None
    )
    now = int(time.time())
    header = {"alg": "RS256", "typ": "JWT"}
    claims = {
        "iss": client_email,
        "scope": "https://www.googleapis.com/auth/datastore",
        "aud": "https://oauth2.googleapis.com/token",
        "iat": now, "exp": now + 3600,
    }
    s1 = b64url(json.dumps(header).encode())
    s2 = b64url(json.dumps(claims).encode())
    signature = private_key.sign(f"{s1}.{s2}".encode(), padding.PKCS1v15(), hashes.SHA256())
    jwt_token = f"{s1}.{s2}.{b64url(signature)}"

    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=f"grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer&assertion={jwt_token}".encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        access_token = json.loads(resp.read())["access_token"]
    return access_token, project_id


def enregistrer_paiement_firestore(access_token, project_id, paiement, sms_id, recu_le):
    # id du document = la reference du paiement (evite les doublons naturellement)
    doc_url = (
        f"https://firestore.googleapis.com/v1/projects/{project_id}"
        f"/databases/(default)/documents/paiements_confirmes_sms/{paiement['reference']}"
    )
    body = {
        "fields": {
            "operateur": {"stringValue": paiement["operateur"]},
            "montant": {"integerValue": paiement["montant"]},
            "expediteur_nom": {"stringValue": paiement.get("expediteur_nom", "")},
            "reference": {"stringValue": paiement["reference"]},
            "statut": {"stringValue": "non_utilise"},
            "sms_id": {"integerValue": str(sms_id)},
            "recu_le": {"stringValue": recu_le},
        }
    }
    req = urllib.request.Request(
        doc_url, data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        method="PATCH",
    )
    urllib.request.urlopen(req, timeout=15)


def main():
    dernier_id = charger_dernier_id_traite()
    sms_list = lire_sms(50)
    nouveaux = [s for s in sms_list if s["_id"] > dernier_id]
    if not nouveaux:
        print("Aucun nouveau SMS.")
        return

    paiements_trouves = []
    max_id = dernier_id
    for sms in nouveaux:
        max_id = max(max_id, sms["_id"])
        expediteur = sms.get("address", "")
        if not any(e in expediteur.lower() for e in EXPEDITEURS_VALIDES):
            continue
        paiement = extraire_paiement(sms.get("body", ""), expediteur)
        if paiement:
            paiements_trouves.append((paiement, sms["_id"], sms.get("received", "")))

    if paiements_trouves:
        access_token, project_id = obtenir_token_firestore()
        for paiement, sms_id, recu_le in paiements_trouves:
            enregistrer_paiement_firestore(access_token, project_id, paiement, sms_id, recu_le)
            print(f"Enregistre: {paiement['operateur']} {paiement['montant']}F ref={paiement['reference']}")
    else:
        print(f"{len(nouveaux)} nouveau(x) SMS examine(s), aucun paiement Mobile Money valide dedans.")

    sauver_dernier_id_traite(max_id)


if __name__ == "__main__":
    INTERVALLE_SECONDES = int(os.environ.get("INTERVALLE_SURVEILLANCE", "30"))
    print(f"Surveillance des paiements SMS demarree (verification toutes les {INTERVALLE_SECONDES}s). Ctrl+C pour arreter.")
    while True:
        try:
            main()
        except Exception as e:
            print(f"Erreur pendant la verification: {e}")
        time.sleep(INTERVALLE_SECONDES)

