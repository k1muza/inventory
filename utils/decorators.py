import time
from functools import wraps

def timer(func):
    """Prints the execution time of a function."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        end = time.perf_counter()
        print(f"{func.__name__!r} executed in {(end-start):.3f}s")
        return result
    return wrapper
