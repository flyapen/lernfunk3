# -*- coding: utf-8 -*-
"""
	Lernfunk3::Core::View
	~~~~~~~~~~~~~~~

	This module provides read and write access to the central Lernfunk database.

	** View contains the liveview REST endpoint

    :copyright: (c) 2012 by Lars Kiesow
    :license: FreeBSD and LGPL, see LICENSE for more details.
"""

from core import app
from core.util import *
from core.db import get_db
from core.authenticate import get_authorization

from flask import request, session, g, redirect, url_for, abort, make_response


@app.route('/view/media/')
@app.route('/view/media/<media_id>')
@app.route('/view/media/<media_id>/<lang>')
def list_media(media_id=None, lang=None):

	user = None
	try:
		user = get_authorization( request.authorization )
	except KeyError as e:
		abort(401, e)
	if not user:
		abort(403)
	
	if app.debug:
		print('### User #######################')
		print(user)
		print('################################')
	query_condition = ''
	# Admins and editors can see everything. So there is no need for conditions.
	if not ( user.is_admin() or user.is_editor() ):
		# Add user as conditions
		query_condition = '''left outer join lf_access a on a.media_id = m.id 
			where ( a.user_id = %s ''' % user.id
		# Add groups as condition (if necessary)
		if not len(user.groups):
			query_condition += ') '
		elif len(user.groups) == 1:
			query_condition += 'or a.group_id = %s ) ' % user.groups.keys()[0]
		else:
			grouplist = '(' + ','.join([str(id) for id in user.groups.keys()]) + ')'
			query_condition += ' a.group_id in %s ) ' % grouplist
		# Add access condition
		query_condition += 'and read_access '


	# Check flags for additional data
	with_series      = is_true(request.args.get('with_series',      '1'))
	with_contributor = is_true(request.args.get('with_contributor', '1'))
	with_creator     = is_true(request.args.get('with_creator',     '1'))
	with_publisher   = is_true(request.args.get('with_publisher',   '1'))
	with_file        = is_true(request.args.get('with_file',        '0'))
	with_subject     = is_true(request.args.get('with_subject',     '1'))
	limit            = to_int(request.args.get('limit',  '10'), 10)
	offset           = to_int(request.args.get('offset',  '0'),  0)

	# Request data
	db = get_db()
	cur = db.cursor()
	query = '''select bin2uuid(m.id), m.version, m.parent_version, m.language,
			m.title, m.description, m.owner, m.editor, m.timestamp_edit,
			m.timestamp_created, m.published, m.source, m.visible,
			m.source_system, m.source_key, m.rights, m.type, m.coverage,
			m.relation from lf_published_media m '''
	if media_id:
		# abort with 400 Bad Request if media_id is not a valid uuid or thread it
		# as language code if language argument does not exist
		if is_uuid(media_id):
			query_condition += ( 'and ' if query_condition else 'where ' ) + \
					'id = uuid2bin("%s") ' % media_id
		else:
			if lang:
				abort(400)
			else:
				lang = media_id

	# Check for language argument
	if lang:
		for c in lang:
			if c not in lang_chars:
				abort(400)
		query_condition += ( 'and ' if query_condition else 'where ' ) + \
				'language = "%s" ' % lang
	query += query_condition

	# Add limit and offset
	query += 'limit %s, %s ' % ( offset, limit )

	if app.debug:
		print('### Query ######################')
		print( query )
		print('################################')

	dom = result_dom()
	cur.execute( query )
	# For each media we get
	for id, version, parent_version, language, title, description, owner, \
			editor, timestamp_edit, timestamp_created, published, source, \
			visible, source_system, source_key, rights, type, coverage, \
			relation in cur.fetchall():
		m = dom.createElement("lf:media")
		# Add default elements
		xml_add_elem( dom, m, "dc:identifier",     id )
		xml_add_elem( dom, m, "lf:version",        version )
		xml_add_elem( dom, m, "lf:parent_version", parent_version )
		xml_add_elem( dom, m, "dc:language",       language )
		xml_add_elem( dom, m, "dc:title",          title )
		xml_add_elem( dom, m, "dc:description",    description )
		xml_add_elem( dom, m, "lf:owner",          owner )
		xml_add_elem( dom, m, "lf:editor",         editor )
		xml_add_elem( dom, m, "dc:date",           timestamp_created )
		xml_add_elem( dom, m, "lf:last_edit",      timestamp_edit )
		xml_add_elem( dom, m, "lf:published",      published )
		xml_add_elem( dom, m, "dc:source",         source )
		xml_add_elem( dom, m, "lf:visible",        visible )
		xml_add_elem( dom, m, "lf:source_system",  source_system )
		xml_add_elem( dom, m, "lf:source_key",     source_key )
		xml_add_elem( dom, m, "dc:rights",         rights )
		xml_add_elem( dom, m, "dc:type",           type )

		# Get series
		if with_series:
			cur.execute( '''select bin2uuid(series_id) from lf_media_series 
				where media_id = uuid2bin("%s")''' % id )
			for (series_id,) in cur.fetchall():
				xml_add_elem( dom, m, "lf:series_id", series_id )

		# Get contributor (user)
		if with_contributor:
			cur.execute( '''select user_id from lf_media_contributor
				where media_id = uuid2bin("%s")''' % id )
			for (user_id,) in cur.fetchall():
				xml_add_elem( dom, m, "lf:contributor", user_id )

		# Get creator (user)
		if with_creator:
			cur.execute( '''select user_id from lf_media_creator
				where media_id = uuid2bin("%s")''' % id )
			for (user_id,) in cur.fetchall():
				xml_add_elem( dom, m, "lf:creator", user_id )

		# Get publisher (organization)
		if with_publisher:
			cur.execute( '''select organization_id from lf_media_publisher
				where media_id = uuid2bin("%s")''' % id )
			for (organization_id,) in cur.fetchall():
				xml_add_elem( dom, m, "lf:publisher", organization_id )

		# Get files
		if with_file:
			cur.execute( '''select bin2uuid(id), format, uri,
				source, source_key, source_system from lf_prepared_file
				where media_id = uuid2bin("%s")''' % id )
			for id, format, uri, src, src_key, src_sys in cur.fetchall():
				f = dom.createElement("lf:file")
				xml_add_elem( dom, f, "dc:identifier",    id )
				xml_add_elem( dom, f, "dc:format",        format )
				xml_add_elem( dom, f, "lf:uri",           uri )
				xml_add_elem( dom, f, "lf:source",        src )
				xml_add_elem( dom, f, "lf:source_key",    src_key )
				xml_add_elem( dom, f, "lf:source_system", src_sys )
				m.appendChild(f)

		# Get subjects
		if with_subject:
			cur.execute( '''select s.name from lf_media_subject ms 
					join lf_subject s on s.id = ms.subject_id 
					where s.language = "%s" 
					and ms.media_id = uuid2bin("%s") ''' % (language, id) )
			for (subject,) in cur.fetchall():
				xml_add_elem( dom, m, "dc:subject", subject )


		dom.childNodes[0].appendChild(m)

	response = make_response(dom.toxml())
	response.mimetype = 'application/xml'
	return response



