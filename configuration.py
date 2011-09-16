# -*- coding: utf-8 -*-

# Copyright (C) 2011 Shenja Sosna <shenja at sosna.zp.ua>

# This file is part of DVCS-autosync.

# DVCS-autosync is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# DVCS-autosync is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with Project Hamster.  If not, see <http://www.gnu.org/licenses/>.

"""
this code copied from Mehdi Abaakouk <theli48@gmail.com> via Listen, 2006 Mehdi AbaakoukGimmie (c) 
License: GPLv2
"""
#from xdg.BaseDirectory import xdg_config_home, xdg_data_home
from ConfigParser import RawConfigParser as ConfigParser
import os
import logging
logging.getLogger("DVCS-autosync")

#CONFIG_FOLDER = join(xdg_config_home, "autosync")
VERSION_CONFIG=1

class Config():
    
    def __init__(self):
        self._config = ConfigParser()
        self.getboolean = self._config.getboolean
        self.getint = self._config.getint
        self.getfloat = self._config.getfloat
        self.options = self._config.options
        self.has_option = self._config.has_option
        self.remove_option = self._config.remove_option
        self.add_section = self._config.add_section

        for section, values in self.__get_default().iteritems():
            self._config.add_section(section)
            for key, value in values.iteritems():
                self._config.set(section, key, value)
    
    def get_config_file(self, checkpathes, method = None):
        p = filter(os.path.exists, checkpathes)
        if p != ():
            return p[0]
        else:
            for path in checkpathes:
                try:
                    if not os.path.exists(os.path.dirname(path)):
                        os.makedirs(os.path.dirname(path))
                    if method is not None:
                        if method(path):
                            break
                        else:
                            continue
                    else:
                        try:
                            self.config.write(file(path, 'w'))
                            os.chmod(path, 0600)
                            break
                        except IOError:
                            continue
                except OSError:
                    # what to do if impossible?
                    logging.error("couldn't create the config directory")
            if not os.path.exists(path):
                return None
            else:
                return path
    
    def get_path_config(self):
        checkpathes = (os.path.realpath('./.autosync'),
                       os.path.join(os.path.expanduser('~'),'.autosync'))
        return self.get_config_file(checkpathes)
    
    def load(self, config_file=None):
        if config_file == None:
            config_file = self.get_path_config()
        self._config.read( config_file )
        #self.update_config()

    def get(self,section,option,default=None):
        if default is None:
            return self._config.get(section,option)
        else:
            try: 
                return self._config.get(section,option)
            except: 
                return default

    def set(self,section,option,value):
        if not self._config.has_section(section):
            logging.debug("Section \"%s\" not exist, create...", section)
            self._config.add_section(section)
        self._config.set(section,option,value)
        #Dispatcher.config_change(section,option,value)
        
    def write(self):
        pass
        #filename = CONFIG_FOLDER
        #f = file(filename, "w")
        #self._config.write(f)
        #f.close()

    def state(self, arg):
        return self._config.getboolean("setting", arg)

    def __get_default(self):
        return {
            "plugins":{
                    },
            "autosync":
            {
            "path": "~/amw",
            "syncmethod": "xmpp",
            "notifymethod":"all",
            "pulllock" : "conservative",
            "readfrequency": "5",
            "ignorepath": ".git .svn .hg src/packages src/java/openuat src/csharp/sparkleshare src/cpp/cross/keepassx src/android/ipv6config" 
            },
            "dvcs":
            {
            "statuscmd":"git status | grep -iq ""nothing to commit""",
            "addcmd":"git add %s",
            "rmcmd":"git rm -r %s",
            "modifycmd":"git add %s",
            "movecmd":"git rm %s git add %s"
            },
            "xmpp":
            {
            "username":"your XMPP id here",
            "password" :"your XMPP password here",
            "alsonotify":"if set, another XMPP id that will get notified when something happens"
            },
            "autosync-server":
            {
            "server":"http://whatever.sync.server",
            "username":"your-username",
            "password":"your-password"
            }
            

        }

config = Config()
