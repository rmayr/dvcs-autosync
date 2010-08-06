#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Usage:
#   ./autosync.py [config file, default is ~/.autosync]
#
# Background monitoring |path| and its subdirectories for modifications on
# files and automatically commits the changes to git. This script assumes
# that the passed directory is (a subdirectory) of a checkout out git tree.
# A PID file is written to [pidfile] for killing the daemon later on.
# Optionally, an [ignores] file is read with one exclusion pattern per line
# and files matching any of the patterns are ignored. This will typically be
# the .gitignore file already existing the git tree.
#
# Example:
#   ./autosync.py /my-git-work-tree
#
# Note that for Jabber login, there probably needs to be a 
# _xmpp-client._tcp.<domain name of jabber account> SRV entry in DNS so that 
# the Python XMPP module can look up the server and port to use. Without such 
# an SRV entry, Jabber login may fail even if the account details are correct 
# and the server is reachable.
#
# Note, when there are errors 
#  ERROR:pyinotify:add_watch: cannot watch ...
# on startup, it will either be an invalid file or directory name which can 
# not be watched for changes, or the number of files a user may watch 
# concurrently using the kernel inotify interface has reached the set limit.
# In the latter case, the limit can be changed by modifying the sysctl variable
# fs.inotify.max_user_watches and increasing it to a sufficient value 
# (e.g. 500000).
#
# Dependencies:
#   Linux, Python 2.6, Pyinotify, JabberBot (>= 0.9)
# Recommended packages:
#   Pynotify for desktop notifications
#
import sys, signal, os, time, subprocess, threading, fnmatch, pyinotify, ConfigParser, jabberbot
botcmd = jabberbot.botcmd

# some global variables, will be initialized in main
desktopnotifykde = False
desktopnotifygnome = False
knotify = None
notifier = None
bot = None

def printmsg(title, msg):
    if desktopnotifygnome:
	n = pynotify.Notification(title, msg)
	n.show()
    elif desktopnotifykde:
	knotify.event('info', 'kde', [], title, msg, [], [], 0, dbus_interface="org.kde.KNotify")
    else:
	print title + ': ' + msg


class AutosyncJabberBot(jabberbot.JabberBot):
    def _process_thread(self):
	while self.__running:
	    self.conn.Process(1)
	    self.idle_proc()

    def start_serving(self):
	self.connect()
        if self.conn:
            self.log('bot connected. serving forever.')
        else:
            self.log('could not connect to server - aborting.')
            return

	self.__running = True
	self.__thread = threading.Thread(target = self._process_thread)
	self.__thread.start()

    def stop_serving(self):
	self.__running = False
	self.__thread.join()
  
    @botcmd
    def whoami( self, mess, args):
        """Tells you your username"""
        return mess.getFrom()

    @botcmd
    def ping( self, mess, args):
	print 'Received ping command over Jabber channel'
        return 'pong'


class FileChangeHandler(pyinotify.ProcessEvent):
    def my_init(self, cwd, ignored):
        self.cwd = cwd
        self.ignored = ignored
        
    def exec_cmd(self, command):
	subprocess.call(command.split(' '), cwd=self.cwd)

    def _run_cmd(self, event, action):
	curpath = event.pathname
	if event.dir:
	    print 'Ignoring change to directory ' + curpath
	    return
        if any(fnmatch.fnmatch(curpath, pattern) for pattern in self.ignored):
	    print 'Ignoring change to file %s because it matches the ignored patterns from .gitignore' % curpath
            return

	printmsg('Local change', 'Committing changes in ' + curpath + " : " + action)

    def process_IN_DELETE(self, event):
	self._run_cmd(event, 'rm')

    def process_IN_CREATE(self, event):
        self._run_cmd(event, 'add')

    def process_IN_MODIFY(self, event):
        self._run_cmd(event, 'add')
        
    # TODO: implement moved
    # TODO: react to attribute changes as well

def signal_handler(signal, frame):
        print 'You pressed Ctrl+C, exiting gracefully!'
        if notifier:
	    notifier.stop()
	if bot:
	    bot.stop_serving()
        sys.exit(0)

