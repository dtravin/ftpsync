import os
import socket
import unittest
import thread
from ftplib import FTP
from time import sleep
import Queue
import tempfile
import shutil

import logging
import sys
import base64

import requests
import requests_mock

from db_storage import DatabaseStorage

from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import ThreadedFTPServer
from ftpsync import FTPSync, sort_by_tstamp, adjust_commas

logging.basicConfig(level=logging.INFO,
                    stream=sys.stdout,  # filename='myserver.log', # log to this file
                    format='%(asctime)s %(message)s')  # include timestamp
USERNAME = 'test_user'
PASSWORD = 'test_password'
WELCOME_MSG = 'WELCOME'
POST_URL = 'mock://endpoint/lcoo'
POST_USER = 'lcoo_user'
POST_PASSWORD = 'lcoo_password'
EXPECTED_BASIC_AUTH_HEADER = 'Basic %s' % base64.b64encode('%s:%s' % (POST_USER, POST_PASSWORD))


def ftp_server(username, password, port, dir):
    authorizer = DummyAuthorizer()
    authorizer.add_user(username, password, dir, perm='elradfmwM')
    handler = FTPHandler
    handler.authorizer = authorizer
    handler.banner = WELCOME_MSG
    logging.info('Opening FTPD on port %s' % port)
    address = ('0.0.0.0', port)

    server = ThreadedFTPServer(address, handler)
    server.max_cons_per_ip = 100
    return server


def create_file(folder, content):
    import faker
    fake = faker.Faker()
    rand_date = fake.date_time()
    fname = 'OPTIBET%s.XML' % rand_date.isoformat()
    with open('%s/%s' % (folder, fname),'w') as f:
        f.write(content)
        f.flush()
        return f.name


session = requests.Session()


class TestFTPSync(unittest.TestCase):
    succeeded_posts_queue = Queue.Queue()

    def http_endpoint_200(self):
        def request_received_callback(request, context):
            context.status_code = 200
            logging.debug('Received post %s' % request)
            self.succeeded_posts_queue.put((request.body, request.headers['Authorization']))
            return 'response'

        adapter = requests_mock.Adapter()
        adapter.register_uri('POST', POST_URL, text=request_received_callback)
        session.mount('mock', adapter)
        return session

    def http_endpoint_401(self):
        def request_received_callback(request, context):
            context.status_code = 401
            logging.debug('Returning 401 for received post %s' % request)
            return 'Unexpected error'

        adapter = requests_mock.Adapter()
        adapter.register_uri('POST', POST_URL, text=request_received_callback)
        session.mount('mock', adapter)
        return session

    def setUp(self):
        self.portFTP = self.pickUnusedPort()

        self.work_dir = tempfile.mkdtemp()
        logging.info('Port %s. Working dir %s' % (self.portFTP, self.work_dir))

        try:
            self.ftp_server = ftp_server(USERNAME, PASSWORD, self.portFTP, self.work_dir)
        except Exception, e:
            logging.error('Cannot start FTPD %s' % e)
            raise e

        def _start_ftp():
            self.ftp_server.serve_forever()

        thread.start_new_thread(_start_ftp, ())
        self.storage = DatabaseStorage(dbname='temp.db')
        self.storage.initialize()
        ftp_online = False
        while not ftp_online:
            sleep(0.2)
            try:
                ftp_online = FTP().connect('localhost', self.portFTP)
                if ftp_online:
                    logging.info('FTPD online')
            except Exception, e:
                logging.debug('Cannot connect to %s error is %s' % (self.portFTP, e))

    def _start_ftp_sync(self, requests_session):
        self.ftpsync = FTPSync(post_url=POST_URL, post_user=POST_USER, post_password=POST_PASSWORD,
                               storage=self.storage, requests_session=requests_session)

        resp = self.ftpsync.connect('localhost', self.portFTP)
        self.assertTrue(WELCOME_MSG in resp)

        resp = self.ftpsync.login(USERNAME, PASSWORD)
        self.assertTrue('successful' in resp)

        thread.start_new_thread(self.ftpsync.monitor_loop, ())
        thread.start_new_thread(self.ftpsync.posting_loop, ())

    def pickUnusedPort(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('localhost', 0))
        addr, port = s.getsockname()
        s.close()
        return port

    def tearDown(self):
        self.storage.clean()
        shutil.rmtree(self.work_dir)
        if self.ftpsync:
            self.ftpsync.stop()
        self.ftp_server.close()
        os.remove('temp.db')

    def test_endpoint_down(self):
        requests_session = self.http_endpoint_401()
        self._start_ftp_sync(requests_session)
        sleep(1)
        c1 = "<test />"
        create_file(self.work_dir, c1)
        sleep(1)
        self.assertTrue(self.ftpsync.stopped)

    def test_no_new_files(self):
        requests_session = self.http_endpoint_200()
        self._start_ftp_sync(requests_session)
        try:
            content, auth_header = self.succeeded_posts_queue.get(True, 2)
            self.fail('Should receive nothing instead of %s' % content)
        except Queue.Empty:
            pass

    def test_one_new_file_posted(self):
        requests_session = self.http_endpoint_200()
        self._start_ftp_sync(requests_session)

        c1 = "<test />"
        create_file(self.work_dir, c1)
        try:
            content, auth_header = self.succeeded_posts_queue.get(True, 2)
            self.assertEquals(c1, content)
            self.assertEquals(EXPECTED_BASIC_AUTH_HEADER, auth_header)
        except Queue.Empty:
            self.fail('Should receive one new file')

    def test_ftpserver_down(self):
        requests_session = self.http_endpoint_200()
        self._start_ftp_sync(requests_session)
        self.ftp_server.close()
        sleep(1)
        self.assertTrue(self.ftpsync.stopped)


class TestUtil(unittest.TestCase):
    def test_tstamp_extract(self):
        f1 = "OPTIBET2016-9-25T11-59-33.XML"
        f2 = "OPTIBET2016-9-23T11-59-33.XML"
        f3 = "OPTIBET2016-9-24T11-59-33.XML"

        expected = [f2, f3, f1]
        self.assertEqual(expected, sort_by_tstamp([f1, f2, f3]))

    def test_skip_invalid(self):
        f1 = "OPTIBET.XML"
        f2 = "OPTIBET2016-9-23T11-59-33.XML"
        f3 = "OPTIBET2016-9-24T11-59-33.XML"

        expected = [f2, f3]
        self.assertEqual(expected, sort_by_tstamp([f1, f2, f3]))

    def test_comma_replace_to_dot(self):
        test='''
        123,00
        456,d
        df,dd
        '''

        expected='''
        123.00
        456,d
        df,dd
        '''

        commas = adjust_commas(test)
        self.assertEquals(expected, commas)

if __name__ == '__main__':
    unittest.main()
