# -*- coding: utf-8 -*-
# ============================================================================
# Copyright René Mayrhofer, 2012-
#
# Contributors:
# * Sebastian Spaeth: refactoring & cleanup
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation; either version 2 or 3 of the License.
# ============================================================================
__all__ = ["Notifier", "jabberbot"]
import warnings

# Make 'Notifier' available
from .filenotifier import Notifier
# Make private copy of jabberbot available, disable deprecation warnings
with warnings.catch_warnings():
    warnings.filterwarnings("ignore",category=DeprecationWarning)
    from . import jabberbot

