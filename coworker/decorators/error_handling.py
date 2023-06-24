import time

from functools import wraps
from typing import Callable
from psycopg2 import ProgrammingError

from ..exceptions.exceptions import RateLimitException, RequestException, ProgrammingErrorException

def handle_errors_with_retry(num_retries: int = 4, base_backoff_time: int = 1) -> Callable:
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(num_retries + 1):
                try:
                    result = func(*args, **kwargs)
                    return result
                except RequestException as e:
                    response = e.response
                    if attempt < num_retries:
                        if response.status_code == 429:  # Rate Limit Error
                            sleep_time = base_backoff_time * (2 ** attempt)
                            time.sleep(sleep_time)
                        else:
                            # Retry on all other cases
                            continue
                    else:
                        raise RateLimitException("Still rate-limited after multiple retries.")
                except Exception as e:
                    print(f"Error {response.status_code}: {response.text}")
        return wrapper
    return decorator

def handle_database_errors(func: Callable) -> Callable:
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            return result
        except ProgrammingError as e:
            raise ProgrammingErrorException("ProgrammingError:", e)
        except Exception as e:
            print("Error:", e)
    return wrapper