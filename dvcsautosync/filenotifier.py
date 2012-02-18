import logging
import os

try:
    import pyinotify

    # The definition of this class has to be OS arbitrated because pyinotify can't be
    # imported under windows and inheriting from pyinotify.ProcessEvent needs it...
    class LinuxFileChangeHandlerAdapter(pyinotify.ProcessEvent):
        def __init__(self, pevent=None, handler=None):
            super(LinuxFileChangeHandlerAdapter, self).__init__(pevent)
            self.handler = handler

        def process_IN_DELETE(self, event):
            # sanity check - don't remove file if it still exists in the file system!
            if os.path.exists(event.pathname):
                logging.debug('Ignoring file delete event on %s, as it still exists - it was probably immediately re-created by the application', event.pathname)
                return
             
            self.handler._queue_action(event, 'rm', [event.pathname])

        def process_IN_CREATE(self, event):
            # sanity check - don't add file if it (no longer) exists in the file system!
            if not os.path.exists(event.pathname):
                logging.debug('Ignoring file create event on %s, as it (no longer) exists - it was probably created as a temporary file and immediately removed by the application', event.pathname)
                return

            self.handler._queue_action(event, 'add', [event.pathname])

        def process_IN_MODIFY(self, event):
            self.handler._queue_action(event, 'modify', [event.pathname])

        def process_IN_CLOSE_WRITE(self, event):
            self.handler._queue_action(event, 'modify', [event.pathname])

        def process_IN_ATTRIB(self, event):
            self.handler._queue_action(event, 'modify', [event.pathname])

        def process_IN_MOVED_TO(self, event):
            try:
                if event.src_pathname:
                    logging.debug('Detected moved file from %s to %s', event.src_pathname, event.pathname)
                    self._handler.queue_action(event, 'move', [event.src_pathname, event.pathname], act_on_dirs=True)
                else:
                    logging.debug('Moved file to %s, but unknown source, will simply add new file', event.pathname)
                    self.handler._queue_action(event, 'add', [event.pathname], act_on_dirs=True)
            except AttributeError:
                # we don't even have the attribute in the event, so also add
                logging.debug('Moved file to %s, but unknown source, will simply add new file', event.pathname)
                self.handler._queue_action(event, 'add', [event.pathname], act_on_dirs=True)

    def Notifier(path, ignoreabsolutepaths, ignorefilepatterns, handler, read_freq=0):
        exclude = pyinotify.ExcludeFilter(ignoreabsolutepaths)
        watch_manager = pyinotify.WatchManager()

        # FIXME: frequency doesn't work....
        notifier = pyinotify.Notifier(watch_manager, LinuxFileChangeHandlerAdapter(handler = handler), read_freq=read_freq)

        # coalescing events needs pyinotify >= 0.9, so make this optional
        try:
            notifier.coalesce_events()
        except AttributeError as e:
            logging.warning('Cannot coalesce events, pyinotify does not seem to support it (maybe too old): %s', e)

        mask = pyinotify.IN_DELETE \
             | pyinotify.IN_CREATE \
             | pyinotify.IN_CLOSE_WRITE \
             | pyinotify.IN_ATTRIB \
             | pyinotify.IN_MOVED_FROM \
             | pyinotify.IN_MOVED_TO \
             | pyinotify.IN_DONT_FOLLOW \
             | pyinotify.IN_ONLYDIR

        try:
            logging.debug('Adding recursive, auto-adding watch for path %s with event mask %d', path, mask)
            wd = watch_manager.add_watch(path, mask, rec=True, auto_add=True, quiet=False, exclude_filter=exclude)
            if wd <= 0:
                logging.warning('Unable to add watch for path %s - this will not work', path)
        except pyinotify.WatchManagerError, e:
            logging.warning("pyinotify.WatchManagerError: %s, %s", e, e.wmd)

        return notifier
except:
    pass

try:
    from collections import deque
    import win32file, win32con

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

    def Notifier(path, ignoreabsolutepaths, ignorefilepatterns, handler, read_freq=0):
        return WindowsFileChangeHandlerAdapter(path, ignoreabsolutepaths, handler)
except:
    pass

try:
    from fsevents import Observer
    from fsevents import Stream
    import time

    class MacOSFileChangeHandlerAdapter(threading.Thread):
        def __init__(self, path, ignoreabsolutepaths, handler):
            threading.Thread.__init__(self)
            self.handler = handler
            self.ignoreabsolutepaths = ignoreabsolutepaths
            self.path = path
    
        # This is to mimic the event-type of inotify
        class MyEvent():
            def __init__(self, dir, pathname, action):
                self.dir = dir
                self.pathname = pathname
                masks = {   # from doc : http://developer.apple.com/library/mac/#documentation/Darwin/Reference/FSEvents_Ref/FSEvents_h/index.html#HeaderDoc_enums
                            256:"IN_CREATE", # created
                            512:"IN_DELETE", # removed
                            # in doc, but don't seem to be used, included to prevent potential bug
                            2048:"IN_MODIFY", # renamed
                            4096:"IN_MODIFY", # modified
                            0x00000400:'InodeMetaMod',
                            0x00002000:'FinderInfoMod',
                            0x00004000:'ChangeOwner',
                            0x00008000:'XattrMod',
                            # not in doc, but actually used
                            64:"IN_DELETE", # before rename
                            128:"IN_CREATE", # after rename
                            2:"IN_MODIFY",
                        }
                self.maskname = masks[action]
                print self.maskname
        
        def __call__(self, event):
            for ignoreabsolutepath in self.ignoreabsolutepaths:
                if event.name.startswith(ignoreabsolutepath):
                    return
                    
            event = self.MyEvent(os.path.isdir(event.name), event.name, event.mask)
            
            if event.maskname == "IN_CREATE": #CREATE or MOVE_TO
                self.handler._queue_action(event, 'add', [event.pathname], act_on_dirs=True)
            elif event.maskname == "IN_DELETE": #DELETE or MOVE_FROM
                if os.path.exists(event.pathname):
                    logging.debug('Ignoring file delete event on %s, as it still exists - it was probably immediately re-created by the application', event.pathname)
                    return
                self.handler._queue_action(event, 'rm', [event.pathname], act_on_dirs=True)
            elif event.maskname == "IN_MODIFY": #MODIFY:
                self.handler._queue_action(event, 'modify', [event.pathname], act_on_dirs=True)
        
        def run(self):
            
            observer = Observer()
            observer.start()

            #handler = self.process_event(self)
            
            stream = Stream(self, self.path, file_events=True)
            observer.schedule(stream)

        def process_events(self):
            pass

        def check_events(self):
            pass

        def read_events(self):
            time.sleep(10)

    def Notifier(path, ignoreabsolutepaths, ignorefilepatterns, handler, read_freq=0):
        notifier = MacOSFileChangeHandlerAdapter(path, ignoreabsolutepaths, handler)
        notifier.start()
        return notifier
except:
    pass
