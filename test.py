import os
import unittest
import thread
from time import sleep
import Queue
import random
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
from pyftpdlib.servers import FTPServer
from ftpsync import FTPSync

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

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
    address = ('', port)

    server = FTPServer(address, handler)
    server.max_cons_per_ip = 5
    return server


def create_file(folder, content):
    with tempfile.NamedTemporaryFile(prefix='lcoo_', suffix='.xml', dir=folder, delete=False) as f:
        f.write(content)
        f.flush()
        return f.name


session = requests.Session()


class TestFTPSync(unittest.TestCase):
    def setUp(self):
        self.succeeded_posts_queue = Queue.Queue()

        def request_received_callback(request, context):
            context.status_code = 200
            logging.debug('Received post %s' % request)
            self.succeeded_posts_queue.put((request.body, request.headers['Authorization']))
            return 'response'

        adapter = requests_mock.Adapter()
        adapter.register_uri('POST', POST_URL, text=request_received_callback)
        session.mount('mock', adapter)

        self.portFTP = random.randrange(21000, 25000)

        self.work_dir = tempfile.mkdtemp()
        logging.info('Port %s. Working dir %s' % (self.portFTP, self.work_dir))

        self.ftp_server = ftp_server(USERNAME, PASSWORD, self.portFTP, self.work_dir)
        thread.start_new_thread(self.ftp_server.serve_forever, ())
        sleep(0.3)

        self.storage = DatabaseStorage(dbname='temp.db')
        self.storage.initialize()

        self.lcood = FTPSync(post_url=POST_URL, post_user=POST_USER, post_password=POST_PASSWORD,
                             storage=self.storage, requests_session=session)

        resp = self.lcood.connect('localhost', self.portFTP)
        self.assertTrue(WELCOME_MSG in resp)

        resp = self.lcood.login(USERNAME, PASSWORD)
        self.assertTrue('successful' in resp)

        thread.start_new_thread(self.lcood.monitor_loop, ())
        thread.start_new_thread(self.lcood.posting_loop, ())

        sleep(0.3)

    def tearDown(self):
        self.storage.clean()
        shutil.rmtree(self.work_dir)
        self.lcood.stop()
        self.ftp_server.close()
        os.remove('temp.db')
        sleep(2)

    def test_no_new_files(self):
        try:
            content, auth_header = self.succeeded_posts_queue.get(True, 2)
            self.fail('Should receive nothing instead of %s' % content)
        except Queue.Empty:
            pass

    def test_one_new_file_posted(self):
        c1 = "<test />"
        create_file(self.work_dir, c1)
        try:
            content, auth_header = self.succeeded_posts_queue.get(True, 2)
            self.assertEquals(c1, content)
            self.assertEquals(EXPECTED_BASIC_AUTH_HEADER, auth_header)
        except Queue.Empty:
            self.fail('Should receive one new file')


if __name__ == '__main__':
    unittest.main()
