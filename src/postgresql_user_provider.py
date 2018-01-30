import boto3
import logging
import psycopg2
from botocore.exceptions import ClientError
from psycopg2.extensions import AsIs
from cfn_resource_provider import ResourceProvider

log = logging.getLogger()

request_schema = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type": "object",
    "oneOf": [
        {"required": ["Connection", "User", "Password"]},
        {"required": ["Connection", "User", "PasswordParameterName"]}
    ],
    "properties": {
        "Database": {"$ref": "#/definitions/connection"
                     },
        "User": {
            "type": "string",
            "pattern": "^[A-Za-z][A-Za-z0-9_\$]*$",
            "description": "the user to create"
        },
        "Password": {
            "type": "string",
            "pattern": "^[A-Za-z_][A-Za-z0-9_-]*$",
            "description": "the password for the user"
        },
        "PasswordParameterName": {
            "type": "string",
            "minlength": 1,
            "description": "the name of the password in the Parameter Store."
        },
        "WithDatabase": {
            "type": "boolean",
            "default": "false",
            "description": "create a database with the same name, or only a user"
        },
        "DeletionPolicy": {
            "type": "string",
            "default": "Retain",
            "enum": ["Drop", "Retain"]
        }
    },
    "definitions": {
        "connection": {
            "type": "object",
            "oneOf": [
                {"required": ["DBName", "Host", "Port", "User", "Password"]},
                {"required": ["DBName", "Host", "Port", "User", "PasswordParameterName"]}
            ],
            "properties": {
                "DBName": {
                    "type": "string",
                    "description": "the name of the database"
                },
                "Host": {
                    "type": "string",
                    "description": "the host of the database"
                },
                "Port": {
                    "type": "integer",
                    "default": 5432,
                    "description": "the network port of the database"
                },
                "User": {
                    "type": "string",
                    "description": "the username of the database owner"
                },
                "Password": {
                    "type": "string",
                    "description": "the password of the database owner"
                },
                "PasswordParameterName": {
                    "type": "string",
                    "description": "the name of the database owner password in the Parameter Store."
                }
            }
        }
    }
}


class PostgresDBUserProvider(ResourceProvider):

    def __init__(self):
        super(PostgresDBUserProvider, self).__init__()
        self.ssm = boto3.client('ssm')
        self.connection = None

    def convert_property_types(self):
        self.heuristic_convert_property_types(self.properties)

    def get_password(self, name):
        try:
            response = self.ssm.get_parameter(Name=name, WithDecryption=True)
            return response['Parameter']['Value']
        except ClientError as e:
            raise ValueError('Could not obtain password using name {}, {}'.format(name, e.message))

    @property
    def user_password(self):
        if 'Password' in self.properties:
            return self.get('Password')
        else:
            return self.get_password(self.get('PasswordParameterName'))

    @property
    def dbowner_password(self):
        db = self.get('Database')
        if 'Password' in db:
            return db.get('Password')
        else:
            return self.get_password(db['PasswordParameterName'])

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
        return self.get('WithDatabase', False)

    @property
    def deletion_policy(self):
        return self.get('DeletionPolicy')

    @property
    def connect_info(self):
        return {'host': self.host, 'port': self.port, 'dbname': self.dbname,
                'user': self.dbowner, 'password': self.dbowner_password}

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
        log.info('connecting to database %s on port %d as user %s', self.host, self.port, self.dbowner)
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
            self.physical_resource_id = self.url
        except Exception as e:
            self.physical_resource_id = 'could-not-create'
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
