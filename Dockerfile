FROM ubuntu:16.04
MAINTAINER dtravin@gmail.com

RUN apt-get update && apt-get install -y python-setuptools python-pip supervisor git
RUN mkdir -p /var/log/supervisor /opt

RUN cd /opt && git clone https://github.com/dtravin/ftpsync.git && cd ftpsync && pip install -r requirements.txt

COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
CMD /usr/bin/supervisord -n #c /etc/supervisor/supervisord.conf
