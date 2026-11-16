from contextlib import contextmanager

@contextmanager
def raises(exc_type):
    try:
        yield
    except exc_type:
        return
    raise AssertionError(f"Expected {exc_type.__name__} to be raised, but no matching exception occurred.")
