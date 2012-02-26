# -*- coding: utf-8 -*-
# ============================================================================
# Copyright René Mayrhofer, 2012
#
# Contributors:
# * Sebastian Spaeth: refactoring & cleanup
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation; either version 2 or 3 of the License.
# ============================================================================
__all__ = ["Notifier", "jabberbot", "desktopnotifer"]
import warnings
from sys import platform

# Make private copy of jabberbot available, disable deprecation warnings
with warnings.catch_warnings():
    warnings.filterwarnings("ignore",category=DeprecationWarning)
    from . import jabberbot

# Make 'Notifier' available
if platform.startswith('linux'):
    try:
        import pyinotify
    except ImportError:        
        # TODO: Do we have a generic fallback? We should use that then.
        raise ImportError("Failed to import pyinotify. Please install python-"
                          "inotify if you are on Linux.")
    from .filenotifier_lin import Notifier
elif platform.startswith('win'):
    from .filenotifier_win import Notifier
elif platform.startswith('darwin'):
    from .filenotifier_mac import Notifier
else:
    raise Exception("Unknown OS. Please report this value to the "
                    "dvcs-autosync developers: %s" % platform)

# Make desktopnotify available
from .desktopnotify import desktopnotifer
