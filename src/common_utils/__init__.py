import traceback


def record_error_stack(func):
    def inner_func(*arg, **kwargs):
        # noinspection PyBroadException
        try:
            func(*arg, **kwargs)
        except:
            traceback.print_exc()

    return inner_func
