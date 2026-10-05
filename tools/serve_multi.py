"""Run the game server on several addresses of this PC at once.

Used by tools/play_tripo.ps1 -Tailscale: the host keeps playing on 127.0.0.1 while
friends on the same Tailscale network reach the server at its 100.x address.
Nothing listens on the public internet.

    python tools/serve_multi.py 127.0.0.1,100.101.102.103 8765
"""
from __future__ import annotations

import socket
import sys
from pathlib import Path

import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    hosts = [h for h in sys.argv[1].split(",") if h]
    port = int(sys.argv[2])
    sockets = []
    for host in hosts:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind((host, port))
        listener.listen(128)
        sockets.append(listener)
    config = uvicorn.Config("server.app:create_app", factory=True, workers=1, access_log=False, proxy_headers=False)
    uvicorn.Server(config).run(sockets=sockets)


if __name__ == "__main__":
    main()
