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
import sys, signal, os, time, subprocess, threading, fnmatch, pyinotify, ConfigParser, jabberbot, xmpp
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


# this helper class has been shamelessly copied from http://socialwire.ca/2010/01/python-resettable-timer-example/
class ResettableTimer(threading.Thread):
  """
  The ResettableTimer class is a timer whose counting loop can be reset
  arbitrarily. Its duration is configurable. Commands can be specified
  for both expiration and update. Its update resolution can also be
  specified. Resettable timer keeps counting until the "run" method
  is explicitly killed with the "kill" method.
  """
  def __init__(self, maxtime, expire, inc=None, update=None):
    """
    @param maxtime: time in seconds before expiration after resetting
                    in seconds
    @param expire: function called when timer expires
    @param inc: amount by which timer increments before
                updating in seconds, default is maxtime/2
    @param update: function called when timer updates
    """
    self.maxtime = maxtime
    self.expire = expire
    if inc:
      self.inc = inc
    else:
      self.inc = maxtime/2
    if update:
      self.update = update
    else:
      self.update = lambda c : None
    self.counter = 0
    self.active = True
    self.stop = False
    threading.Thread.__init__(self)
    self.setDaemon(True)
  def set_counter(self, t):
    """
    Set self.counter to t.

    @param t: new counter value
    """
    self.counter = t
  def deactivate(self):
    """
    Set self.active to False.
    """
    self.active = False
  def kill(self):
    """
    Will stop the counting loop before next update.
    """
    self.stop = True
  def reset(self):
    """
    Fully rewinds the timer and makes the timer active, such that
    the expire and update commands will be called when appropriate.
    """
    self.counter = 0
    self.active = True

  def run(self):
    """
    Run the timer loop.
    """
    while True:
      self.counter = 0
      while self.counter < self.maxtime:
        self.counter += self.inc
        time.sleep(self.inc)
        if self.stop:
          return
        if self.active:
          self.update(self.counter)
      if self.active:
        self.active = False
        self.expire()


class AutosyncJabberBot(jabberbot.JabberBot):
    def _process_thread(self):
	print 'Background Jabber bot thread starting'
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

	# this is a hack to get other bots to add this one to their "seen" lists
	# TODO: still doesn't work, figure out how to use JabberBot to get rid of
	# 'AutosyncJabberBot : Ignoring message from unseen guest: rene-sync@doc.to/AutosyncJabberBot on iss'
	self.conn.send(xmpp.Presence(to=username))

    def stop_serving(self):
	self.__running = False
	self.__thread.join()
  
    @botcmd
    def whoami(self, mess, args):
        """Tells you your username"""
        return 'You are %s, I am %s/%s' % (mess.getFrom(), self.jid, self.res)

    @botcmd
    def ping(self, mess, args):
	print 'Received ping command over Jabber channel'
        return 'pong'
        
    @botcmd
    def pushed(self, mess, args):
	print 'Received pushed command over Jabber channel with args %s from %s' % (args, mess.getFrom())
	if mess.getFrom() == str(self.jid) + '/' + self.res:
	    print 'Ignoring own pushed message looped back by server'
	else:
	    print 'TRYING TO PULL FROM %s' % args


class FileChangeHandler(pyinotify.ProcessEvent):
    def my_init(self, cwd, ignored):
        self.cwd = cwd
        self.ignored = ignored
        self.timer = None
        
    def exec_cmd(self, commands):
	for command in commands.split('\n'):
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
	print 'Committing changes in ' + curpath + " : " + action
	self.exec_cmd(action)
	self.exec_cmd(cmd_commit)
	# reset the timer and start in case it is not yet running (start should be idempotent if it already is)
	# this has the effect that, when another change is committed within the timer period (readfrequency seconds),
	# then these changes will be pushed in one go
	if self.timer and self.timer.is_alive():
	    print 'Resetting already active timer to new timeout of %s seconds until push would occur' % readfrequency
	    self.timer.reset()
	else:
	    print 'Starting push timer with %s seconds until push would occur (if no other changes happen in between)' % readfrequency
	    self.timer = ResettableTimer(maxtime=readfrequency, expire=self.real_push, inc=1, update=self.timer_tick)
	    self.timer.start()

    def process_IN_DELETE(self, event):
	self._run_cmd(event, cmd_rm % event.pathname)

    def process_IN_CREATE(self, event):
        self._run_cmd(event, cmd_add % event.pathname)

    def process_IN_MODIFY(self, event):
        self._run_cmd(event, cmd_modify % event.pathname)

    def process_IN_ATTRIB(self, event):
        self._run_cmd(event, cmd_modify % event.pathname)

    def process_IN_MOVED_TO(self, event):
	if event.src_pathname:
	    print 'Detected moved file from %s to %s' % (event.src_pathname, event.pathname)
	    self._run_cmd(event, cmd_move % (event.src_pathname, event.pathname))
	else:
	    print 'Moved file to %s, but unknown source, will simply add new file' % event.pathname
	    self._run_cmd(event, cmd_add % event.pathname)
	    
    def timer_tick(self, counter):
	print 'Tick %d / %d' % (counter, self.timer.maxtime)
	    
    def real_push(self):
	printmsg('Pushing changes', 'Pushing last local changes to remote repository')
	print 'Pushing last local changes to remote repository'
	self.exec_cmd(cmd_push)
	
	# and try to notify other instances
	if bot:
	    proc = subprocess.Popen(cmd_remoteurl.split(' '), stdout=subprocess.PIPE)
	    (remoteurl, errors) = proc.communicate()
	    for sendto in [username, alsonotify]:
		bot.send(sendto, 'pushed %s' % remoteurl)


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
    readfrequency = int(config.get('autosync', 'readfrequency'))
    
    # Read required DCVS commands
    cmd_startup = config.get('dcvs', 'startupcmd')
    cmd_commit = config.get('dcvs', 'commitcmd')
    cmd_push = config.get('dcvs', 'pushcmd')
    cmd_pull = config.get('dcvs', 'pullcmd')
    cmd_add = config.get('dcvs', 'addcmd')
    cmd_rm = config.get('dcvs', 'rmcmd')
    cmd_modify = config.get('dcvs', 'modifycmd')
    cmd_move = config.get('dcvs', 'movecmd')
    cmd_remoteurl = config.get('dcvs', 'remoteurlcmd')
    
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
	
    username = config.get('xmpp', 'username')
    password = config.get('xmpp', 'password')
    alsonotify = config.get('xmpp', 'alsonotify')
    res = 'AutosyncJabberBot on %s' % os.uname()[1]
    try:
	bot = AutosyncJabberBot(username, password, res=res, debug=False, ignoreownmsg=False)
	bot.start_serving()
	bot.send(username, 'login %s' % res)
	bot.send(alsonotify, 'Autosync logged in with XMPP id %s' % username)
	printmsg('Autosync Jabber login successful', 'Successfully logged into Jabber account ' + username)
    except Exception as inst:
	print type(inst)
	print inst
	printmsg('Autosync Jabber login failed', 'Could not login to Jabber account ' + username + '. Will not announce pushes to other running autosync instances.')	

    wm = pyinotify.WatchManager()
    handler = FileChangeHandler(cwd=path, ignored=ignorefilepatterns)
    # TODO: frequency doesn't work....
    #notifier = pyinotify.ThreadedNotifier(wm, handler, read_freq=readfrequency)
    notifier = pyinotify.ThreadedNotifier(wm, handler)
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
    
    print '----------------------------------------------------------------'

    while True:
	time.sleep(10)
