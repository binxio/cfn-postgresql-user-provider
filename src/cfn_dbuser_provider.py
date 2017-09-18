import os
import re
import sys
import boto3
import logging
import psycopg2
from botocore.exceptions import ClientError
from psycopg2.extensions import AsIs

import cfn_resource

log = logging.getLogger()
log.setLevel(os.getenv("LOGLEVEL", logging.INFO))
handler = cfn_resource.Resource()


class Response(dict):

    def __init__(self, status, reason, resource_id, data={}):
        self['Status'] = status
        self['Reason'] = reason
        self['PhysicalResourceId'] = resource_id
        self['Data'] = data


class ResourceValueError(ValueError):

    def __init__(self, msg):
        super(self.__class__, self).__init__(msg)


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
        if 'DeletionPolicy' not in self:
            self['DeletionPolicy'] = 'Retain'

    def check_valid(self):
        if 'User' not in self:
            raise ResourceValueError("User property is required")
        if not re.match(r'\w+', self.user):
            raise ResourceValueError("User only allowed to contain letter, digits and _")

        if 'Password' not in self:
            raise ResourceValueError("Password property is required")
        if 'WithDatabase' in self:
            v = str(self['WithDatabase']).lower()
            if not (v == 'true' or v == 'false'):
                raise ResourceValueError('WithDatabase property "%s" is not a boolean' % v)

        if 'Database' not in self or type(self['Database']) != dict:
            raise ResourceValueError("Database property is required and must be an object")

        if 'DeletionPolicy' not in self:
            raise ResourceValueError("DeletionPolicy property is required")

        if self['DeletionPolicy'] not in ['Retain', 'Drop']:
            raise ResourceValueError("DeletionPolicy has an invalid value '%s', choose 'Drop' or 'Retain'." %
                                     self['DeletionPolicy'])

        db = self['Database']
        if 'Host' not in db:
            raise ResourceValueError("Host is required in Database")

        if 'Port' not in db:
            raise ResourceValueError("Port is required in Database")
        if not (type(db['Port']) == int or str(db['Port']).isdigit()):
            raise ResourceValueError("Port is required to be an integer in Database")

        if 'User' not in db:
            raise ResourceValueError("User is required in Database")
        if not re.match(r'\w+', self.dbowner):
            raise ResourceValueError("User only allowed to contain letter, digits and _")

        if 'Password' not in db:
            raise ResourceValueError("Password is required in Database")
        if 'DBName' not in db:
            raise ResourceValueError("DBName is required in Database")

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
    def dbowner(self):
        return self['Database']['User']

    @property
    def with_database(self):
        return str(self['WithDatabase']).lower() == 'true'

    @property
    def deletion_policy(self):
        return self['DeletionPolicy']

    @property
    def connect_info(self):
        return {'host': self['Database']['Host'], 'port': self['Database']['Port'],
                'dbname': self['Database']['DBName'], 'user': self['Database']['User'],
                'password': self['Database']['Password']}

    @property
    def logical_resource_id(self):
        return self['LogicalResourceId'] if 'LogicalResourceId' in self else ''

    @property
    def physical_resource_id(self):
        return self['PhysicalResourceId'] if 'PhysicalResourceId' in self else ''

    @property
    def allow_update(self):
        return 'PhysicalResourceId' in self and self.physical_resource_id == self.url

    @property
    def url(self):
        if self.with_database:
            return 'postgresql:%s:%s:%s:%s:%s' % (self.host, self.port, self.dbname, self.user, self.user)
        else:
            return 'postgresql:%s:%s:%s::%s' % (self.host, self.port, self.dbname, self.user)

    def connect(self):
        try:
            self.connection = psycopg2.connect(**self.connect_info)
            self.connection.set_session(autocommit=True)
        except Exception as e:
            raise ValueError('Failed to connect, %s' % e.message)

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, type, value, traceback):
        self.close()
        return False

    def close(self):
        if self.connection:
            self.connection.close()

    def db_exists(self):
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT FROM pg_catalog.pg_database WHERE datname = %s", [self.user])
            rows = cursor.fetchall()
            return len(rows) > 0

    def user_exists(self):
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT FROM pg_catalog.pg_user WHERE usename = %s", [self.user])
            rows = cursor.fetchall()
            return len(rows) > 0

    def drop_user(self):
        with self.connection.cursor() as cursor:
            if self.deletion_policy == 'Drop':
                log.info('drop role  %s', self.user)
                cursor.execute('DROP ROLE %s', [AsIs(self.user)])
            else:
                log.info('disable login of  %s', self.user)
                cursor.execute("ALTER ROLE %s NOLOGIN", [AsIs(self.user)])

    def drop_database(self):
        if self.deletion_policy == 'Drop':
            log.info('drop database of %s', self.user)
            with self.connection.cursor() as cursor:
                cursor.execute('DROP DATABASE %s', [AsIs(self.user)])
        else:
            log.info('not dropping database %s', self.user)

    def update_password(self):
        log.info('update password of %s', self.user)
        with self.connection.cursor() as cursor:
            cursor.execute("ALTER ROLE %s LOGIN ENCRYPTED PASSWORD %s", [AsIs(self.user), self.password])

    def create_user(self):
        log.info('create user %s', self.user)
        with self.connection.cursor() as cursor:
            cursor.execute('CREATE ROLE %s LOGIN ENCRYPTED PASSWORD %s', [AsIs(self.user), self.password])

    def create_database(self):
        log.info('create database %s', self.user)
        with self.connection.cursor() as cursor:
            cursor.execute('GRANT %s TO %s', [AsIs(self.user), AsIs(self.dbowner)])
            cursor.execute('CREATE DATABASE %s OWNER %s', [AsIs(self.user), AsIs(self.user)])
            cursor.execute('REVOKE %s FROM %s', [AsIs(self.user), AsIs(self.dbowner)])

    def grant_ownership(self):
        log.info('grant ownership on %s to %s', self.user, self.user)
        with self.connection.cursor() as cursor:
            cursor.execute('GRANT %s TO %s', [AsIs(self.user), AsIs(self.dbowner)])
            cursor.execute('ALTER DATABASE %s OWNER TO %s', [AsIs(self.user), AsIs(self.user)])
            cursor.execute('REVOKE %s FROM %s', [AsIs(self.user), AsIs(self.dbowner)])

    def drop(self):
        if self.user_exists():
            self.drop_user()
        if self.with_database and self.db_exists():
            self.drop_database()

    def create(self):
        if self.user_exists():
            self.update_password()
        else:
            self.create_user()

        if self.with_database:
            if self.db_exists():
                self.grant_ownership()
            else:
                self.create_database()


@handler.create
def create(event, context):
    try:
        with PostgresDBUser(event) as user:
            user.create()
        return Response('SUCCESS', '', user.url)
    except Exception as e:
        return Response('FAILED', 'Failed to create user, %s' % e.message, 'could-not-create')


@handler.update
def update(event, context):
    try:
        with PostgresDBUser(event) as user:
            if user.allow_update:
                user.update_password()
            else:
                return Response('FAILED', 'Only the password of %s can be updated' % user.user, user.physical_resource_id)
        return Response('SUCCESS', '', user.url)
    except Exception as e:
        return Response('FAILED', 'Failed to update the user, %s' % e.message, event['PhysicalResourceId'])


@handler.delete
def delete(event, context):
    if event['PhysicalResourceId'] == 'could-not-create':
        return Response('SUCCESS', 'user was never created', event['PhysicalResourceId'])

    try:
        with PostgresDBUser(event) as user:
            user.drop()
        return Response('SUCCESS', '', event['PhysicalResourceId'])
    except ResourceValueError as e:
        # ignore resources we could not create in the first place..
        return Response('SUCCESS', e.message, event['PhysicalResourceId'])
    except Exception as e:
        return Response('FAILED', e.message, event['PhysicalResourceId'])
