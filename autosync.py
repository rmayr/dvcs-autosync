#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Usage:
#   ./autosync.py path pidfile ignores
#
# Background monitoring |path| and its subdirectories for modifications on
# files and automatically commits the changes to git. This script assumes
# that the passed directory is (a subdirectory) of a checkout out git tree.
# A PID file is written to [pidfile] for killing the daemon later on.
# Optionally, an [ignores] file is read with one exclusion pattern per line
# and files matching any of the patterns are ignored. This will typically be
# the .gitignore file already existing the git tree.
#
# It is an adapted and slightly extended version of the autocompile.py script
# distributed as a pyinotify example with the daemon.py script mixed in.
#
# Example:
#   ./autosync.py /my-git-work-tree
#
# Dependancies:
#   Linux, Python 2.6, Pyinotify, JabberBot
# Recommended packages:
#   Pynotify for desktop notifications
#
import sys, os, functools, threading
#import subprocess
import pyinotify
import jabberbot
#botcmd = jabberbot.botcmd

# some global variables, will be initialized in main
desktopnotifykde = False
desktopnotifygnome = False
knotify = None

def printmsg(title, msg):
    if desktopnotifygnome:
	n = pynotify.Notification(title, msg)
	n.show()
    elif desktopnotifykde:
	knotify.event('info', 'kde', [], title, msg, [], [], 0, dbus_interface="org.kde.KNotify")
    else:
	print title + ': ' + msg
      

#class AutosyncJabberBot(jabberbot.JabberBot):
    #@botcmd
    #def whoami( self, mess, args):
        #"""Tells you your username"""
        #return mess.getFrom()

class OnWriteHandler(pyinotify.ProcessEvent):
    def my_init(self, cwd, cmd, ignored):
        self.cwd = cwd
        self.ignored = ignored
        self.cmd = cmd

    def _run_cmd(self, event, action):
	path = event.pathname
	if event.dir:
	    print 'Ignoring change to directory ' + path
	    return
#        if all(not path.endswith(ext) for ext in self.extensions):
#            return

	printmsg('Local change', 'Committing changes in ' + path + " : " + action)
	
#        subprocess.call(self.cmd.split(' '), cwd=self.cwd)

    def process_IN_DELETE(self, event):
	self._run_cmd(event, 'rm')

    def process_IN_CREATE(self, event):
        self._run_cmd(event, 'add')

    def process_IN_MODIFY(self, event):
        self._run_cmd(event, 'add')

def auto_compile(path, pidfile, cmd, ignored):
    wm = pyinotify.WatchManager()
    handler = OnWriteHandler(cwd=path, cmd=cmd, ignored=ignored)
    notifier = pyinotify.Notifier(wm, default_proc_fun=handler)
    wm.add_watch(path, pyinotify.ALL_EVENTS, rec=True, auto_add=True)
    print '==> Start monitoring %s (type c^c to exit)' % path
    # notifier.loop(daemonize=True, pid_file=pidfile, force_kill=True)
    notifier.loop()

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print >> sys.stderr, 'Command line error: missing argument(s).'
        sys.exit(1)

    # Required arguments
    path = sys.argv[1]
    pidfile = sys.argv[2]

    # Optional argument
    ignorefile = os.path.join(path, '.gitignore')
    if len(sys.argv) == 4:
        ignorefile = sys.argv[3]
    if os.path.exists(ignorefile):
	excl = pyinotify.ExcludeFilter(ignorefile)
    else:
	excl = None

    cmd = 'git add -A; git commit -m "Autocommit"'

    # try to set up desktop notification, first for KDE4, then for Gnome
    try:
	import dbus
	knotify = dbus.SessionBus().get_object("org.kde.knotify", "/Notify")
	knotify.event("warning", "kde", [], 
	    'KDE4 notification initialized', 'Initialized KDE4 desktop notification via DBUS', 
	    [], [], 0, dbus_interface="org.kde.KNotify")
	desktopnotifykde = True
    except:
	print 'KDE4 KNotify does not seem to run or dbus is not installed'
    
    try:
	import pynotify
	if pynotify.init('autosync application'):
	    print 'pynotify initializd successfully, will use desktop notifications'
	    desktopnotifygnome = True
	else:
	    print 'there was a problem initializing the pynotify module'
    except:
	print 'pynotify does not seem to be installed'
	
    #username = 'myjabber@account.org'
    #password = 'mypassword'
    #bot = SystemInfoJabberBot(username,password)
    #bot.send(username, 'Logged into jabber account')
    #th = threading.Thread( target = bc.thread_proc)
    #bot.serve_forever(connect_callback = lambda: th.start())
    #bc.thread_killed = True

    printmsg('autosync starting', 'Initialization of local file notifications and Jabber login done, starting main loop')

    # Blocks monitoring
    auto_compile(path, pidfile, cmd, excl)
