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

USER = "www-data"
GROUP = "www-data"
BASEDIR="/paste/"

class PasteServer:

    def index(self):
        key = cherrypy.request.headers['Host'].split(".")[0]
        if key in ('new', 'paste'):
            uname = ""
            if cherrypy.request.simple_cookie.has_key('username'):
                uname = cherrypy.request.simple_cookie['username'].value
            tmpl = kid.Template(BASEDIR+"templates/main.html", username=uname, default_lang=DEFAULT_LANG, langs=OK_LANGS)
            return tmpl.serialize(output='xhtml')
        else:
            db=sqlite3.connect(cherrypy.config.get("paste.database"))
            c=db.cursor()
            c.execute("SELECT user, description, lang, paste FROM paste WHERE hash=?", (str(key),))
            if not c.rowcount:
                return "Unknown Paste %s" % (key)
            user, desc, lang, paste = c.fetchone()
            db.close()
            lexer = pygments.lexers.get_lexer_by_name(lang)
            formatter = HtmlFormatter(linenos=True, cssclass="source")
            paste = highlight(paste, lexer, formatter)
            css = formatter.get_style_defs(arg='') 
            tmpl = kid.Template(BASEDIR+"templates/paste.html", paste=paste,user=user, desc=desc, css=css)
            return tmpl.serialize(output='xhtml')
    index.exposed = True

    def add(self, user, desc, lang, paste):
        if not lang in OK_LANGS:
            return "Bad lang!"
        paste = paste.replace("\r","")
        key=md5.md5(user+desc+paste).hexdigest()[:16]
        db=sqlite3.connect(cherrypy.config.get("paste.database"))
        c=db.cursor()
        c.execute("REPLACE into paste (hash, user, description, lang, paste) VALUES (?, ?, ?, ?, ?)", (key, user, desc, lang, paste))
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

