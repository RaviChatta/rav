# compat.py - Universal compatibility layer
import sys
import mimetypes
from typing import Any

class _Compat:
    def __getattr__(self, name: str) -> Any:
        if name == 'imghdr':
            return self._imghdr_compat()
        raise AttributeError(name)

    def _imghdr_compat(self):
        class ImghdrCompat:
            @staticmethod
            def what(file, h=None):
                mime = mimetypes.guess_type(file)[0]
                return mime.split('/')[-1] if mime else None
        return ImghdrCompat()

sys.modules[__name__] = _Compat()
