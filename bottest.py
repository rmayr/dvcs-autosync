#!/usr/bin/env python
# -*- coding: utf-8 -*-
from jabberbot import JabberBot, botcmd
import datetime

class SystemInfoJabberBot(JabberBot):
    @botcmd
    def serverinfo( self, mess, args):
        """Displays information about the server"""
        version = open('/proc/version').read().strip()
        loadavg = open('/proc/loadavg').read().strip()

        return '%s\n\n%s' % ( version, loadavg, )
    
    @botcmd
    def time( self, mess, args):
        """Displays current server time"""
        return str(datetime.datetime.now())

    @botcmd
    def rot13( self, mess, args):
        """Returns passed arguments rot13'ed"""
        return args.encode('rot13')

    @botcmd
    def whoami( self, mess, args):
        """Tells you your username"""
        return mess.getFrom()
 
username = 'rene@jabber.ccc.de'
password = 'origin'
bot = SystemInfoJabberBot(username,password)
bot.send('r@doc.to', 'testing')
bot.serve_forever()
