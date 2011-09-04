#!/usr/bin/python

import cherrypy
import os
import pwd
import grp
import sqlite3
import md5
import kid

from pygments import highlight
import pygments.lexers
from pygments.formatters import HtmlFormatter

OK_LANGS=[x[2][0] for x in pygments.lexers.LEXERS.values()]
OK_LANGS.sort()

DEFAULT_LANG="text"

CHARS={0x00: u"&lt;NUL&gt;",
       0x01: u"&lt;SOH&gt;",
       0x02: u"&lt;STX&gt;",
       0x03: u"&lt;ETX&gt;",
       0x04: u"&lt;EOT&gt;",
       0x05: u"&lt;ENQ&gt;",
       0x06: u"&lt;ACK&gt;",
       0x07: u"&lt;BEL&gt;",
       0x08: u"&lt;BS&gt;",
       0x0B: u"&lt;VT&gt;",
       0x0C: u"&lt;FF&gt;",
       0x0E: u"&lt;SO&gt;",
       0x0F: u"&lt;SI&gt;",
       0x10: u"&lt;DLE&gt;",
       0x11: u"&lt;DC1&gt;",
       0x12: u"&lt;DC2&gt;",
       0x13: u"&lt;DC3&gt;",
       0x14: u"&lt;DC4&gt;",
       0x15: u"&lt;NAK&gt;",
       0x16: u"&lt;SYN&gt;",
       0x17: u"&lt;ETB&gt;",
       0x18: u"&lt;CAN&gt;",
       0x19: u"&lt;EM&gt;",
       0x1A: u"&lt;SUB&gt;",
       0x1B: u"&lt;ESC&gt;",
       0x1C: u"&lt;FS&gt;",
       0x1D: u"&lt;GS&gt;",
       0x1E: u"&lt;RS&gt;",
       0x1F: u"&lt;US&gt;",
}

def stripctlchars(s):
    return s.translate(CHARS)

class NoSuchPaste(cherrypy.NotFound):
    def __init__(self, key):
        cherrypy.NotFound.__init__(self, key)
        self.key = key
        self._message = "Paste %s not found" % key

class PasteServer:

    @cherrypy.expose
    def robots_txt(self):
        cherrypy.response.headers['Content-Type'] = 'text/plain; charset=UTF-8'
        return """User-agent: *
Disallow:
"""

    def _get_paste(self, fields, key=None):
        if key is None:
            key = cherrypy.request.headers['Host'].split(".")[0]
        db=sqlite3.connect(cherrypy.request.app.config['paste']['dbfile'])
        c=db.cursor()
        try:
            c.execute("SELECT "+(",".join(fields))+" FROM paste WHERE hash=?", (str(key),))
            r = c.fetchone()
            if r is None:
                raise NoSuchPaste(key)
        finally:
            db.close()
        return r

    @cherrypy.expose
    def index(self):
        try:
            user, desc, lang, paste = self._get_paste(["user","description","lang","paste"])
        except NoSuchPaste as e:
            if e.key in ('new', 'paste'):
                uname = ""
                if cherrypy.request.cookie.has_key('username'):
                    uname = cherrypy.request.cookie['username'].value
                tmpl = kid.Template("templates/main.html", username=uname, default_lang=DEFAULT_LANG, langs=OK_LANGS)
                return tmpl.serialize(output='xhtml')
            raise

        lexer = pygments.lexers.get_lexer_by_name(lang)
        formatter = HtmlFormatter(linenos=True, cssclass="source")
        paste = stripctlchars(highlight(paste, lexer, formatter))
        css = formatter.get_style_defs(arg='')
        tmpl = kid.Template("templates/paste.html", paste=paste,user=user, desc=desc, css=css)
        return tmpl.serialize(output='xhtml')

    @cherrypy.expose
    def raw(self):
        paste, = self._get_paste(["paste"])
        return paste

    @cherrypy.expose
    def add(self, user, desc, lang, paste):
        if not lang in OK_LANGS:
            return "Bad lang!"
        paste = paste.replace("\r","")
        key=md5.md5(user+desc+paste).hexdigest()[:16]
        db=sqlite3.connect(cherrypy.request.app.config['paste']['dbfile'])
        c=db.cursor()
        c.execute("REPLACE into paste (hash, user, description, lang, paste) VALUES (?, ?, ?, ?, ?)", (key, user, desc, lang, paste))
        db.commit()
        db.close()
        cherrypy.response.cookie['username'] = user
        cherrypy.response.cookie['username']['path'] = '/'
        cherrypy.response.cookie['username']['max-age'] = 3600 * 24 * 30 
        raise cherrypy.HTTPRedirect("http://%s.%s/" % (key, cherrypy.request.app.config['paste']['basehost']))

cherrypy.tree.mount(PasteServer(), config="paste.conf")

if __name__ == '__main__':
    print "Use: cherryd -c development.conf -i paste"
