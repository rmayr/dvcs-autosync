import pyinotify
import logging
import os

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
