from app.orchestrator.state import State

def map_execution_to_http(execution, result):
    """
    Converts internal execution state into API contract response.
    This isolates API behavior from runner logic.
    """

    # SUCCESS or FALLBACK → ready response
    if execution.status in (State.SUCCESS, State.FALLBACK):
        return {
            "status": "ready",
            "execution_id": execution.id,
            "cached": False,   # will change later
            "data": result
        }

    # LOCKED or RUNNING → client must poll
    if execution.status in (State.LOCKED, State.RUNNING, State.PENDING):
        return {
            "status": "processing",
            "execution_id": execution.id,
            "cached": False
        }

    # FAILED
    if execution.status == State.FAILED:
        return {
            "status": "failed",
            "execution_id": execution.id,
            "error": execution.error_message
        }

    # safety fallback
    return {
        "status": "unknown",
        "execution_id": execution.id
    }
