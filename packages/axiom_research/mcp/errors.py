class McpRuntimeError(Exception):
    def __init__(self, error_type: str, message: str, *, retryable: bool = False):
        self.error_type = error_type
        self.message = message
        self.retryable = retryable
        super().__init__(f"[{error_type}] {message}")

    def as_dict(self) -> dict[str, str | bool]:
        return {
            "error_type": self.error_type,
            "message": self.message,
            "retryable": self.retryable,
        }


def redact(text: str, secrets: tuple[str, ...] = ()) -> str:
    safe = text
    for secret in secrets:
        if secret:
            safe = safe.replace(secret, "[REDACTED]")
    return safe
