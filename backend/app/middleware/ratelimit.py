import time
from fastapi import Request, HTTPException

RATE_LIMIT = 5        # requests
WINDOW = 60           # seconds

clients = {}


def rate_limit(request: Request):
    ip = request.client.host
    now = time.time()

    if ip not in clients:
        clients[ip] = []

    # keep only recent hits
    clients[ip] = [
        t for t in clients[ip]
        if now - t < WINDOW
    ]

    if len(clients[ip]) >= RATE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Try later."
        )

    clients[ip].append(now)
