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
#   Linux, Python 2.6, Pyinotify
#
import functools
import subprocess
import sys
import pyinotify

class OnWriteHandler(pyinotify.ProcessEvent):
    def my_init(self, cwd, extension, cmd):
        self.cwd = cwd
        self.ignores = 
        self.cmd = cmd

    def _run_cmd(self):
        print '==> Modification detected'
        subprocess.call(self.cmd.split(' '), cwd=self.cwd)

    def process_IN_MODIFY(self, event):
        if all(not event.pathname.endswith(ext) for ext in self.extensions):
            return
        self._run_cmd()

def auto_compile(path, pidfile, cmd):
    wm = pyinotify.WatchManager()
    handler = OnWriteHandler(cwd=path, cmd=cmd)
    notifier = pyinotify.Notifier(wm, default_proc_fun=handler)
    wm.add_watch(path, pyinotify.ALL_EVENTS, rec=True, auto_add=True)
    print '==> Start monitoring %s (type c^c to exit)' % path
    # notifier.loop(daemonize=True, pid_file=pidfile, force_kill=True)
    notifier.loop();

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print >> sys.stderr, "Command line error: missing argument(s)."
        sys.exit(1)

    # Required arguments
    path = sys.argv[1]
    pidfile = sys.argv[2]

    # Optional argument
    ignorefile = os.path.join(path, '.gitignore')
    if len(sys.argv) == 4:
        ignorefile = sys.argv[3]
    if 
    excl = pyinotify.ExcludeFilter(excl_file)

    cmd = 'git add -A; git commit -m "Autocommit"'

    # Blocks monitoring
    auto_compile(path, pidfile, cmd)
