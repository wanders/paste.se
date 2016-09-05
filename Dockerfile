FROM ubuntu:16.04

RUN apt-get update -y && apt-get install python python-pip sqlite3 -y

RUN pip install tornado pygments

ADD server.py pasteconfig.py schema.sql favicon.ico /paste/
ADD templates/*.html /paste/templates/

WORKDIR /paste
RUN sqlite3 paste.db <schema.sql

EXPOSE 8800

CMD python /paste/server.py