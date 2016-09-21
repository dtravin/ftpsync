import Queue
import logging
from time import sleep

import requests
from requests.auth import HTTPBasicAuth
from ftplib import FTP


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

    def _lcoo_file_sequence_extractor(self, args):
        return 1

    def enqueue_to_post(self, remote_fname, content):
        logging.info('Queueing remote file %s to post' % remote_fname)
        self.content_queue.put((remote_fname, content))

    def monitor_loop(self):
        logging.info('Monitoring started')

        while not self.stopped:
            all_files = self.ftp.nlst()
            logging.debug('Directory list %s' % all_files)

            to_post = self.storage.find_not_posted(all_files)
            to_post_sorted = sorted(to_post, key=self._lcoo_file_sequence_extractor)
            for remote_fname in to_post_sorted:
                try:
                    self.ftp.retrbinary('RETR ' + remote_fname, (lambda content: self.enqueue_to_post(remote_fname, content)))
                except:
                    logging.error('Error retrieving %s' % remote_fname)

            sleep(self.scan_interval_seconds)
            while not self.content_queue.empty():
                sleep(self.scan_interval_seconds)

        self.ftp.quit()

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
            except Exception as e:
                logging.error('Upload failed for %s with %s' % (fname, e))

    def stop(self):
        self.stopped = True
