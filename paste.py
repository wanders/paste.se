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

class PasteServer:

    def robots_txt(self):
        cherrypy.response.headers['Content-Type'] = 'text/plain; charset=UTF-8'
        return """User-agent: *
Disallow:
"""
    robots_txt.exposed = True

    def index(self):
        key = cherrypy.request.headers['Host'].split(".")[0]
        if key in ('new', 'paste'):
            uname = ""
            if cherrypy.request.cookie.has_key('username'):
                uname = cherrypy.request.cookie['username'].value
            tmpl = kid.Template("templates/main.html", username=uname, default_lang=DEFAULT_LANG, langs=OK_LANGS)
            return tmpl.serialize(output='xhtml')
        else:
            db=sqlite3.connect(cherrypy.request.app.config['paste']['dbfile'])
            c=db.cursor()
            c.execute("SELECT user, description, lang, paste FROM paste WHERE hash=?", (str(key),))
            r = c.fetchone()
            if r is None:
                return "Unknown paste"
            user, desc, lang, paste = r
            db.close()
            lexer = pygments.lexers.get_lexer_by_name(lang)
            formatter = HtmlFormatter(linenos=True, cssclass="source")
            paste = highlight(paste, lexer, formatter)
            css = formatter.get_style_defs(arg='') 
            tmpl = kid.Template("templates/paste.html", paste=paste,user=user, desc=desc, css=css)
            return tmpl.serialize(output='xhtml')
    index.exposed = True

    def raw(self):
        key = cherrypy.request.headers['Host'].split(".")[0]
        cherrypy.response.headers['Content-Type'] = 'text/plain; charset=UTF-8'
        db=sqlite3.connect(cherrypy.request.app.config['paste']['dbfile'])
        c=db.cursor()
        c.execute("SELECT user, description, lang, paste FROM paste WHERE hash=?", (str(key),))
        r = c.fetchone()
        if r is None:
            return "Unknown paste"
        user, desc, lang, paste = r
        db.close()
        return paste
    raw.exposed = True


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
        
    add.exposed = True

cherrypy.tree.mount(PasteServer(), config="paste.conf")

if __name__ == '__main__':
    print "Use: cherryd -c development.conf -i paste"
