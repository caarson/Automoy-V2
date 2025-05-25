class ModelNotRecognizedException(Exception):
    """
    Raised when the given model name is not recognized by the system.

    For instance, this exception can be thrown when an unsupported
    or unknown model name is passed to a function that expects
    a known/supported model.

    Example:
        supported_models = ["gpt-3.5-turbo", "gpt-4", "my-local-model"]
        if model_name not in supported_models:
            raise ModelNotRecognizedException(model_name, supported_models)
    """

    def __init__(self, model_name: str = None, supported_models: list = None):
        """
        :param model_name: The name of the model that was unrecognized.
        :param supported_models: A list of valid model names, if available.
        """
        self.model_name = model_name
        self.supported_models = supported_models if supported_models else []

        message = f"Model '{model_name}' is not recognized."
        if self.supported_models:
            message += f" Supported models are: {', '.join(self.supported_models)}."
        super().__init__(message)

class AutomoyError(Exception):
    """Base exception class for Automoy specific errors."""
    pass

class OperationError(AutomoyError):
    """Exception raised for errors during an operation execution."""
    def __init__(self, operation_name: str, message: str):
        self.operation_name = operation_name
        self.message = f"Error in operation '{operation_name}': {message}"
        super().__init__(self.message)
