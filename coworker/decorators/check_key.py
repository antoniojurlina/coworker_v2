from functools import wraps

from ..exceptions.exceptions import MissingAPIKeyException

def check_key_decorator(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if args[0].open_ai_key is None:
            raise MissingAPIKeyException("Missing OpenAI key.")
        return func(*args, **kwargs)

    return wrapper