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
from pygments.formatters import HtmlFormatter, ImageFormatter, TerminalFormatter

import gdata.service
import gdata.photos
import gdata.photos.service

from StringIO import StringIO

SCOPE="http://picasaweb.google.com/data/"


OK_LANGS=[x[2][0] for x in pygments.lexers.LEXERS.values()]
OK_LANGS.sort(key=lambda x: x.lower())

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
                return tmpl.serialize(output='xhtml-strict')
            raise

        canupload=self._canupload(paste)
        lexer = pygments.lexers.get_lexer_by_name(lang)
        formatter = HtmlFormatter(linenos=True, cssclass="source")
        paste = stripctlchars(highlight(paste, lexer, formatter))
        css = formatter.get_style_defs(arg='')
        tmpl = kid.Template("templates/paste.html",
                            paste=paste,
                            user=user,
                            canupload=canupload,
                            desc=desc,
                            css=css)
        return tmpl.serialize(output='xhtml-strict')

    @cherrypy.expose
    def raw(self):
        cherrypy.response.headers['Content-Type'] = 'text/plain; charset=UTF-8'
        paste, = self._get_paste(["paste"])
        return paste

    @cherrypy.expose
    def term(self):
        paste,lang = self._get_paste(["paste","lang"])
        cherrypy.response.headers['Content-Type'] = 'text/plain; charset=UTF-8'
        lexer = pygments.lexers.get_lexer_by_name(lang)
        formatter = TerminalFormatter()
        return highlight(paste, lexer, formatter)

    @cherrypy.expose
    def png(self):
        paste,lang = self._get_paste(["paste","lang"])
        if not self._canupload(paste):
            return "Paste too big for png..."
        cherrypy.response.headers['Content-Type'] = 'image/png'
        lexer = pygments.lexers.get_lexer_by_name(lang)
        formatter = ImageFormatter()
        return highlight(paste, lexer, formatter)

    @cherrypy.expose
    def add(self, user, desc, lang, paste):
        if not lang in OK_LANGS:
            return "Bad lang!"
        paste = paste.replace("\r","")
        key=md5.md5(user.encode("utf-8")+desc.encode("utf-8")+paste.encode("utf-8")).hexdigest()[:16]
        db=sqlite3.connect(cherrypy.request.app.config['paste']['dbfile'])
        c=db.cursor()
        c.execute("REPLACE into paste (hash, user, description, lang, paste) VALUES (?, ?, ?, ?, ?)", (key, user, desc, lang, paste))
        db.commit()
        db.close()
        cherrypy.response.cookie['username'] = user
        cherrypy.response.cookie['username']['path'] = '/'
        cherrypy.response.cookie['username']['max-age'] = 3600 * 24 * 30 
        raise cherrypy.HTTPRedirect("http://%s.%s/" % (key, cherrypy.request.app.config['paste']['basehost']))


    @cherrypy.expose
    def googleupload(self):
        key = cherrypy.request.headers['Host'].split(".")[0]
        next = "http://auth.%s/authsub/%s" % (cherrypy.request.app.config['paste']['basehost'], key)
        aurl = gdata.service.GenerateAuthSubRequestUrl(next, SCOPE, secure=False, session=True)
        raise cherrypy.HTTPRedirect(aurl)

    def _canupload(self, paste):
        splitted = paste.split("\n")
        if len(splitted) > 24 or any(len(x) > 80 for x in splitted):
            return False
        return True


    @cherrypy.expose
    def authsub(self, *args, **kwargs):
        key = args[0]
        user, desc, lang, paste = self._get_paste(["user","description","lang","paste"], key=key)

        if not self._canupload(paste):
            return "Paste too big for upload..."

        pasteurl="http://%s.%s/" % (key, cherrypy.request.app.config['paste']['basehost'])

        lexer = pygments.lexers.get_lexer_by_name(lang)
        formatter = ImageFormatter(linenos=True, cssclass="source")
        img = highlight(paste, lexer, formatter)

        sutoken = kwargs['token']

        srv = gdata.photos.service.PhotosService()
        srv.SetAuthSubToken(sutoken)
        srv.UpgradeToSessionToken()

        albums = srv.GetUserFeed().entry
        for a in albums:
            extelements = dict([(e.tag, e.text) for e in a.extension_elements])
            if extelements.get('albumType') == 'CameraSync':
                failed=False
                try:
                    srv.InsertPhotoSimple(a, "pasteseupload", "%s\n(pasted by %s on %s)" % (desc, user, pasteurl), StringIO(img))
                except:
                    failed=True
                tmpl = kid.Template("templates/picasaupload-done.html",
                                    albumname = a.title.text,
                                    failed=failed,
                                    pasteurl=pasteurl)
                return tmpl.serialize(output='xhtml-strict')


        tmpl = kid.Template("templates/picasaupload-done.html",
                            albumname=None, failed=True,
                            pasteurl="http://%s.%s/" % (args[0], cherrypy.request.app.config['paste']['basehost']))
        return tmpl.serialize(output='xhtml-strict')




cherrypy.tree.mount(PasteServer(), config="paste.conf")

if __name__ == '__main__':
    print "Use: cherryd -c development.conf -i paste"