@app.route('/view/series/')
@app.route('/view/series/<series_id>')
@app.route('/view/series/<series_id>/<lang>')
def list_series(series_id=None, lang=None):

	# Check flags for additional data
	with_media       = is_true(request.args.get('with_media',       '1'))
	with_creator     = is_true(request.args.get('with_creator',     '1'))
	with_publisher   = is_true(request.args.get('with_publisher',   '1'))
	with_subject     = is_true(request.args.get('with_subject',     '1'))
	limit            = to_int(request.args.get('limit',  '10'), 10)
	offset           = to_int(request.args.get('offset',  '0'),  0)

	db = get_db()
	cur = db.cursor()
	query = '''select bin2uuid(id), version, parent_version, title,
			language, description, source, timestamp_edit, timestamp_created,
			published, owner, editor, visible, source_key, source_system 
			from lf_published_series '''
	if series_id:
		# abort with 400 Bad Request if series_id is not a valid uuid or thread it
		# as language code if language argument does not exist
		if is_uuid(series_id):
			query += 'where id = uuid2bin("%s") ' % series_id
		else:
			if lang:
				abort(400)
			else:
				lang = series_id

	# Check for language argument
	if lang:
		for c in lang:
			if c not in lang_chars:
				abort(400)
		query += ( 'and language = "%s" ' \
				if 'where id' in query \
				else 'where language = "%s" ' ) % lang

	# Add limit and offset
	query += 'limit %s, %s ' % ( offset, limit )

	cur.execute( query )
	dom = result_dom()

	# For each media we get
	for id, version, parent_version, title, language, description, source, \
			timestamp_edit, timestamp_created, published, owner, editor, \
			visible, source_key, source_system in cur.fetchall():
		s = dom.createElement('lf:series')
		xml_add_elem( dom, s, "dc:identifier",     id )
		xml_add_elem( dom, s, "lf:version",        version )
		xml_add_elem( dom, s, "lf:parent_version", parent_version )
		xml_add_elem( dom, s, "dc:title",          title )
		xml_add_elem( dom, s, "dc:language",       language )
		xml_add_elem( dom, s, "dc:description",    description )
		xml_add_elem( dom, s, "dc:source",         source )
		xml_add_elem( dom, s, "lf:last_edit",      timestamp_edit )
		xml_add_elem( dom, s, "dc:date",           timestamp_created )
		xml_add_elem( dom, s, "lf:published",      published )
		xml_add_elem( dom, s, "lf:owner",          owner )
		xml_add_elem( dom, s, "lf:editor",         editor )
		xml_add_elem( dom, s, "lf:visible",        visible )
		xml_add_elem( dom, s, "lf:source_key",     source_key )
		xml_add_elem( dom, s, "lf:source_system",  source_system )
		dom.childNodes[0].appendChild(s)

		# Get media
		if with_media:
			cur.execute( '''select bin2uuid(media_id) from lf_media_series 
				where series_id = uuid2bin("%s")''' % id )
			for (media_id,) in cur.fetchall():
				xml_add_elem( dom, s, "lf:media_id", media_id )

		# Get creator (user)
		if with_creator:
			cur.execute( '''select user_id from lf_series_creator
				where series_id = uuid2bin("%s")''' % id )
			for (user_id,) in cur.fetchall():
				xml_add_elem( dom, s, "lf:creator", user_id )

		# Get publisher (organization)
		if with_publisher:
			cur.execute( '''select organization_id from lf_series_publisher
				where series_id = uuid2bin("%s")''' % id )
			for (organization_id,) in cur.fetchall():
				xml_add_elem( dom, s, "lf:publisher", organization_id )

		# Get subjects
		if with_subject:
			cur.execute( '''select s.name from lf_series_subject ms 
					join lf_subject s on s.id = ms.subject_id 
					where s.language = "%s" 
					and ms.series_id = uuid2bin("%s") ''' % (language, id) )
			for (subject,) in cur.fetchall():
				xml_add_elem( dom, s, "dc:subject", subject )

	response = make_response(dom.toxml())
	response.mimetype = 'application/xml'
	return response



