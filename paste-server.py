#!/usr/bin/python

import cherrypy
import os
import pwd
import grp
import sqlite
import md5

from pygments import highlight
import pygments.lexers
from pygments.formatters import HtmlFormatter

OK_LANGS=[x[2][0] for x in pygments.lexers.LEXERS.values()]
OK_LANGS.sort()

DEFAULT_LANG="text"

escape = lambda a: a.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
USER = "www-data"
GROUP = "www-data"
BASEDIR="/paste/"

class PasteServer:

    def index(self):
        key = cherrypy.request.headers['Host'].split(".")[0]
        if key in ('new', 'paste'):
            lang_opts = "\n".join([('<option value="%s"%s>%s</option>' % (l,l==DEFAULT_LANG and " selected" or "",l)) for l in OK_LANGS])
            data = file(BASEDIR+"static/main.html").read()
            uname = ""
            if cherrypy.request.simple_cookie.has_key('username'):
                uname = cherrypy.request.simple_cookie['username'].value
            data = data.replace("%%LANGOPTS%%", lang_opts)
            data = data.replace("%%USERNAME%%", uname)
            return data
        else:
            db=sqlite.connect(BASEDIR+"database/paste.db")
            c=db.cursor()
            c.execute("SELECT user, description, lang, paste FROM paste WHERE hash=%s", (str(key),))
            if not c.rowcount:
                return "Unknown Paste %s" % (key)
            user, desc, lang, paste = c.fetchone()
            db.close()
            lexer = pygments.lexers.get_lexer_by_name(lang)
            formatter = HtmlFormatter(linenos=True, cssclass="source")
            paste = highlight(paste, lexer, formatter)
            user = escape(user)
            desc = escape(desc)
            css = formatter.get_style_defs(arg='') 
            data = file(BASEDIR+"static/paste.html").read()
            data = data.replace("%%PASTE%%", paste)
            data = data.replace("%%USER%%", user)
            data = data.replace("%%DESC%%", desc)
            data = data.replace("%%CSS%%", css)
            return data
    index.exposed = True

    def add(self, user, desc, lang, paste):
        if not lang in OK_LANGS:
            return "Bad lang!"
        paste = paste.replace("\r","")
        key=md5.md5(user+desc+paste).hexdigest()[:16]
        db=sqlite.connect(BASEDIR+"database/paste.db")
        c=db.cursor()
        c.execute("REPLACE into paste (hash, user, description, lang, paste) VALUES (%s, %s, %s, %s, %s)", (key, user, desc, lang, paste))
        db.commit()
        db.close()
        cherrypy.response.simple_cookie['username'] = user
        cherrypy.response.simple_cookie['username']['path'] = '/'
        cherrypy.response.simple_cookie['username']['max-age'] = 3600 * 24 * 30 
        raise cherrypy.HTTPRedirect("http://%s.%s/" % (key, cherrypy.config.get("paste.basehost")))
        
    add.exposed = True

cherrypy.root = PasteServer()

if __name__ == '__main__':
    if os.getuid() == 0:
        os.setgid(grp.getgrnam(GROUP)[2])
        os.setegid(grp.getgrnam(GROUP)[2])
        os.setuid(pwd.getpwnam(USER)[2])
        os.seteuid(pwd.getpwnam(USER)[2])
    cherrypy.config.update(file=BASEDIR+"paste.conf")
    cherrypy.server.start()

