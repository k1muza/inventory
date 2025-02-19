import time
from functools import wraps
from logging import getLogger

logger = getLogger(__name__)

def timer(func):
    """Prints the execution time of a function. Used as a decorator."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        end = time.perf_counter()
        logger.debug(f"{func.__name__!r} executed in {(end-start):.3f}s")
        return result
    return wrapper
