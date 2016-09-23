FROM python:2.7-alpine

RUN pip install tornado pygments

ARG domain=dev.paste.se
ARG deflang=text

ADD server.py favicon.ico /paste/
ADD templates/*.html /paste/templates/

RUN \
  echo "DB_FILE = 'paste.db'"           >/paste/pasteconfig.py; \
  echo "BASE_DOMAIN = '${domain}'"     >>/paste/pasteconfig.py; \
  echo "DEFAULT_LANG = '${deflang}'"   >>/paste/pasteconfig.py; \
  echo "TORNADOARGS=dict(debug=True)"  >>/paste/pasteconfig.py;

WORKDIR /paste

EXPOSE 8800

CMD /paste/server.py
