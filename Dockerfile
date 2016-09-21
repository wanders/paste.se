FROM ubuntu:16.04

RUN apt-get update -y && apt-get install python python-pip sqlite3 -y

RUN pip install tornado pygments

ADD server.py favicon.ico /paste/
ADD templates/*.html /paste/templates/

RUN \
  echo "DB_FILE = 'paste.db'"           >/paste/pasteconfig.py; \
  echo "BASE_DOMAIN = 'dev.paste.se'"  >>/paste/pasteconfig.py; \
  echo "DEFAULT_LANG = 'text'"         >>/paste/pasteconfig.py; \
  echo "TORNADOARGS=dict(debug=True)"  >>/paste/pasteconfig.py;

WORKDIR /paste

EXPOSE 8800

CMD python /paste/server.py
