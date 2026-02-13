class State:

    PENDING = "pending"
    LOCKED = "locked"
    RUNNING = "running"

    SUCCESS = "success"
    FALLBACK = "fallback"
    SUPPRESSED = "suppressed"

    FAILED = "failed"
    CANCELLED = "cancelled"

    # Helper sets
    ACTIVE_STATES = {PENDING, LOCKED, RUNNING}
    TERMINAL_STATES = {SUCCESS, FALLBACK, FAILED, CANCELLED}
    
    @classmethod
    def is_terminal(cls, status: str) -> bool:
        """Check if a status represents a completed execution."""
        return status in cls.TERMINAL_STATES