@app.route('/view/subject/')
@app.route('/view/subject/<subject_id>')
@app.route('/view/subject/<subject_id>/<lang>')
def list_subject(subject_id=None, lang=None):

	limit            = to_int(request.args.get('limit',  '10'), 10)
	offset           = to_int(request.args.get('offset',  '0'),  0)

	db = get_db()
	cur = db.cursor()
	query = '''select id, name, language from lf_subject '''
	if subject_id:
		# abort with 400 Bad Request if subject_id is not valid or thread it
		# as language code if language argument does not exist
		try:
			query += 'where id = %s ' % int(subject_id)
		except ValueError:
			# subject_id is not valid
			if lang:
				abort(400)
			else:
				lang = subject_id

	# Check for language argument
	if lang:
		for c in lang:
			if c not in lang_chars:
				abort(400)
		query += ( 'and language = "%s" ' \
				if 'where id' in query \
				else 'where language = "%s" ' ) % lang

	# Add limit and offset
	query += 'limit %s, %s ' % ( offset, limit )

	cur.execute( query )
	dom = result_dom()

	# For each media we get
	for id, name, language in cur.fetchall():
		s = dom.createElement('lf:subject')
		xml_add_elem( dom, s, "lf:id",       id )
		xml_add_elem( dom, s, "lf:name",     name )
		xml_add_elem( dom, s, "dc:language", language )
		dom.childNodes[0].appendChild(s)

	response = make_response(dom.toxml())
	response.mimetype = 'application/xml'
	return response



