import win32file, win32con
from collections import deque
import logging
import os

class WindowsFileChangeHandlerAdapter(object):
    FILE_LIST_DIRECTORY = 0x0001
    EVT_CREATE = 1
    EVT_DELETE = 2
    EVT_MODIFY = 3
    EVT_MOVE_FROM = 4
    EVT_MOVE_TO = 5

    def __init__(self, path, ignoreabsolutepaths, handler):
        super(WindowsFileChangeHandlerAdapter, self).__init__()
        self.handler = handler
        self.ignoreabsolutepaths = ignoreabsolutepaths
        self.path = path

        self._eventq = deque()
        self.hDir = win32file.CreateFile(
          self.path,
          self.FILE_LIST_DIRECTORY,
          win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE,
          None,
          win32con.OPEN_EXISTING,
          win32con.FILE_FLAG_BACKUP_SEMANTICS,
          None
        )

    def stop(self):
        self.hDir = None

    # This is to mimic the event-type of inotify
    class MyEvent():
        def __init__(self, dir, pathname, action):
            self.dir = dir
            self.pathname = pathname
            self.maskname = [ "", "IN_CREATE", "IN_DELETE", "IN_MODIFY", "IN_DELETE", "IN_CREATE"][action]

    def process_events(self):
        pass

    def check_events(self):
        pass

    def read_events(self):
        if self.hDir is None:
            return

        results = win32file.ReadDirectoryChangesW (
                self.hDir,
                1024,
                True,
                win32con.FILE_NOTIFY_CHANGE_FILE_NAME |
                win32con.FILE_NOTIFY_CHANGE_DIR_NAME |
                win32con.FILE_NOTIFY_CHANGE_ATTRIBUTES |
                win32con.FILE_NOTIFY_CHANGE_SIZE |
                win32con.FILE_NOTIFY_CHANGE_LAST_WRITE |
                win32con.FILE_NOTIFY_CHANGE_SECURITY,
                None,
                None
                )

        for action, file in results:
            full_filename = os.path.join(self.path, file)

            # Check if this file is ignored
            if filter(lambda s: full_filename.startswith(s), self.ignoreabsolutepaths):
                continue

            event = self.MyEvent(os.path.isdir(file), file, action)
            if action == self.EVT_CREATE or action == self.EVT_MOVE_TO:
                self.handler._queue_action(event, 'add', [event.pathname])
            elif action == self.EVT_DELETE or action == self.EVT_MOVE_FROM:
                if os.path.exists(event.pathname):
                    logging.debug('Ignoring file delete event on %s, as it still exists - it was probably immediately re-created by the application', event.pathname)
                    continue
                self.handler._queue_action(event, 'rm', [event.pathname])
            elif action == self.EVT_MODIFY:
                self.handler._queue_action(event, 'modify', [event.pathname])


def Notifier(path, ignoreabsolutepaths, ignorefilepatterns, handler,
             read_freq=0):
    return WindowsFileChangeHandlerAdapter(path, ignoreabsolutepaths, handler)
