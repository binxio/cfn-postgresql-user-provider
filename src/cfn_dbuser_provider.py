import boto3
import hashlib
import logging
import time
import string
import psycopg2
from random import choice
from botocore.exceptions import ClientError
from psycopg2.extensions import AsIs

import cfn_resource

log = logging.getLogger()
log.setLevel(logging.DEBUG)

ssm = boto3.client('ssm')
sts = boto3.client('sts')
region = boto3.session.Session().region_name
account_id = sts.get_caller_identity()['Account']

handler = cfn_resource.Resource()


class Response(dict):

    def __init__(self, status, reason, resource_id, data={}):
        self['Status'] = status
        self['Reason'] = reason
        self['PhysicalResourceId'] = resource_id
        self['Data'] = data


class PostgresDBUser(dict):

    def __init__(self, event):
        self.update(event)
        self.update(event['ResourceProperties'])
        del self['ResourceProperties']
	self.add_defaults()
	self.check_valid()
        self._value = None

    def add_defaults(self):
	if 'Database' in self:
		if 'Port' not in self['Database']:
			self['Database']['Port'] = 5432
	if 'WithDatabase' not in self:
		self['WithDatabase'] = 'true'

    def check_valid(self):
	if 'User' not in self:
		raise ValueError( "User property is required")
	if 'Password' not in self:
		raise ValueError( "Password property is required")
	if 'WithDatabase' in self:
		v = str(self['WithDatabase']).lower()
		if not (v == 'true' or v == 'false'):
			raise ValueError( 'WithDatabase property "%s" is not a boolean' % v)

	if 'Database' not in self or type(self['Database']) != dict:
		raise ValueError( "Database property is required and must be an object")

	db = self['Database']
	if 'Host' not in db:
		raise ValueError( "Host is required in Database")

	if 'Port' not in db:
		raise ValueError( "Port is required in Database")
	if not (type(db['Port']) == int or str.isdigit()):
		raise ValueError( "Port is required to be an integer in Database")

	if 'User' not in db:
		raise ValueError( "User is required in Database")
	if 'Password' not in db:
		raise ValueError( "Password is required in Database")
	if 'DBName' not in db:
		raise ValueError( "DBName is required in Database")

    @property
    def user(self):
        return self['User']

    @property
    def password(self):
        return self['Password']

    @property
    def host(self):
        return self['Database']['Host']

    @property
    def port(self):
        return self['Database']['Port']

    @property
    def dbname(self):
        return self['Database']['DBName']

    @property
    def with_database(self):
        return self['WithDatabase'] == 'true'

    @property
    def connect_info(self):
	return { 'host': self['Database']['Host'], 'port': self['Database']['Port'],
		 'dbname': self['Database']['DBName'], 'user': self['Database']['User'], 
		 'password': self['Database']['Password'] }
 
    @property
    def logical_resource_id(self):
        return self['LogicalResourceId'] if 'LogicalResourceId' in self else ''

    @property
    def physical_resource_id(self):
        return self['PhysicalResourceId'] if 'PhysicalResourceId' in self else ''


    @property
    def allow_overwrite(self):
        return 'PhysicalResourceId' in self and self.physical_resource_id == self.url

    @property
    def url(self):
	if self.with_database:
		return 'postgresql:%s:%s:%s?user=%s' % (self.host, self.port, self.user, self.user)
	else:
		return 'postgresql://%s:%s?user=%s' % (self.host, self.port, self.user)

@handler.create
def create(event, context):
    connection = None
    try:
        dbuser = PostgresDBUser(event)
    except ValueError as e:
	return Response('FAILED', e.message, 'could-not-create')

    try:
	connection = psycopg2.connect(**dbuser.connect_info)
	cursor = connection.cursor()
	cursor.execute("SELECT FROM pg_catalog.pg_user WHERE usename = %s", [dbuser.user])
	rows = cursor.fetchall()
	if len(rows) == 0:
		cursor.execute('CREATE ROLE "%s" LOGIN ENCRYPTED PASSWORD %s', [dbuser.user, dbuser.password])
	else:
		return Response('FAILED', 'User %s already exists' % dbuser.user, 'could-not-create')
    finally:
	if connection is not None:
		connection.close()
	
    return Response('SUCCESS', '', dbuser.url)



@handler.update
def update(event, context):
    return Response('SUCCESS', reason, event['PhysicalResourceId'])


@handler.delete
def delete(event, context):
    connection = None
    try:
        dbuser = PostgresDBUser(event)
    except ValueError as e:
	return Response('FAILED', e.message)

    try:
	connection = psycopg2.connect(**dbuser.connect_info)
	cursor = connection.cursor()
	cursor.execute('DROP ROLE "%s"', [AsIs(dbuser.user)])
    finally:
	if connection is not None:
		connection.close()
	
    return Response('SUCCESS', '', dbuser.url)
