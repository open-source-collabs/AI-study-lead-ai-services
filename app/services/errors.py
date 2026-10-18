class LLMConfigurationError(RuntimeError):
    pass


class LLMProviderError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class InvalidModelOutput(RuntimeError):
    pass
