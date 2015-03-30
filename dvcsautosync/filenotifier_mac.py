from fsevents import Observer
from fsevents import Stream
import threading
import time
import logging
import os

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

def Notifier(path, ignoreabsolutepaths, ignorefilepatterns, handler,
             read_freq=0):
    notifier = MacOSFileChangeHandlerAdapter(path, ignoreabsolutepaths, handler)
    notifier.start()
    return notifier
