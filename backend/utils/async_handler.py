from functools import wraps
from fastapi import Request
from utils.api_error import APIError


def async_handler(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except APIError as e:
            raise e  # already structured
        except Exception as e:
            # convert unknown errors → APIError
            raise APIError(
                status_code=500,
                message=str(e),
                errors=["Internal Server Error"]
            )
    return wrapper