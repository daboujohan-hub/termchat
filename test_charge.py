#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test de charge TermChat — ouvre beaucoup de connexions TLS et les garde ouvertes.
by Aboudev Labs CI

    python3 test_charge.py HOTE PORT [NB_CONNEXIONS] [DUREE_SEC] [--insecure] [--debit N]

Exemples :
    python3 test_charge.py localhost 9999 500 30 --insecure
    python3 test_charge.py mon-serveur.com 9999 5000 60 --debit 200

- Ne se connecte à aucun compte et n'envoie AUCUNE action (donc rien n'est écrit dans Firestore).
- --insecure : accepte un certificat auto-signé (à utiliser seulement pour tes tests).
- --debit N  : nombre de nouvelles connexions par seconde (défaut 100).
- Sur la machine de test, lance d'abord : ulimit -n 65535
"""
import asyncio, ssl, sys, time, statistics, collections


def lire_args():
    args = sys.argv[1:]
    insecure = "--insecure" in args
    debit = 100
    if "--debit" in args:
        i = args.index("--debit")
        debit = int(args[i + 1])
        del args[i:i + 2]
    args = [a for a in args if a != "--insecure"]
    if len(args) < 2:
        print(__doc__); sys.exit(1)
    hote, port = args[0], int(args[1])
    nb = int(args[2]) if len(args) > 2 else 100
    duree = int(args[3]) if len(args) > 3 else 20
    return hote, port, nb, duree, insecure, debit


async def un_client(i, hote, port, duree, ctx, debit, res):
    await asyncio.sleep(i / debit)          # montée progressive
    t0 = time.time()
    try:
        r, w = await asyncio.wait_for(asyncio.open_connection(hote, port, ssl=ctx), 20)
    except Exception as e:
        res["echecs"] += 1
        res["erreurs"][type(e).__name__] += 1
        return
    res["latences"].append(time.time() - t0)
    res["connectes"] += 1
    res["ouverts"] += 1
    res["pic"] = max(res["pic"], res["ouverts"])
    try:
        await asyncio.wait_for(r.read(1), duree)   # on attend (le serveur peut nous couper)
        res["coupes_par_serveur"] += 1
    except asyncio.TimeoutError:
        pass
    except Exception:
        res["coupes_par_serveur"] += 1
    finally:
        res["ouverts"] -= 1
        try: w.close()
        except Exception: pass


async def main():
    hote, port, nb, duree, insecure, debit = lire_args()
    ctx = ssl.create_default_context()
    if insecure:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    res = {"connectes": 0, "echecs": 0, "ouverts": 0, "pic": 0, "coupes_par_serveur": 0,
           "latences": [], "erreurs": collections.Counter()}
    print(f"▶ {nb} connexions vers {hote}:{port}, {debit}/s, maintenues {duree}s")
    t0 = time.time()
    taches = [asyncio.create_task(un_client(i, hote, port, duree, ctx, debit, res)) for i in range(nb)]

    async def suivi():
        while True:
            await asyncio.sleep(5)
            print(f"  t={time.time()-t0:5.0f}s  ouvertes={res['ouverts']}  échecs={res['echecs']}")
    s = asyncio.create_task(suivi())
    await asyncio.gather(*taches)
    s.cancel()

    lat = sorted(res["latences"])
    print("\n══ RÉSULTAT ══")
    print(f"Demandées : {nb} | connectées : {res['connectes']} | échecs : {res['echecs']} | pic simultané : {res['pic']}")
    print(f"Coupées par le serveur pendant l'attente : {res['coupes_par_serveur']}")
    if lat:
        print(f"Délai de connexion (TLS compris) : médiane {statistics.median(lat)*1000:.0f} ms | "
              f"95% sous {lat[int(len(lat)*0.95)-1]*1000:.0f} ms | max {lat[-1]*1000:.0f} ms")
    for nom, n in res["erreurs"].most_common(5):
        print(f"  erreur {nom} : {n}")
    taux = 100 * res["connectes"] / nb if nb else 0
    print(f"Taux de réussite : {taux:.1f} %")


if __name__ == "__main__":
    asyncio.run(main())

