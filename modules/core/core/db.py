# -*- coding: utf-8 -*-
'''
	Lernfunk3::Core::db
	~~~~~~~~~~~~~~~

	This module provides read and write access to the central Lernfunk database.
	
	** Db contains database handline

    :copyright: (c) 2012 by Lars Kiesow
    :license: FreeBSD and LGPL, see LICENSE for more details.
'''

from core import app
import MySQLdb
from flask import _app_ctx_stack


def get_db():
	'''Opens a new database connection if there is none yet for the
	current application context.
	'''
	top = _app_ctx_stack.top
	if not hasattr(top, 'mysql_db'):
		top.mysql_db = MySQLdb.connect(
			host    = app.config['DATABASE_HOST'],
			user    = app.config['DATABASE_USER'],
			passwd  = app.config['DATABASE_PASSWD'],
			db      = app.config['DATABASE_NAME'],
			port    = int(app.config['DATABASE_PORT']),
			charset = 'utf8' )
	return top.mysql_db


@app.teardown_appcontext
def close_db_connection(exception):
	'''Closes the database again at the end of the request.
	'''
	top = _app_ctx_stack.top
	if hasattr(top, 'mysql_db'):
		top.mysql_db.close()