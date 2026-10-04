"""Optional, thread-scoped idle-sleep request. It cannot prevent manual sleep."""
import ctypes
import os


_CONTINUOUS = 0x80000000
_SYSTEM_REQUIRED = 0x00000001


class PowerRequestError(RuntimeError):
    def __init__(self):
        super().__init__('keep_awake_failed')


def _set_execution_state(flags):
    if os.name != 'nt':
        raise PowerRequestError()
    api = ctypes.WinDLL('kernel32', use_last_error=True).SetThreadExecutionState
    api.argtypes = [ctypes.c_uint]
    api.restype = ctypes.c_uint
    return api(flags)


class KeepAwake:
    """Enter and exit on the monitor thread; preserve its previous requirements."""
    def __init__(self, enabled=False):
        if type(enabled) is not bool:
            raise ValueError('invalid_keep_awake')
        self.enabled = enabled
        self.active = False
        self.previous = None

    def __enter__(self):
        if self.enabled:
            try:
                self.previous = _set_execution_state(_CONTINUOUS | _SYSTEM_REQUIRED)
                if not self.previous:
                    raise PowerRequestError()
            except Exception:
                raise PowerRequestError() from None
            self.active = True
        return self

    def __exit__(self, exc_type, *_):
        if self.active:
            try:
                if not _set_execution_state(self.previous | _CONTINUOUS):
                    raise PowerRequestError()
                self.active = False
            except Exception:
                # Keep the original failure when unwinding a failed read. The
                # worker exits either way, ending its thread-scoped request.
                if exc_type is None:
                    raise PowerRequestError() from None
