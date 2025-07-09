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

# Additional exception classes imported by main.py
class LLMResponseError(AutomoyError):
    """Exception raised for errors related to LLM responses."""
    def __init__(self, message: str):
        self.message = f"LLM Response Error: {message}"
        super().__init__(self.message)

class ObjectiveError(AutomoyError):
    """Exception raised for errors related to objective formulation or processing."""
    def __init__(self, message: str):
        self.message = f"Objective Error: {message}"
        super().__init__(self.message)

class StepError(AutomoyError):
    """Exception raised for errors related to step execution or processing."""
    def __init__(self, step_id: str, message: str):
        self.step_id = step_id
        self.message = f"Step Error (ID: {step_id}): {message}"
        super().__init__(self.message)

class VisualElementError(AutomoyError):
    """Exception raised for errors related to visual elements."""
    def __init__(self, element_id: str = None, message: str = "Unknown error"):
        self.element_id = element_id
        id_str = f" (ID: {element_id})" if element_id else ""
        self.message = f"Visual Element Error{id_str}: {message}"
        super().__init__(self.message)

# We might need more specialized exceptions for other areas:
class OmniParserError(AutomoyError):
    """Exception raised for errors related to OmniParser integration."""
    def __init__(self, message: str):
        self.message = f"OmniParser Error: {message}"
        super().__init__(self.message)

class GUIError(AutomoyError):
    """Exception raised for errors related to GUI operation or communication."""
    def __init__(self, message: str):
        self.message = f"GUI Error: {message}"
        super().__init__(self.message)

class ConfigError(AutomoyError):
    """Exception raised for errors related to configuration loading or access."""
    def __init__(self, message: str):
        self.message = f"Config Error: {message}"
        super().__init__(self.message)

class WebViewError(AutomoyError):
    """Exception raised for errors related to PyWebview operation."""
    def __init__(self, message: str):
        self.message = f"WebView Error: {message}"
        super().__init__(self.message)
