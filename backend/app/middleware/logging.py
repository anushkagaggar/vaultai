import time
import logging
from fastapi import Request

logger = logging.getLogger("vaultai")


async def log_requests(request: Request, call_next):

    start = time.time()

    response = await call_next(request)

    duration = round(time.time() - start, 3)

    user_id = getattr(request.state, "user_id", None)

    logger.info(
        f"{request.method} "
        f"{request.url.path} "
        f"user={user_id} "
        f"status={response.status_code} "
        f"time={duration}s"
    )

    return response
