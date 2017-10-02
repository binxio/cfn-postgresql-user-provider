import os
import re
import sys
import boto3
import logging
import psycopg2
from botocore.exceptions import ClientError
from psycopg2.extensions import AsIs

from cfn_provider import ResourceProvider

log = logging.getLogger()
log.setLevel(level=os.getenv("LOGLEVEL", logging.INFO))


class PostgresDBUserProvider(ResourceProvider):

    def __init__(self):
        super(PostgresDBUserProvider, self).__init__()
        self.ssm = boto3.client('ssm')
        self.connection = None
        self.owner_password = None
        self.user_password = None

    def is_valid_request(self):
        try:
            self.check_valid()
        except ValueError as e:
            self.fail(e.message)
            return False
        return True

    def check_valid(self):
        if 'User' not in self.properties:
            raise ValueError("User property is required")
        if not re.match(r'[a-zA-Z][\$\w]+', self.properties['User']):
            raise ValueError(
                "User only allowed to start with a letter followed by zero or more letters, digits, _ or $")

        if ('Password' not in self.properties and 'PasswordParameterName' not in self.properties) or ('Password' in self.properties and 'PasswordParameterName' in self.properties):
            raise ValueError("Password or PasswordParameterName is required")

        if 'PasswordParameterName' in self.properties:
            name = self.properties['PasswordParameterName']
            try:
                response = self.ssm.get_parameter(Name=name, WithDecryption=True)
                self.user_password = response['Parameter']['Value']
            except ClientError as e:
                raiseValueError('Could not obtain password using name %s, %s' % (name, e.message))
        else:
            self.user_password = self.properties['Password']

        if 'WithDatabase' in self.properties:
            v = str(self.properties['WithDatabase']).lower()
            if not (v == 'true' or v == 'false'):
                raise ValueError('WithDatabase property "%s" is not a boolean' % v)

        if 'Database' not in self.properties or type(self.properties['Database']) != dict:
            raise ResourceValueError('Database property is required and must be an object')

        if 'DeletionPolicy' in self.properties and self.properties['DeletionPolicy'] not in ['Retain', 'Drop']:
            raise ValueError("DeletionPolicy has an invalid value '%s', choose 'Drop' or 'Retain'." %
                             self.properties['DeletionPolicy'])

        db = self.properties['Database']
        if 'DBName' not in db:
            raise ValueError("DBName is required in Database")

        if 'Host' not in db:
            raise ValueError("Host is required in Database")

        if 'Port' not in db:
            raise ValueError("Port is required in Database")
        if not (type(db['Port']) == int or str(db['Port']).isdigit()):
            raise ValueError("Port is required to be an integer in Database")

        if 'User' not in db:
            raise ValueError("User is required in Database")
        if not re.match(r'\w+', db['User']):
            raise ValueError('User only allowed to contain letter, digits and _')

        if ('Password' not in db and 'PasswordParameterName' not in db) or ('Password' in db and 'PasswordParameterName' in db):
            raise ValueError('Password or PasswordParameterName is required in Database')

        if 'PasswordParameterName' in db:
            name = db['PasswordParameterName']
            try:
                response = self.ssm.get_parameter(Name=name, WithDecryption=True)
                self.dbowner_password = response['Parameter']['Value']
            except ClientError as e:
                raise ValueError('Could not obtain password using name %s, %s' % (name, e.message))
        else:
            self.dbowner_password = db['Password']

    @property
    def user(self):
        return self.get('User')

    @property
    def host(self):
        return self.get('Database', {}).get('Host', None)

    @property
    def port(self):
        return self.get('Database', {}).get('Port', 5432)

    @property
    def dbname(self):
        return self.get('Database', {}).get('DBName', None)

    @property
    def dbowner(self):
        return self.get('Database', {}).get('User', None)

    @property
    def with_database(self):
        return str(self.get('WithDatabase', 'true')).lower() == 'true'

    @property
    def deletion_policy(self):
        return self.get('DeletionPolicy', 'Retain')

    @property
    def connect_info(self):
        return {'host': self.host, 'port': self.port, 'dbname': self.dbname,
                'user': self.dbowner, 'password': self.dbowner_password}

    @property
    def logical_resource_id(self):
        return self.request['LogicalResourceId'] if 'LogicalResourceId' in self else ''

    @property
    def allow_update(self):
        return self.url == self.physical_resource_id

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

    def close(self):
        if self.connection:
            self.connection.close()

    def db_exists(self):
        with self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT FROM pg_catalog.pg_database WHERE datname = %s", [self.user])
            rows = cursor.fetchall()
            return len(rows) > 0

    def role_exists(self):
        with self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT FROM pg_catalog.pg_roles WHERE rolname = %s", [self.user])
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
        log.info('update password of role %s', self.user)
        with self.connection.cursor() as cursor:
            cursor.execute("ALTER ROLE %s LOGIN ENCRYPTED PASSWORD %s", [
                           AsIs(self.user), self.user_password])

    def create_role(self):
        log.info('create role %s ', self.user)
        with self.connection.cursor() as cursor:
            cursor.execute('CREATE ROLE %s LOGIN ENCRYPTED PASSWORD %s', [
                           AsIs(self.user), self.user_password])

    def create_database(self):
        log.info('create database %s', self.user)
        with self.connection.cursor() as cursor:
            cursor.execute('GRANT %s TO %s', [
                           AsIs(self.user), AsIs(self.dbowner)])
            cursor.execute('CREATE DATABASE %s OWNER %s', [
                           AsIs(self.user), AsIs(self.user)])
            cursor.execute('REVOKE %s FROM %s', [
                           AsIs(self.user), AsIs(self.dbowner)])

    def grant_ownership(self):
        log.info('grant ownership on %s to %s', self.user, self.user)
        with self.connection.cursor() as cursor:
            cursor.execute('GRANT %s TO %s', [
                           AsIs(self.user), AsIs(self.dbowner)])
            cursor.execute('ALTER DATABASE %s OWNER TO %s', [
                           AsIs(self.user), AsIs(self.user)])
            cursor.execute('REVOKE %s FROM %s', [
                           AsIs(self.user), AsIs(self.dbowner)])

    def drop(self):
        if self.with_database and self.db_exists():
            self.drop_database()
        if self.role_exists():
            self.drop_user()

    def create_user(self):
        if self.role_exists():
            self.update_password()
        else:
            self.create_role()

        if self.with_database:
            if self.db_exists():
                self.grant_ownership()
            else:
                self.create_database()

    def create(self):
        try:
            self.connect()
            self.create_user()
            self.set_physical_resource_id(self.url)
        except Exception as e:
            self.set_physical_resource_id('could-not-create')
            self.fail('Failed to create user, %s' % e.message)
        finally:
            self.close()

    def update(self):
        try:
            self.connect()
            if self.allow_update:
                self.update_password()
            else:
                self.fail('Only the password of %s can be updated' % self.user)
        except Exception as e:
            self.fail('Failed to update the user, %s' % e.message)
        finally:
            self.close()

    def delete(self):
        if self.physical_resource_id == 'could-not-create':
            self.success('user was never created')

        try:
            self.connect()
            self.drop()
        except Exception as e:
            return self.fail(e.message)
        finally:
            self.close()

provider = PostgresDBUserProvider()


def handler(request, context):
    return provider.handle(request, context)
