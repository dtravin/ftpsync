import logging
import sqlite3


class DatabaseStorage:

    def __init__(self, dbname='db.db'):
        self.dbname = dbname

    def initialize(self):
        try:
            con = sqlite3.connect(self.dbname)
            with con:
                cur = con.cursor()
                cur.execute('CREATE TABLE successful_posts (filename VARCHAR(200) PRIMARY KEY)')
                con.commit()
        except Exception, e:
            pass

    def clean(self):
        try:
            con = sqlite3.connect(self.dbname)
            with con:
                cur = con.cursor()
                cur.execute('DROP TABLE successful_posts')
                con.commit()
        except Exception, e:
            logging.error(e)

    def mark_as_posted(self, fname):
        con = sqlite3.connect(self.dbname)
        with con:
            cur = con.cursor()
            cur.execute('INSERT INTO successful_posts (filename) VALUES("%s")' % fname)
            con.commit()

    def find_not_posted(self, remote_filenames):
        con = sqlite3.connect(self.dbname)
        with con:
            cur = con.cursor()
            sql = 'SELECT filename FROM successful_posts where filename in (%s)' % ','.join(['"%s"' % f for f in remote_filenames])
            cur.execute(sql)
            uploaded = [x[0] for x in cur.fetchall()]
            not_posted_yet = []
            for x in remote_filenames:
                if x not in uploaded:
                    not_posted_yet.append(x)
            return not_posted_yet
