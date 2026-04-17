#!/usr/bin/env python
"""Start the FastAPI backend with sharding enabled"""

import uvicorn
import sys
import io
import os
import socket
from urllib.request import urlopen

# Fix encoding for Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from app.main import app
from app.sharding_integration import initialize_router
from app.sharded_db import initialize_sharded_db


def _is_port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def _is_backend_healthy(port: int) -> bool:
    try:
        with urlopen(f"http://127.0.0.1:{port}/docs", timeout=2) as response:
            return response.status == 200
    except Exception:
        return False

if __name__ == "__main__":
    host = os.getenv("MODULE_B_HOST", "0.0.0.0")
    port = int(os.getenv("MODULE_B_PORT", "8000"))
    public_host = "localhost" if host in {"0.0.0.0", "127.0.0.1"} else host

    if _is_port_open("127.0.0.1", port):
        if _is_backend_healthy(port):
            print(f"[INFO] Backend already running at http://localhost:{port}")
            print("[INFO] Reusing existing process. No action needed.")
            sys.exit(0)
        print(f"[ERROR] Port {port} is already in use by another process.")
        print(f"[ERROR] Set MODULE_B_PORT to a free port and retry.")
        sys.exit(1)

    print("="*60)
    print("INITIALIZING SHARDED DATABASE")
    print("="*60)
    
    try:
        initialize_sharded_db()
        print("[OK] Database manager initialized")
    except Exception as e:
        print(f"[ERROR] Database initialization failed: {e}")
        sys.exit(1)
    
    try:
        initialize_router()
        print("[OK] Sharding router initialized")
    except Exception as e:
        print(f"[ERROR] Router initialization failed: {e}")
        sys.exit(1)
    
    print("\n" + "="*60)
    print("STARTING FASTAPI BACKEND")
    print("="*60)
    print(f"Backend URL: http://{public_host}:{port}")
    print(f"API Docs:    http://{public_host}:{port}/docs")
    print(f"ReDoc:       http://{public_host}:{port}/redoc")
    print("="*60 + "\n")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )
