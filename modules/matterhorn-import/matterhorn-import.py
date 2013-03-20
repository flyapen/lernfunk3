#!/bin/env python
# -*- coding: utf-8 -*-

# Set default encoding to UTF-8
import sys
reload(sys)
sys.setdefaultencoding('utf8')

import json
import urllib2
from xml.dom.minidom import parseString
from pprint import pprint
from util import xml_get_data


def check_rules( ruleset, data ):
	''' Check rules defined in configuration. Returns False if a rule does not
	apply, True otherwise.
	'''
	if ruleset['-mimetype'] and \
			ruleset['-mimetype'] == data.get('mimetype'):
		return False
	if ruleset['-extension'] and \
			data.get('url').endwith(ruleset['-extension']):
		return False
	if ruleset['-protocol'] and \
			data.get('url').startswith(ruleset['-protocol']):
		return False
	if ruleset['-source_system'] and \
			ruleset['-source_system'] == data.get('source_system'):
		return False
	if ruleset['-type'] and \
			ruleset['-type'] == type:
		return False
	if ruleset['mimetype'] and \
			ruleset['mimetype'] != data.get('mimetype'):
		return False
	if ruleset['extension'] and \
			not data.get('url').endswith( ruleset['extension'] ):
		return False
	if ruleset['protocol'] and \
			not data.get('url').startswith( ruleset['protocol'] ):
		return False
	if ruleset['source_system'] and \
			ruleset['source_system'] != data.get('source_system'):
		return False
	if ruleset['type'] and \
			ruleset['type'] != data.get('type'):
		return False
	# Finally check the tags
	if True in [ t in data['tags'] for t in ruleset['-tags'] ]:
		return False
	if False in [ t in data['tags'] for t in ruleset['tags'] ]:
		return False
	return True


def split_vals( vals, delim, stripchars=' ' ):
	for d in delim:
		new = []
		for v in vals:
			for n in v.split(d):
				n = n.strip(stripchars)
				if n:
					new.append(n)
		vals = new
	return vals


def load_config():
	f = open( 'config.json', 'r')
	config = json.load(f)
	f.close()

	# Check/normalize config
	for key in ['creator', 'contributor', 'subject']:
		if not key in config['delimeter'].keys():
			entry[key] = None
	for entry in config['trackrules'] + config['metadatarules']:
		for key in ['name','comment']:
			if not key in entry.keys():
				entry[key] = ''
		for key in ['mimetype', '-mimetype', 'extension', '-extension', \
				'protocol', '-protocol', 'source_system', '-source_system', \
				'lf-quality', 'lf-server-id', 'lf-type', 'type', '-type']:
			if not key in entry.keys():
				entry[key] = None
		for key in ['tags', '-tags']:
			if not key in entry.keys():
				entry[key] = []

	return config


def import_media( mp ):
	global config

	# This will be a post field:
	source_system = 'localhost'

	# Parse XML
	mp = parseString( mp )

	# Get metadata
	m = {}
	s = {}
	m['title']       = xml_get_data(mp, 'title')
	s['id']          = xml_get_data(mp, 'series')
	s['title']       = xml_get_data(mp, 'seriestitle')
	m['license']     = xml_get_data(mp, 'license')
	m['language']    = xml_get_data(mp, 'language')
	m['creator']     = xml_get_data(mp, 'creator',     array='always')
	m['contributor'] = xml_get_data(mp, 'contributor', array='always')
	m['subject']     = xml_get_data(mp, 'subject',     array='always')

	# Split values if necessary
	m['subject']     = split_vals( m['subject'], 
			config['delimeter']['subject'] or [] )
	m['creator']     = split_vals( m['creator'], 
			config['delimeter']['creator'] or [] )
	m['contributor'] = split_vals( m['contributor'], 
			config['delimeter']['contributor'] or [] )

	# Get additional metadata
	for cat in mp.getElementsByTagNameNS('*', 'catalog'):
		t = {'source_system' : source_system}
		t['mimetype'] = xml_get_data(cat, 'mimetype')
		t['type']     = cat.getAttribute('type')
		t['id']       = cat.getAttribute('ref').lstrip('catalog').lstrip(':')
		t['tags']     = xml_get_data(cat, 'tag', array='always')
		t['url']      = xml_get_data(cat, 'url')

		for r in config['metadatarules']:
			if not check_rules( r, t ):
				continue
			# Get additional metadata from server
			try:
				u = urllib2.urlopen(t['url'])
				dcdata = u.read()
				u.close()
				dcdata = parseString(dcdata)
				ns = 'http://purl.org/dc/terms/'
				if r.get('use-for') == 'media':
					m['created'] = xml_get_data(dcdata, 'created', namespace=ns)
				if r.get('use-for') == 'series':
					s['creator']     = xml_get_data(dcdata, 'creator',     namespace=ns)
					s['contributor'] = xml_get_data(dcdata, 'contributor', namespace=ns)
			except urllib2.URLError:
				pass




	for track in mp.getElementsByTagNameNS('*', 'track'):
		t = {'source_system' : source_system}
		t['mimetype'] = xml_get_data(track, 'mimetype')
		t['type']     = track.getAttribute('type')
		t['id']       = track.getAttribute('ref').lstrip('track').lstrip(':')
		t['tags']     = xml_get_data(track, 'tag', array='always')
		t['url']      = xml_get_data(track, 'url')

		for r in config['trackrules']:
			# Check rules defined in configuration. If a rule does not apply jump
			# straight to the next set of rules.
			if not check_rules( r, t ):
				continue

			# Build request
			pprint(t)

			# Send request
			# http://docs.python.org/2/library/urllib2.html
	
	pprint(m)
	pprint(s)



def main():
	global config
	try:
		config = load_config()
	except ValueError as e:
		print( 'Error loading config: %s' % str(e) )
		exit()

	f = open( sys.argv[1], 'r' )
	mediapackage = f.read()
	f.close()

	import_media( mediapackage )


if __name__ == "__main__":
	main()