if __name__ == '__main__':
    config = ConfigParser.RawConfigParser()
    defaultcfgpath = os.path.expanduser('~/.autosync')
    if len(sys.argv) >= 2:
	config.read([sys.argv[1], defaultcfgpath])
    else:
	config.read(defaultcfgpath)

    pathstr = config.get('autosync', 'path')
    path = os.path.normpath(os.path.expanduser(pathstr))
    if os.path.isdir(path):
	print 'Watching path ' + path
    else:
	print 'Error: path ' + path + ' (expanded from ' + pathstr + ') does not exist'
	os.exit(1)
    
    pidfile = config.get('autosync', 'pidfile')
    ignorepaths = config.get('autosync', 'ignorepath')
    readfrequency = config.get('autosync', 'readfrequency')
    
    # Read required DCVS commands
    cmd_startup = config.get('dcvs', 'startupcmd')
    cmd_commit = config.get('dcvs', 'commitcmd')
    cmd_push = config.get('dcvs', 'pushcmd')
    cmd_pull = config.get('dcvs', 'pullcmd')
    cmd_add = config.get('dcvs', 'addcmd')
    cmd_rm = config.get('dcvs', 'rmcmd')
    cmd_modify = config.get('dcvs', 'modifycmd')
    cmd_move = config.get('dcvs', 'movecmd')
    
    # TODO: this is currently git-specific, should be configurable
    ignorefile = os.path.join(path, '.gitignore')
    # load the patterns and match them internally with fnmatch
    if os.path.exists(ignorefile):
	f = open(ignorefile, 'r')
	ignorefilepatterns = [pat.strip() for pat in f.readlines()]
	f.close()
    else:
	ignoefilepatterns = []
    # (unfortunately, can't use pyinotify.ExcludeFilter, because this expects regexes (which .gitignore doesn't support))
    print 'Ignoring files matching any of the patterns ' + ' '.join(ignorefilepatterns)

    # but we can use the ignore filter with our own pathname excludes
    # However, need to prepend the watch path name, as the excludes need to be 
    # absolute path names.
    ignoreabsolutepaths = [os.path.normpath(path + os.sep + ignorepath) for ignorepath in ignorepaths.split()]
    print 'Adding list to inotify exclude filter: '
    print ignoreabsolutepaths
    excl = pyinotify.ExcludeFilter(ignoreabsolutepaths)

    signal.signal(signal.SIGINT, signal_handler)

    # try to set up desktop notification, first for KDE4, then for Gnome
    # the signature is not correct, so rely on pynotify only at the moment
    #try:
	#import dbus
	#knotify = dbus.SessionBus().get_object("org.kde.knotify", "/Notify")
	#knotify.event("warning", "autosync application", [],
	    #'KDE4 notification initialized', 'Initialized KDE4 desktop notification via DBUS', 
	    #[], [], 0, dbus_interface='org.kde.KNotify')
	#desktopnotifykde = True
    #except:
	#print 'KDE4 KNotify does not seem to run or dbus is not installed'
    
    try:
	import pynotify
	if pynotify.init('autosync application'):
	    print 'pynotify initialized successfully, will use desktop notifications'
	    desktopnotifygnome = True
	else:
	    print 'there was a problem initializing the pynotify module'
    except:
	print 'pynotify does not seem to be installed'
	
    username = config.get('jabber', 'username')
    password = config.get('jabber', 'password')
    try:
	bot = AutosyncJabberBot(username,password)
	bot.start_serving()
	bot.send(username, 'Logged into jabber account')
	printmsg('Autosync Jabber login successful', 'Successfully logged into Jabber account ' + username)
    except Exception as inst:
	print type(inst)
	print inst
	printmsg('Autosync Jabber login failed', 'Could not login to Jabber account ' + username + '. Will not announce pushes to other running autosync instances.')	

    wm = pyinotify.WatchManager()
    handler = FileChangeHandler(cwd=path, ignored=ignorefilepatterns)
    notifier = pyinotify.ThreadedNotifier(wm, handler, read_freq=readfrequency)
    # coalescing events needs pyinotify >= 0.9, so make this optional
    try:
	notifier.coalesce_events()
    except AttributeError as inst:
	print 'Can not coalesce events, pyinotify does not seem to support it (maybe to old): %s' % inst
    mask = pyinotify.IN_DELETE | pyinotify.IN_CREATE | pyinotify.IN_MODIFY | pyinotify.IN_ATTRIB | pyinotify.IN_MOVED_FROM | pyinotify.IN_MOVED_TO | pyinotify.IN_DONT_FOLLOW | pyinotify.IN_ONLYDIR
    try:
	print 'Adding recursive, auto-adding watch for path %s with event mask %d' % (path, mask)
	wd = wm.add_watch(path, mask, rec=True, auto_add=True, quiet=False, exclude_filter=excl)
	if wd <= 0:
	    print 'Unable to add watch for path %s - this will not work' % path
    except pyinotify.WatchManagerError, err:
	print err, err.wmd

    printmsg('autosync starting', 'Initialization of local file notifications and Jabber login done, starting main loop')

    print '==> Start monitoring %s (type c^c to exit)' % path
    # TODO: daemonize
    # notifier.loop(daemonize=True, pid_file=pidfile, force_kill=True)
    notifier.start()

    print 'Fetching updates from remote now: ' + cmd_pull
    handler.exec_cmd(cmd_pull)
    print 'Running startup command to check for local changes now: ' + cmd_startup
    handler.exec_cmd(cmd_startup)
    print 'Committing and pushing local changes now: ' + cmd_commit + ' and ' + cmd_push
    handler.exec_cmd(cmd_commit)
    handler.exec_cmd(cmd_push)

    while True:
	time.sleep(10)