@app.route('/view/file/')
@app.route('/view/file/<file_id>')
def list_file(file_id=None):
	limit            = to_int(request.args.get('limit',  '10'), 10)
	offset           = to_int(request.args.get('offset',  '0'),  0)

	db = get_db()
	cur = db.cursor()
	query = '''select bin2uuid(id), format, uri, bin2uuid(media_id),
				source, source_key, source_system from lf_prepared_file '''
	if file_id:
		# abort with 400 Bad Request if file_id is not valid
		if is_uuid(file_id):
			query += 'where id = uuid2bin("%s") ' % file_id
		else:
			abort(400)

	# Add limit and offset
	query += 'limit %s, %s ' % ( offset, limit )

	cur.execute( query )
	dom = result_dom()

	# For each file we get
	for id, format, uri, media_id, src, src_key, src_sys in cur.fetchall():
		f = dom.createElement("lf:file")
		xml_add_elem( dom, f, "dc:identifier",    id )
		xml_add_elem( dom, f, "dc:format",        format )
		xml_add_elem( dom, f, "lf:uri",           uri )
		xml_add_elem( dom, f, "lf:media_id",      media_id )
		xml_add_elem( dom, f, "lf:source",        src )
		xml_add_elem( dom, f, "lf:source_key",    src_key )
		xml_add_elem( dom, f, "lf:source_system", src_sys )
		dom.childNodes[0].appendChild(f)

	response = make_response(dom.toxml())
	response.mimetype = 'application/xml'
	return response


@app.route('/view/organization/')
@app.route('/view/organization/<organization_id>')
def list_organization(organization_id=None):
	limit            = to_int(request.args.get('limit',  '10'), 10)
	offset           = to_int(request.args.get('offset',  '0'),  0)

	db = get_db()
	cur = db.cursor()
	query = '''select id, name, vcard_uri, parent_organization 
			from lf_organization '''
	if organization_id:
		# abort with 400 Bad Request if file_id is not valid
		try:
			query += 'where id = %s ' % int(organization_id)
		except ValueError:
			abort(400)

	# Add limit and offset
	query += 'limit %s, %s ' % ( offset, limit )

	cur.execute( query )
	dom = result_dom()

	# For each file we get
	for id, name, vcard_uri, parent_organization in cur.fetchall():
		o = dom.createElement("lf:organization")
		xml_add_elem( dom, o, "dc:identifier",             id )
		xml_add_elem( dom, o, "lf:name",                   name )
		xml_add_elem( dom, o, "lf:parent_organization_id", parent_organization )
		xml_add_elem( dom, o, "lf:vcard_uri",              vcard_uri )
		dom.childNodes[0].appendChild(o)

	response = make_response(dom.toxml())
	response.mimetype = 'application/xml'
	return response



@app.route('/view/group/')
@app.route('/view/group/<group_id>')
def list_group(group_id=None):
	limit            = to_int(request.args.get('limit',  '10'), 10)
	offset           = to_int(request.args.get('offset',  '0'),  0)

	db = get_db()
	cur = db.cursor()
	query = '''select id, name from lf_group '''
	if group_id:
		# abort with 400 Bad Request if id is not valid
		try:
			query += 'where id = %s ' % int(group_id)
		except ValueError:
			abort(400)

	# Add limit and offset
	query += 'limit %s, %s ' % ( offset, limit )

	cur.execute( query )
	dom = result_dom()

	# For each file we get
	for id, name in cur.fetchall():
		g = dom.createElement("lf:group")
		xml_add_elem( dom, g, "dc:identifier", id )
		xml_add_elem( dom, g, "lf:name",       name )
		dom.childNodes[0].appendChild(g)

	response = make_response(dom.toxml())
	response.mimetype = 'application/xml'
	return response


@app.route('/view/user/')
@app.route('/view/user/<user_id>')
def list_user(user_id=None):
	limit            = to_int(request.args.get('limit',  '10'), 10)
	offset           = to_int(request.args.get('offset',  '0'),  0)

	db = get_db()
	cur = db.cursor()
	query = '''select id, name, vcard_uri from lf_user '''
	if user_id:
		# abort with 400 Bad Request if id is not valid
		try:
			query += 'where id = %s ' % int(user_id)
		except ValueError:
			abort(400)

	# Add limit and offset
	query += 'limit %s, %s ' % ( offset, limit )

	cur.execute( query )
	dom = result_dom()

	# For each file we get
	for id, name, vcard_uri in cur.fetchall():
		u = dom.createElement("lf:user")
		xml_add_elem( dom, u, "dc:identifier", id )
		xml_add_elem( dom, u, "lf:name",       name )
		xml_add_elem( dom, u, "lf:vcard_uri",  vcard_uri )
		dom.childNodes[0].appendChild(u)

	response = make_response(dom.toxml())
	response.mimetype = 'application/xml'
	return response