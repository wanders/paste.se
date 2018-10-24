#!/usr/bin/env python
#
# Author:: Anders Waldenborg <anders@0x63.nu>
# Copyright:: Copyright (c) 2005-2016, Anders Waldenborg
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#
# Except as contained in this notice, the name(s) of the above copyright
# holders shall not be used in advertising or otherwise to promote the
# sale, use or other dealings in this Software without prior written
# authorization.

import tornado.web
import sqlite3
import md5

from pygments import highlight
import pygments.lexers
from pygments.formatters import HtmlFormatter, ImageFormatter, TerminalFormatter

import pasteconfig


OK_LANGS = [x[2][0] for x in pygments.lexers.LEXERS.values()]
OK_LANGS.sort(key=lambda x: x.lower())

CHARS = {0x00: u"&lt;NUL&gt;",
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
         0x1F: u"&lt;US&gt;"
}


def stripctlchars(s):
    return s.translate(CHARS)


class PasteBaseHandler(tornado.web.RequestHandler):

    def _get_paste(self, fields, key=None):
        if key is None:
            key = self.request.host.split(".")[0]
        db = sqlite3.connect(pasteconfig.DB_FILE)
        c = db.cursor()
        try:
            c.execute("SELECT "+(",".join(fields))+" FROM paste WHERE hash=?", (str(key),))
            r = c.fetchone()
            if r is None:
                raise KeyError(key)
        finally:
            db.close()
        return r


class RobotsTxtHandler(PasteBaseHandler):
    def get(self):
        try:
            may_index, = self._get_paste(["may_index"])
        except KeyError:
            self.clear()
            self.set_status(404)
            self.finish("<html><body>Not found</body></html>")
            return

        self.set_header("Content-Type", 'text/plain; charset="utf-8"')
        res = "User-agent: *\n"
        if may_index:
            res += "Disallow: /googleupload"
        else:
            res += "Disallow: /"
        self.finish(res)


class MainHandler(PasteBaseHandler):
    def get(self):
        if (self.request.host.split(":")[0] == pasteconfig.BASE_DOMAIN or
            self.request.host.split(".")[0] == "new"):
            uname = self.get_cookie("username", "")
            self.render("templates/main.html",
                        username=uname,
                        default_lang=pasteconfig.DEFAULT_LANG,
                        configurable_index=pasteconfig.CONFIGURABLE_INDEX,
                        langs=OK_LANGS)
            return

        try:
            user, desc, lang, paste = self._get_paste(["user",
                                                       "description",
                                                       "lang",
                                                       "paste"])
        except KeyError:
            self.clear()
            self.set_status(404)
            self.render("templates/404.html",
                        key=self.request.host.split(".")[0],
                        host=self.request.host,
                        base=pasteconfig.BASE_DOMAIN)
            return

        lexer = pygments.lexers.get_lexer_by_name(lang)
        formatter = HtmlFormatter(linenos=True, cssclass="source")
        paste = stripctlchars(highlight(paste, lexer, formatter))
        css = formatter.get_style_defs(arg='')

        self.render("templates/paste.html", css=css, user=user, desc=desc, paste=paste)


class TermHandler(PasteBaseHandler):
    def get(self):
        try:
            paste, lang = self._get_paste(["paste", "lang"])
        except KeyError:
            self.clear()
            self.set_status(404)
            self.finish("<html><body>Not found</body></html>")
            return

        lexer = pygments.lexers.get_lexer_by_name(lang)
        formatter = TerminalFormatter()
        paste = highlight(paste, lexer, formatter)

        self.set_header("Content-Type", 'text/plain; charset="utf-8"')
        self.finish(paste)


class PNGHandler(PasteBaseHandler):
    def get(self):
        try:
            paste, lang = self._get_paste(["paste", "lang"])
        except KeyError:
            self.clear()
            self.set_status(404)
            self.finish("<html><body>Not found</body></html>")
            return

        lexer = pygments.lexers.get_lexer_by_name(lang)
        formatter = ImageFormatter(font_name="DroidSansMono", font_size=15)
        paste = highlight(paste, lexer, formatter)

        self.set_header("Content-Type", 'text/plain; charset="utf-8"')
        self.finish(paste)


class RawHandler(PasteBaseHandler):
    def get(self):
        try:
            paste, = self._get_paste(["paste"])
        except KeyError:
            self.clear()
            self.set_status(404)
            self.finish("<html><body>Not found</body></html>")
            return

        self.set_header("Content-Type", 'text/plain; charset="utf-8"')
        self.finish(paste)


class AddHandler(tornado.web.RequestHandler):
    def post(self):
        user = self.get_argument("user")
        desc = self.get_argument("desc")
        lang = self.get_argument("lang")
        paste = self.get_argument("paste", strip=False)
        index = (self.get_argument("index", default="").lower() == "yes")

        if lang not in OK_LANGS:
            return "Bad lang!"

        paste = paste.replace("\r", "")

        key = md5.md5(user.encode("utf-8") +
                      desc.encode("utf-8") +
                      paste.encode("utf-8")).hexdigest()[:16]

        db = sqlite3.connect(pasteconfig.DB_FILE)
        c = db.cursor()
        c.execute("REPLACE into paste (hash, user, description, lang, paste, may_index) VALUES (?, ?, ?, ?, ?, ?)",
                  (key, user, desc, lang, paste, int(index)))
        db.commit()
        db.close()

        self.set_cookie("username", user,
                        domain=pasteconfig.BASE_DOMAIN,
                        path='/',
                        expires_days=30)

        if self.request.host.split(".")[0] == "new":
            base_host = ".".join(self.request.host.split(".")[1:])
        else:
            base_host = self.request.host

        self.redirect("{}://{}.{}/".format(pasteconfig.REDIRECT_SCHEME, key, base_host))

routes = [
    (r"/robots.txt", RobotsTxtHandler),
    (r"/", MainHandler),
    (r"/\)", MainHandler),  # handle sloppy copy&paste
    (r"/raw", RawHandler),
    (r"/term", TermHandler),
    (r"/png", PNGHandler),
    (r"/add", AddHandler),
]


def create_db_if_not_exists():
    db = sqlite3.connect(pasteconfig.DB_FILE)
    c = db.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS paste (
    hash PRIMARY KEY,
    user,
    description,
    lang,
    paste,
    may_index);
""")
    db.commit()


application = tornado.web.Application(routes,
                                      **pasteconfig.TORNADOARGS)

if __name__ == "__main__":
    create_db_if_not_exists()
    application.listen(8800)
    tornado.ioloop.IOLoop.instance().start()
