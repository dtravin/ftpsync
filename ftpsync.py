import Queue
import logging
import re
from time import sleep

import requests
from requests.auth import HTTPBasicAuth
from ftplib import FTP
import dateutil.parser


def extract_tstamp(fname):
    m = re.search('OPTIBET(.+?)\.XML', fname)
    if m:
        try:
            return dateutil.parser.parse(m.group(1)).replace(tzinfo=dateutil.tz.gettz('CET'))
        except:
            return None
    else:
        return None


def sort_by_tstamp(to_post):
    to_post_with_tstamp = [(x, extract_tstamp(x)) for x in to_post]
    filtered = [e for e in to_post_with_tstamp if e[1]]
    return [e[0] for e in sorted(filtered, key=lambda x: x[1])]


class FTPSync:
    ftp = FTP()
    content_queue = Queue.Queue()
    stopped = False
    con = None
    cur = None

    def __init__(self, post_url, post_user, post_password, storage, scan_interval_seconds = 1, requests_session = requests):
        self.post_url = post_url
        self.post_user = post_user
        self.post_password = post_password
        self.storage = storage
        self.scan_interval_seconds = scan_interval_seconds
        self.requests_session = requests_session

    def connect(self, host, port=21):
        logging.debug('Connecting to port %s' % port)
        resp = self.ftp.connect(host, port)

        return resp

    def login(self, user='anonymous', password='', directory='/'):
        resp = self.ftp.login(user, password)
        self.ftp.cwd(directory)
        return resp

    def enqueue_to_post(self, remote_fname, content):
        logging.info('Queueing remote file %s to post' % remote_fname)
        self.content_queue.put((remote_fname, content))

    def monitor_loop(self):
        logging.info('Monitoring started')

        while not self.stopped:
            try:
                all_files = self.ftp.nlst()
                logging.debug('Directory list %s' % all_files)

                to_post = self.storage.find_not_posted(all_files)

                to_post_sorted = sort_by_tstamp(to_post)
                for remote_fname in to_post_sorted:
                    self.ftp.retrbinary('RETR ' + remote_fname, (lambda content: self.enqueue_to_post(remote_fname, content)))

                sleep(self.scan_interval_seconds)
                while not self.content_queue.empty():
                    sleep(self.scan_interval_seconds)
            except Exception, e:
                logging.error('Error while monitoring FTP %s' % e)
                self.stop()

        try:
            self.ftp.close()
        except Exception, e:
            logging.error('Error closing ftp client %s' % e)

    def posting_loop(self):
        while not self.stopped:
            try:
                fname, content = self.content_queue.get(True, 5)
            except:
                continue

            try:
                resp = self.requests_session.post(self.post_url, data=content, auth=HTTPBasicAuth(self.post_user, self.post_password))
                if resp.status_code == 200:
                    self.storage.mark_as_posted(fname)
                    logging.info('POST succeeded for %s' % fname)
                else:
                    logging.error('POST failed with %s' % resp)
                    self.stop()
            except Exception as e:
                logging.error('Upload failed for %s with %s' % (fname, e))
                self.stop()

    def stop(self):
        self.stopped = True
