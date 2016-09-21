import ConfigParser
import logging
import signal
import sys
import thread

from db_storage import DatabaseStorage
from ftpsync import FTPSync

config = ConfigParser.RawConfigParser(allow_no_value=True)
if not config.read('ftpsyncd.conf'):
    exit(-1, "ftpsyncd.conf not found in working directory")

POST_URL = config.get("post", "url")
POST_USER = config.get("post", "user")
POST_PASSWORD = config.get("post", "password")
FTP_SERVER = config.get("ftp", "server")
FTP_PORT = config.getint("ftp", "port")
FTP_USER = config.get("ftp", "user")
FTP_PASSWORD = config.get("ftp", "password")
scan_interval = config.getint("general", "scan_interval_seconds")
dbname = config.get("general", "dbname")

logging.basicConfig(stream=sys.stdout, level=logging.INFO)

if __name__ == '__main__':
    storage = DatabaseStorage(dbname=dbname)
    storage.initialize()
    ftpsync = FTPSync(post_url=POST_URL, post_user=POST_USER, post_password=POST_PASSWORD, storage=storage)

    def signal_handler(signal, frame):
        ftpsync.stop()
        logging.info('Stop signal received')
        sys.exit(0)
    signal.signal(signal.SIGINT, signal_handler)

    resp = ftpsync.connect(FTP_SERVER, FTP_PORT)
    resp = ftpsync.login(FTP_USER, FTP_PASSWORD)

    thread.start_new_thread(ftpsync.monitor_loop, ())
    ftpsync.posting_loop()
