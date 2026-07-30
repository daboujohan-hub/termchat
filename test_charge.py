import asyncio, ssl, json, time, sys

HOST = "ballast.proxy.rlwy.net"  # serveur de TEST, pas production
PORT = 57568
NB_CLIENTS = 1000000
MESSAGES_PAR_CLIENT = 100

resultats = {"ok": 0, "echec": 0, "temps": [], "erreurs": []}

async def client_simule(idx, semaphore):
    async with semaphore:
        debut = time.time()
        try:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(HOST, PORT, ssl=ctx), timeout=15
            )

            numero = f"+225071{idx:05d}"
            pkt = {"action":"inscrire","numero":numero,"mdp":"TestCharge123!","nom":f"LoadTest{idx}","pays":"CI"}
            writer.write((json.dumps(pkt) + "\n").encode())
            await writer.drain()
            await asyncio.wait_for(reader.readline(), timeout=10)

            for i in range(MESSAGES_PAR_CLIENT):
                pkt_msg = {"action":"message","dest":numero,"texte":f"Charge {i} client {idx}","chiffre":False}
                writer.write((json.dumps(pkt_msg) + "\n").encode())
                await writer.drain()
                await asyncio.wait_for(reader.readline(), timeout=10)

            writer.close()
            await writer.wait_closed()

            duree = time.time() - debut
            resultats["ok"] += 1
            resultats["temps"].append(duree)
        except Exception as e:
            resultats["echec"] += 1
            resultats["erreurs"].append(str(e))

async def main():
    semaphore = asyncio.Semaphore(100)  # max 100 connexions en parallele reelle a la fois
    print(f"Lancement de {NB_CLIENTS} clients ({MESSAGES_PAR_CLIENT} messages chacun) vers {HOST}:{PORT}...")
    debut_total = time.time()
    taches = [client_simule(i, semaphore) for i in range(NB_CLIENTS)]
    await asyncio.gather(*taches)
    duree_totale = time.time() - debut_total

    print(f"\n--- RESULTATS ---")
    print(f"Succes: {resultats['ok']}/{NB_CLIENTS}")
    print(f"Echecs: {resultats['echec']}/{NB_CLIENTS}")
    if resultats["temps"]:
        t = sorted(resultats["temps"])
        n = len(t)
        print(f"Temps min: {t[0]:.2f}s")
        print(f"Temps median: {t[n//2]:.2f}s")
        print(f"Temps p95: {t[int(n*0.95)]:.2f}s")
        print(f"Temps max: {t[-1]:.2f}s")
    if resultats["erreurs"]:
        print(f"\nExemples d'erreurs (5 premieres):")
        for e in resultats["erreurs"][:5]:
            print(f"  - {e}")
    print(f"\nDuree totale: {duree_totale:.2f}s")
    print(f"Debit: {NB_CLIENTS/duree_totale:.1f} clients/s")

asyncio.run(main())
