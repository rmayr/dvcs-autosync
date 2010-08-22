#!/usr/bin/python
# -*- coding: utf-8 -*-

# JabberBot: A simple jabber/xmpp bot framework
# Copyright (c) 2007-2009 Thomas Perl <thpinfo.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#


import sys

try:
    import xmpp
except ImportError:
    print >>sys.stderr, 'You need to install xmpppy from http://xmpppy.sf.net/.'
    sys.exit(-1)
import inspect
import traceback

"""A simple jabber/xmpp bot framework"""

__author__ = 'Thomas Perl <thp@thpinfo.com>'
__version__ = '0.9'
__website__ = 'http://thpinfo.com/2007/python-jabberbot/'
__license__ = 'GPLv3 or later'

def botcmd(*args, **kwargs):
    """Decorator for bot command functions"""

    def decorate(func, hidden=False):
        setattr(func, '_jabberbot_command', True)
        setattr(func, '_jabberbot_hidden', hidden)
        return func

    if len(args):
        return decorate(args[0], **kwargs)
    else:
        return lambda func: decorate(func, **kwargs)


class JabberBot(object):
    AVAILABLE, AWAY, CHAT, DND, XA, OFFLINE = None, 'away', 'chat', 'dnd', 'xa', 'unavailable'

    MSG_AUTHORIZE_ME = 'Hey there. You are not yet on my roster. Authorize my request and I will do the same.'
    MSG_NOT_AUTHORIZED = 'You did not authorize my subscription request. Access denied.'

    def __init__(self, username, password, res=None, debug=False, ignoreownmsg=True):
        """Initializes the jabber bot and sets up commands."""
        self.__debug = debug
        self.__username = username
        self.__password = password
        self.jid = xmpp.JID(self.__username)
        self.res = (res or self.__class__.__name__)
        self.conn = None
        self. ignoreownmsg = ignoreownmsg
        self.__finished = False
        self.__show = None
        self.__status = None
        self.__seen = {}
        self.__threads = {}

        self.commands = {}
        for name, value in inspect.getmembers(self):
            if inspect.ismethod(value) and getattr(value, '_jabberbot_command', False):
                self.debug('Registered command: %s' % name)
                self.commands[name] = value

################################

    def _send_status(self):
        self.conn.send(xmpp.dispatcher.Presence(show=self.__show, status=self.__status))

    def __set_status(self, value):
        if self.__status != value:
            self.__status = value
            self._send_status()

    def __get_status(self):
        return self.__status

    status_message = property(fget=__get_status, fset=__set_status)

    def __set_show(self, value):
        if self.__show != value:
            self.__show = value
            self._send_status()

    def __get_show(self):
        return self.__show

    status_type = property(fget=__get_show, fset=__set_show)

