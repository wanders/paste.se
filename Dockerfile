FROM python:2.7-alpine

RUN pip install tornado pygments

ARG domain=dev.paste.se
ARG deflang=text
ARG configurable_index=True

ADD server.py favicon.ico /paste/
ADD templates/*.html /paste/templates/

RUN \
  echo "DB_FILE = '/data/paste.db'"                      >/paste/pasteconfig.py; \
  echo "BASE_DOMAIN = '${domain}'"                      >>/paste/pasteconfig.py; \
  echo "DEFAULT_LANG = '${deflang}'"                    >>/paste/pasteconfig.py; \
  echo "CONFIGURABLE_INDEX = ${configurable_index}"     >>/paste/pasteconfig.py; \
  echo "TORNADOARGS=dict(debug=True)"                   >>/paste/pasteconfig.py;

WORKDIR /paste

VOLUME /data

EXPOSE 8800

CMD /paste/server.py
