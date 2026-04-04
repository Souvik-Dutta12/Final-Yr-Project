class APIError(Exception):
    def __init__(
            self,
            status_code: int,
            message: str = "Something went wrong !!...", 
            errors: list = None,
            ):
        super().__init__(message)

        self.status_code = status_code
        self.message = message
        self.success = False
        self.data = None
        self.errors = errors if errors is not None else []
    
    def to_dict(self):
        return {
            "message": self.message,
            "success": self.success,
            "data": self.data,
            "errors": self.errors
        }
