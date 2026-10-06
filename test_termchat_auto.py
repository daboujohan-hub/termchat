#!/usr/bin/env python3
import argparse, hashlib, os, subprocess, sys, time
from pathlib import Path

def result(name, ok, detail=''):
    print(('✅' if ok else '❌'), name, (f'— {detail}' if detail else ''))
    return ok

def crypto_tests():
    print('\n🔐 TESTS CRYPTOGRAPHIQUES LOCAUX')
    try:
        from cryptography.fernet import Fernet, InvalidToken
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import x25519
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    except Exception as e:
        result('Dépendance cryptography', False, 'python -m pip install cryptography')
        return 0, 1
    p=f=0
    a=x25519.X25519PrivateKey.generate(); b=x25519.X25519PrivateKey.generate()
    sa=a.exchange(b.public_key()); sb=b.exchange(a.public_key())
    if result('X25519 / ECDH A ↔ B', sa==sb): p+=1
    else: f+=1
    info=b'termchat-e2e-v2'
    ka=HKDF(algorithm=hashes.SHA256(),length=32,salt=None,info=info).derive(sa)
    kb=HKDF(algorithm=hashes.SHA256(),length=32,salt=None,info=info).derive(sb)
    if result('HKDF-SHA256', ka==kb): p+=1
    else: f+=1
    key=__import__('base64').urlsafe_b64encode(ka); box=Fernet(key); msg=b'TERMCHAT_AUTO_TEST'; token=box.encrypt(msg)
    if result('Fernet chiffrement + déchiffrement', box.decrypt(token)==msg): p+=1
    else: f+=1
    try: Fernet(Fernet.generate_key()).decrypt(token); wrong=False
    except InvalidToken: wrong=True
    if result('Mauvaise clé → déchiffrement refusé', wrong): p+=1
    else: f+=1
    old=Fernet.generate_key(); new=Fernet.generate_key()
    if result('Rotation de clé de groupe', old!=new): p+=1
    else: f+=1
    raw=lambda pub: pub.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    fp1=hashlib.sha256(raw(a.public_key())+raw(b.public_key())).hexdigest()
    fp2=hashlib.sha256(raw(a.public_key())+raw(b.public_key())).hexdigest()
    if result('Empreinte déterministe', fp1==fp2): p+=1
    else: f+=1
    b2=x25519.X25519PrivateKey.generate().public_key(); fp3=hashlib.sha256(raw(a.public_key())+raw(b2)).hexdigest()
    if result('Changement de clé → empreinte différente', fp1!=fp3): p+=1
    else: f+=1
    return p,f

def server_tests(path):
    print('\n🐍 TESTS DU SERVEUR')
    if not path:
        print('⏭️ Démarrage serveur — SKIP (utilise --server server.py)'); return 0,0
    pth=Path(path).expanduser().resolve()
    if not pth.exists(): result('Fichier serveur',False,f'Introuvable: {pth}'); return 0,1
    try:
        compile(pth.read_text(encoding='utf-8'),str(pth),'exec'); result('Syntaxe Python du serveur',True); return 1,0
    except SyntaxError as e: result('Syntaxe Python du serveur',False,f'Ligne {e.lineno}: {e.msg}'); return 0,1

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--server'); args=ap.parse_args()
    print('╔══════════════════════════════════════════════════════════╗\n║             TERMCHAT — TEST AUTOMATIQUE                 ║\n║                 mode NON DESTRUCTIF                     ║\n╚══════════════════════════════════════════════════════════╝')
    p=f=0; a,b=crypto_tests(); p+=a; f+=b; a,b=server_tests(args.server); p+=a; f+=b
    print('\n📊 RAPPORT FINAL'); print('─'*58); print(f'✅ Réussis : {p}'); print(f'❌ Échecs  : {f}')
    print('\n🟢 Aucun échec.' if not f else '\n🔴 Des tests ont échoué.')
    print('⚠️ Les tests réseau réels ne sont pas simulés ici : le script ne touche pas à tes comptes.')
if __name__=='__main__': main()
