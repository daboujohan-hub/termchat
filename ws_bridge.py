#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TermChat v6.0 — Bridge WebSocket → TCP
Permet aux navigateurs web de se connecter au serveur TCP via WebSocket.
Lance ce fichier en même temps que server.py.
"""

import asyncio, json, os, websockets

TCP_HOST = os.environ.get("TCP_HOST", "127.0.0.1")
TCP_PORT = int(os.environ.get("PORT", 9999))
WS_PORT  = int(os.environ.get("WS_PORT", 8765))

async def bridge(websocket):
    """Pont entre 1 client WebSocket (navigateur) et le serveur TCP."""
    tcp_reader, tcp_writer = None, None
    try:
        # Connexion au serveur TCP
        tcp_reader, tcp_writer = await asyncio.open_connection(TCP_HOST, TCP_PORT)
        print(f"[Bridge] Nouveau client web connecté → TCP {TCP_HOST}:{TCP_PORT}")

        async def ws_vers_tcp():
            """Reçoit du navigateur, envoie au TCP."""
            async for msg in websocket:
                tcp_writer.write((msg + "\n").encode())
                await tcp_writer.drain()

        async def tcp_vers_ws():
            """Reçoit du TCP, envoie au navigateur."""
            while True:
                ligne = await tcp_reader.readline()
                if not ligne: break
                await websocket.send(ligne.decode("utf-8", errors="replace").strip())

        await asyncio.gather(ws_vers_tcp(), tcp_vers_ws())

    except Exception as e:
        print(f"[Bridge] Erreur: {e}")
    finally:
        if tcp_writer:
            try: tcp_writer.close()
            except: pass
        print("[Bridge] Client web déconnecté.")

async def main():
    print(f"╔══════════════════════════════════════╗")
    print(f"║  TermChat Bridge WebSocket v6.0      ║")
    print(f"║  WS:{WS_PORT} → TCP:{TCP_PORT}              ║")
    print(f"╚══════════════════════════════════════╝")
    async with websockets.serve(bridge, "0.0.0.0", WS_PORT):
        print(f"✅ Bridge actif sur ws://0.0.0.0:{WS_PORT}")
        await asyncio.Future()  # tourne indéfiniment

if __name__ == "__main__":
    asyncio.run(main())
