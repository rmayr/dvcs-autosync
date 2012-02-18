#!/usr/bin/python
# Setup for dvcs-autosync by Rene Mayrhofer
# Ideas for setup script taken from jabberbot setup.py by Thomas Perl

from distutils.core import setup
import os
import re
import sys

# the package name
SCRIPT = 'dvcs-autosync'

keys = ('__version__', '__website__', '__license__', '__author__')
options = dict()
sc = open(SCRIPT)
sclines = sc.readlines()
for line in sclines:
    if not line.strip(): # skip empty or space padded lines
	continue
    if re.compile('^#').search(line) is not None: # skip commented lines
	continue
      
    kvp = line.strip().split('=')
    if kvp[0].strip() in keys:
	options[kvp[0].strip(' \'')] = kvp[1].strip(' \'')

# These metadata fields are simply taken from the script
VERSION = options['__version__']
WEBSITE = options['__website__']
LICENSE = options['__license__']

# Extract name and e-mail ("Firstname Lastname <mail@example.org>")
AUTHOR, EMAIL = re.match(r'(.*) <(.*)>', options['__author__']).groups()

setup(name=SCRIPT,
      version=VERSION,
      author=AUTHOR,
      author_email=EMAIL,
      license=LICENSE,
      url=WEBSITE,

      scripts= [SCRIPT],
      packages = ['dvcsautosync'],
      data_files = [('share/' + SCRIPT, ['autosync-xdg-launcher.sh']),
                    ('share/applications', [SCRIPT + '.desktop']),
                    ('share/icons/hicolor/8x8/apps', ['icons/8x8/dvcs-autosync.png']),
                    ('share/icons/hicolor/16x16/apps', ['icons/16x16/dvcs-autosync.png']),
                    ('share/icons/hicolor/22x22/apps', ['icons/22x22/dvcs-autosync.png']),
                    ('share/icons/hicolor/32x32/apps', ['icons/32x32/dvcs-autosync.png']),
                    ('share/icons/hicolor/48x48/apps', ['icons/48x48/dvcs-autosync.png'])],
      
      description=  'Automatic synchronization of distributed version control repositories',
      download_url= 'https://gitorious.org/dvcs-autosync',
      long_description= 'dvcs-autosync is an open source replacement for Dropbox/Wuala/Box.net/etc. based on distributed version control systems (DVCS). It offers nearly instantaneous mutual updates when a file is added or changed on one side but with the added benefit of (local, distributed) versioning and that it does not rely on a centralized service provider, but can be used with any DVCS hosting option including a completely separate server. Synchronization of directories is based on DVCS repositories. Git is used for main development and is being tested most thoroughly as the backend storage, but other DVCS such as Mercurial are also supported. A single Python script monitors the configured directory for live changes, commits these changes to the DVCS (such as git) and synchronizes with other instances using XMPP messages.',
  )