################################

    def debug(self, s):
        if self.__debug: self.log(s)

    def log( self, s):
        """Logging facility, can be overridden in subclasses to log to file, etc.."""
        print self.__class__.__name__, ':', s

    def connect( self):
        if not self.conn:
            if self.__debug:
                conn = xmpp.Client(self.jid.getDomain())
            else:
                conn = xmpp.Client(self.jid.getDomain(), debug = [])

            conres = conn.connect()
            if not conres:
                self.log( 'unable to connect to server %s.' % self.jid.getDomain())
                return None
            if conres<>'tls':
                self.log("Warning: unable to establish secure connection - TLS failed!")

            authres = conn.auth(self.jid.getNode(), self.__password, self.res)
            if not authres:
                self.log('unable to authorize with server.')
                return None
            if authres<>'sasl':
                self.log("Warning: unable to perform SASL auth os %s. Old authentication method used!" % self.jid.getDomain())

            conn.RegisterHandler('message', self.callback_message)
            conn.RegisterHandler('presence', self.callback_presence)
            conn.sendInitPresence()
            self.conn = conn
            self.roster = self.conn.Roster.getRoster()
            self.log('*** roster ***')
            for contact in self.roster.getItems():
                self.log('  ' + str(contact))
            self.log('*** roster ***')

        return self.conn

    def join_room(self, room):
        """Join the specified multi-user chat room"""
        my_room_JID = "%s/%s" % (room,self.__username)
        self.connect().send(xmpp.Presence(to=my_room_JID))

    def quit( self):
        """Stop serving messages and exit.

        I find it is handy for development to run the
        jabberbot in a 'while true' loop in the shell, so
        whenever I make a code change to the bot, I send
        the 'reload' command, which I have mapped to call
        self.quit(), and my shell script relaunches the
        new version.
        """
        self.__finished = True

    def send_message(self, mess):
        """Send an XMPP message"""
        self.connect().send(mess)

    def send(self, user, text, in_reply_to=None, message_type='chat'):
        """Sends a simple message to the specified user."""
        mess = xmpp.Message(user, text)

        if in_reply_to:
            mess.setThread(in_reply_to.getThread())
            mess.setType(in_reply_to.getType())
        else:
            mess.setThread(self.__threads.get(user, None))
            mess.setType(message_type)

        self.send_message(mess)

    def send_simple_reply(self, mess, text, private=False):
        """Send a simple response to a message"""
        self.send_message( self.build_reply(mess,text, private) )

    def build_reply(self, mess, text=None, private=False):
        """Build a message for responding to another message.  Message is NOT sent"""
        if private: 
            to_user  = mess.getFrom()
            type = "chat"
        else:
            to_user  = mess.getFrom().getStripped()
            type = mess.getType()
        response = xmpp.Message(to_user, text)
        response.setThread(mess.getThread())
        response.setType(type)
        return response

    def get_sender_username(self, mess):
        """Extract the sender's user name from a message""" 
        type = mess.getType()
        jid  = mess.getFrom()
        if type == "groupchat":
            username = jid.getResource()
        elif type == "chat":
            username  = jid.getNode()
        else:
            username = ""
        return username

    def status_type_changed(self, jid, new_status_type):
        """Callback for tracking status types (available, away, offline, ...)"""
        self.debug('user %s changed status to %s' % (jid, new_status_type))

    def status_message_changed(self, jid, new_status_message):
        """Callback for tracking status messages (the free-form status text)"""
        self.debug('user %s updated text to %s' % (jid, new_status_message))

    def broadcast(self, message, only_available=False):
        """Broadcast a message to all users 'seen' by this bot.

        If the parameter 'only_available' is True, the broadcast
        will not go to users whose status is not 'Available'."""
        for jid, (show, status) in self.__seen.items():
            if not only_available or show is self.AVAILABLE:
                self.send(jid, message)

    def callback_presence(self, conn, presence):
        jid, type_, show, status = presence.getFrom(), \
                presence.getType(), presence.getShow(), \
                presence.getStatus()

	print 'callback_presence called with jid=%s, status=%s' % (jid, status)

        if self.jid.bareMatch(jid) and self.ignoreownmsg:
	    print 'ignoring own presence message'
            # Ignore our own presence messages
            return

        if type_ is None:
            # Keep track of status message and type changes
            old_show, old_status = self.__seen.get(jid, (self.OFFLINE, None))
            if old_show != show:
                self.status_type_changed(jid, show)

            if old_status != status:
                self.status_message_changed(jid, status)
                
            print 'adding (%s, %s) to seen jid %s' % (show, status, jid)

            self.__seen[jid] = (show, status)
        elif type_ == self.OFFLINE and jid in self.__seen:
            # Notify of user offline status change
            print 'removing jid %s from seen ones' % jid
            del self.__seen[jid]
            self.status_type_changed(jid, self.OFFLINE)

        try:
            subscription = self.roster.getSubscription(str(jid))
        except KeyError, ke:
            # User not on our roster
            subscription = None

        if type_ == 'error':
            self.log(presence.getError())

        self.debug('Got presence: %s (type: %s, show: %s, status: %s, subscription: %s)' % (jid, type_, show, status, subscription))

        if type_ == 'subscribe':
            # Incoming presence subscription request
            if subscription in ('to', 'both', 'from'):
                self.roster.Authorize(jid)
                self._send_status()

            if subscription not in ('to', 'both'):
                self.roster.Subscribe(jid)

            if subscription in (None, 'none'):
                self.send(jid, self.MSG_AUTHORIZE_ME)
        elif type_ == 'subscribed':
            # Authorize any pending requests for that JID
            self.roster.Authorize(jid)
        elif type_ == 'unsubscribed':
            # Authorization was not granted
            self.send(jid, self.MSG_NOT_AUTHORIZED)
            self.roster.Unauthorize(jid)

    def callback_message( self, conn, mess):
        """Messages sent to the bot will arrive here. Command handling + routing is done in this function."""

        # Prepare to handle either private chats or group chats
        type     = mess.getType()
        jid      = mess.getFrom()
        props    = mess.getProperties()
        text     = mess.getBody()
        username = self.get_sender_username(mess)

        if type not in ("groupchat", "chat"):
            self.debug("unhandled message type: %s" % type)
            return

        self.debug("*** props = %s" % props)
        self.debug("*** jid = %s" % jid)
        self.debug("*** username = %s" % username)
        self.debug("*** type = %s" % type)
        self.debug("*** text = %s" % text)

        # Ignore messages from before we joined
        if xmpp.NS_DELAY in props: return

        # Ignore messages from myself
        if username == self.__username: return

        # If a message format is not supported (eg. encrypted), txt will be None
        if not text: return

        # Ignore messages from users not seen by this bot
        if jid not in self.__seen:
            self.log('Ignoring message from unseen guest: %s' % jid)
            self.debug("I've seen: %s" % ["%s" % x for x in self.__seen.keys()])
            return

        # Remember the last-talked-in thread for replies
        self.__threads[jid] = mess.getThread()

        if ' ' in text:
            command, args = text.split(' ', 1)
        else:
            command, args = text, ''
        cmd = command.lower()
        self.debug("*** cmd = %s" % cmd)

        if self.commands.has_key(cmd):
            try:
                reply = self.commands[cmd](mess, args)
            except Exception, e:
                reply = traceback.format_exc(e)
                self.log('An error happened while processing a message ("%s") from %s: %s"' % (text, jid, reply))
                print reply
        else:
            # In private chat, it's okay for the bot to always respond.
            # In group chat, the bot should silently ignore commands it
            # doesn't understand or aren't handled by unknown_command().
            default_reply = 'Unknown command: "%s". Type "help" for available commands.<b>blubb!</b>' % cmd
            if type == "groupchat": default_reply = None
            reply = self.unknown_command( mess, cmd, args) or default_reply
        if reply:
            self.send_simple_reply(mess,reply)

    def unknown_command(self, mess, cmd, args):
        """Default handler for unknown commands

        Override this method in derived class if you
        want to trap some unrecognized commands.  If
        'cmd' is handled, you must return some non-false
        value, else some helpful text will be sent back
        to the sender.
        """
        return None

    def top_of_help_message(self):
        """Returns a string that forms the top of the help message

        Override this method in derived class if you
        want to add additional help text at the
        beginning of the help message.
        """
        return ""

    def bottom_of_help_message(self):
        """Returns a string that forms the bottom of the help message

        Override this method in derived class if you
        want to add additional help text at the end
        of the help message.
        """
        return ""

    @botcmd
    def help(self, mess, args):
        """Returns a help string listing available options.

        Automatically assigned to the "help" command."""
        if not args:
            if self.__doc__:
                description = self.__doc__.strip()
            else:
                description = 'Available commands:'

            usage = '\n'.join(sorted(['%s: %s' % (name, (command.__doc__ or '(undocumented)').split('\n', 1)[0]) for (name, command) in self.commands.items() if name != 'help' and not command._jabberbot_hidden]))
            usage = usage + '\n\nType help <command name> to get more info about that specific command.'
        else:
            description = ''
            if args in self.commands:
                usage = self.commands[args].__doc__ or 'undocumented'
            else:
                usage = 'That command is not defined.'

        top    = self.top_of_help_message()
        bottom = self.bottom_of_help_message()
        if top   : top    = "%s\n\n" % top
        if bottom: bottom = "\n\n%s" % bottom

        return '%s%s\n\n%s%s' % ( top, description, usage, bottom )

    def idle_proc( self):
        """This function will be called in the main loop."""
        pass

    def shutdown(self):
        """This function will be called when we're done serving

        Override this method in derived class if you
        want to do anything special at shutdown.
        """
        pass

    def serve_forever( self, connect_callback = None, disconnect_callback = None):
        """Connects to the server and handles messages."""
        conn = self.connect()
        if conn:
            self.log('bot connected. serving forever.')
        else:
            self.log('could not connect to server - aborting.')
            return

        if connect_callback:
            connect_callback()

        while not self.__finished:
            try:
                conn.Process(1)
                self.idle_proc()
            except KeyboardInterrupt:
                self.log('bot stopped by user request. shutting down.')
                break

        self.shutdown()

        if disconnect_callback:
            disconnect_callback()


