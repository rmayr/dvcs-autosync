# vim: set et sts=4 sw=4:
import logging

# desktopnotify will point to a class instance containing a .notify() function
desktopnotifer = None

class INotify(object):
    @classmethod
    def _level_to_level_id(cls, level):
        """Finds the identifier of the highest log-level the message matches.
        :Parameters:
            `level` : int
                Representing log level from `logging` module.
        :Returns: an identifier for the respective notification API or None
        """
        if not hasattr(cls, '_levels'):
            raise NotImplementedError

        level = int(level)
        for edge in reversed(sorted(cls._levels.keys())):
            if level >= edge:
                return cls._levels[edge]
        return None

    def notify(self, level, title, text, timeout=float('inf')):
        """Show a desktop notification.
        :Parameters:
            `level` : int
                Representing log level from `logging` module.
            `title` : str
                Title text to use for notification.
            `text` : str
                The actual notification message.
            `timeout` : float
                Duration in seconds to display the notification.
        """
        raise NotImplementedError

#Set up the the KDE notifier
try:
    import dbus
    _bus = dbus.SessionBus()
    _knotify_proxy = _bus.get_object('org.kde.knotify', '/Notify')
    _knotify = dbus.Interface(_knotify_proxy, 'org.kde.KNotify')

    class KNotify(INotify):
        _levels = {logging.INFO:     'notification',
                   logging.WARNING:  'warning',
                   logging.ERROR:    'fatalerror',
                   logging.CRITICAL: 'catastrophe'}

        def __init__(self):
            super(KNotify, self).__init__()

            # Trigger an exception if the KNotify interface isn't available
            self.closeNotification(0)

        def notify(self, level, title, text, timeout=float('inf')):
            event = self._level_to_level_id(level)
            if event is None:
                return

            if timeout == float('inf'):
                timeout = 0
            elif timeout <= 0:
                raise ValueError, "Timeout must be larger than zero (this permits positive infinity)."
            timeout = int(timeout * 1000)

            return self.event(event, 'kde', (), title, text, timeout=timeout)

        def reconfigure(self):
            """Make KNotify reload its configuration."""
            _knotify.reconfigure()

        def closeNotification(self, id):
            """
            :Parameters:
                `id` : int
            """
            _knotify.closeNotification(id)

        def event(self, event, fromApp, contexts, title, text, pixmap=(), actions=(), timeout=0, winId=0):
            """
            :Parameters:
                `event` : str
                `fromApp` : str
                `contexts` : list of variants
                `title` : str
                `text` : str
                `pixmap` : (ay)
                `actions` : list of str
                `timeout` : int
                `winId` : (x)
            :Returns: an `int`, representing an identifier for the created
                notification, 0 (zero) if no notification was created.
            """
            return _knotify.event(event, fromApp, contexts, title, text, pixmap, actions, timeout, winId)

        def update(self, id, title, text, pixmap=(), actions=()):
            """
            :Parameters:
                `id` : int
                `title` : str
                `text` : str
                `pixmap` : (ay)
                `actions` : list of str
            """
            _knotify.update(id, title, text, pixmap, actions)

        def reemit(self, id, contexts):
            """
            :Parameters:
                `id`: int
                `contexts`: list of variants
            """
            _knotify.reemit(id, contexts)

    desktopnotifer = KNotify()
    logging.debug('KDE desktop notify available.')
except:
    pass


try:
    import pynotify, gtk

    class PyNotify(INotify):
        _levels = {logging.INFO:     pynotify.URGENCY_LOW,
                   logging.WARNING:  pynotify.URGENCY_NORMAL,
                   logging.ERROR:    pynotify.URGENCY_CRITICAL,
                   logging.CRITICAL: pynotify.URGENCY_CRITICAL}

        def __init__(self, appname):
            self._icon = None
            super(PyNotify, self).__init__()
            if not pynotify.init(appname):
                raise RuntimeError, "Failed to initialise PyNotify"

        def load_icon(self, name, size, lookup=gtk.ICON_LOOKUP_GENERIC_FALLBACK):
            self._icon = gtk.IconTheme().load_icon(name, size, lookup)

        def notify(self, level, title, text, timeout=float('inf')):
            """
            :param timeout: show notification for 'n' seconds
            """
            urgency = self._level_to_level_id(level)
            if urgency is None:
                return

            notification = pynotify.Notification(title, text)
            if timeout <= 0:
                raise ValueError, "Timeout must be larger than zero (this permits positive infinity)."
            elif timeout < float('inf'):
                notification.set_timeout(timeout*1000)

            if self._icon:
                notification.set_icon_from_pixbuf(self._icon)
            notification.set_urgency(urgency)
            notification.show()
            return notification

    desktopnotifer = PyNotify('autosync application')
    desktopnotifer.load_icon('dvcs-autosync', 48)
    logging.debug('GTK pynotify desktop notify available.')
except:
    pass

try:
    from gntp import notifier
    import os, time
    class GrowlNotifier(INotify):
        def __init__(self, applicationName=None, notifications=None, defaultNotifications=None, applicationIcon=None, hostname=None, password=None):
            self._icon = applicationIcon
            self._notifier = notifier.GrowlNotifier(applicationName, notifications, defaultNotifications, self._icon, hostname, password)
            self._notifier.register()

            super(GrowlNotifier, self).__init__()

        def notify(self, level, title, text, timeout=float('inf')):
            self._notifier.notify('Every notifications', title, text, self._icon)
            # When sending multiple notifications at the same time, Growl seems to only consider the latest. This little delay prevent that.
            time.sleep(0.1)

    desktopnotifer = GrowlNotifier('AutoSync', ['Every notifications'],
                                   applicationIcon=os.path.abspath('/usr/share/icons/hicolor/48x48/apps/dvcs-autosync.png'))
    logging.debug('Growl desktop notify available.')
except:
    pass

#if desktopnotier is still "None", no backend was available.
if not desktopnotifer:
    logging.debug('No Desktop notify backend available.')
