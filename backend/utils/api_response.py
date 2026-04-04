class APIResponse:
    def __init__(
        self,
        status_code: int,
        data = None,
        message: str = "Success",
        ):

        self.status_code = status_code
        self.data = data
        self.message = message
        self.success = status_code < 400

    def to_dict(self):
        return {
            "message": self.message,
            "success": self.success,
            "data": self.data
        }
        