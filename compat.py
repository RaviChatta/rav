# compat.py
import sys
import mimetypes

class ImghdrCompat:
    @staticmethod
    def what(file, h=None):
        return mimetypes.guess_type(file)[0]

sys.modules['imghdr'] = ImghdrCompat()
