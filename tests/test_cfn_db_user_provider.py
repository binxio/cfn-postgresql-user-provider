import sys
import uuid
import cfn_dbuser_provider
from cfn_dbuser_provider import PostgresDBUser
import psycopg2


class Event(dict):

    def __init__(self, request_type, user, physical_resource_id=None, with_database=False):
        self.update({
            'RequestType': 'Create',
            'ResponseURL': 'http://pre-signed-S3-url-for-response',
            'StackId': 'arn:aws:cloudformation:us-west-2:EXAMPLE/stack-name/guid',
            'RequestId': 'request-%s' % str(uuid.uuid4()),
            'ResourceType': 'Custom::PostgresDBUser',
            'LogicalResourceId': 'Whatever',
            'ResourceProperties': {
                'User': user, 'Password': 'password', 'WithDatabase': with_database,
                'Database': {'User': 'postgres', 'Password': 'password', 'Host': 'localhost',
                              'Port': 5432, 'DBName': 'postgres'}
            }})
        if physical_resource_id is not None:
            self['PhysicalResourceId'] = physical_resource_id

    def test_owner_connection(self):
        p = self['ResourceProperties']
        args = {'host': p['Database']['Host'], 'port': p['Database']['Port'], 'dbname': p['Database']['DBName'],
                'user': p['Database']['User'], 'password': p['Database']['Password']}
        return psycopg2.connect(**args)

    def test_user_connection(self):
        p = self['ResourceProperties']
        args = {'host': p['Database']['Host'], 'port': p['Database']['Port'], 'dbname': p['Database']['DBName'],
                'user': p['User'], 'password': p['Password']}
        return psycopg2.connect(**args)


def test_create_user():
    # create a test user
    name = 'u%s' % str(uuid.uuid4()).replace('-', '')
    event = Event('Create', name)
    response = cfn_dbuser_provider.create(event, {})
    assert response['Status'] == 'SUCCESS', response['Reason']
    assert 'PhysicalResourceId' in response
    physical_resource_id = response['PhysicalResourceId']
    expect_id = 'postgresql:localhost:5432:postgres::%(name)s' % {'name': name}
    assert physical_resource_id == expect_id, 'expected %s, got %s' % (expect_id, physical_resource_id)

    with event.test_user_connection() as connection:
        pass

    event = Event('Create', name, with_database=True)
    response = cfn_dbuser_provider.create(event, {})
    assert response['Status'] == 'SUCCESS', '%s' % response['Reason']

    # delete non existing user
    event = Event('Delete', name + "-", physical_resource_id + '-')
    response = cfn_dbuser_provider.delete(event, {})
    assert response['Status'] == 'SUCCESS', response['Reason']

    # delete the created user
    event = Event('Delete', name, physical_resource_id)
    response = cfn_dbuser_provider.delete(event, {})
    assert response['Status'] == 'SUCCESS', response['Reason']

    try:
        with event.test_user_connection() as connection:
            assert False, 'succesfully logged in to delete user'
    except:
        pass


def test_update_password():
    # create a test database
    name = 'u%s' % str(uuid.uuid4()).replace('-', '')
    event = Event('Create', name, with_database=True)
    event['DeletionPolicy'] = 'Drop'
    response = cfn_dbuser_provider.create(event, {})
    assert response['Status'] == 'SUCCESS', '%s' % response['Reason']
    assert 'PhysicalResourceId' in response
    physical_resource_id = response['PhysicalResourceId']
    expect_id = 'postgresql:localhost:5432:postgres:%(name)s:%(name)s' % {'name': name}
    assert physical_resource_id == expect_id, 'expected %s, got %s' % (expect_id, physical_resource_id)

    # update the password
    event = Event('Update', name, physical_resource_id, with_database=True)
    event['Password'] = 'geheim'
    response = cfn_dbuser_provider.update(event, {})
    assert response['Status'] == 'SUCCESS', response['Reason']

    with event.test_user_connection() as connection:
        pass

    # update the user is not possible
    event = Event('Update', name + '-', physical_resource_id, with_database=True)
    response = cfn_dbuser_provider.update(event, {})
    assert response['Status'] == 'FAILED', response['Reason']

    # delete the created database
    event['User'] = name
    response = cfn_dbuser_provider.delete(event, {})
    assert response['Status'] == 'SUCCESS', response['Reason']


def test_create_database():
    # create a test database
    name = 'u%s' % str(uuid.uuid4()).replace('-', '')
    event = Event('Create', name, with_database=True)
    response = cfn_dbuser_provider.create(event, {})
    assert response['Status'] == 'SUCCESS', '%s' % response['Reason']
    assert 'PhysicalResourceId' in response
    physical_resource_id = response['PhysicalResourceId']
    expect_id = 'postgresql:localhost:5432:postgres:%(name)s:%(name)s' % {'name': name}
    assert physical_resource_id == expect_id, 'expected %s, got %s' % (expect_id, physical_resource_id)

    # create the database again
    response = cfn_dbuser_provider.create(event, {})
    assert response['Status'] == 'SUCCESS', '%s' % response['Reason']

    # delete non existing database
    event = Event('Delete', name + "-", physical_resource_id + '-')
    response = cfn_dbuser_provider.delete(event, {})
    assert response['Status'] == 'SUCCESS', response['Reason']

    # drop the login to the database
    event = Event('Delete', name, physical_resource_id, with_database=True)
    response = cfn_dbuser_provider.delete(event, {})
    assert response['Status'] == 'SUCCESS', response['Reason']

    try:
        with event.test_user_connection() as connection:
            assert False, 'succesfully logged in to delete user'
    except:
        pass

    with event.test_owner_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s', [name])
            rows = cursor.fetchall()
            assert len(rows) == 1, 'database %s was dropped' % name

    # drop the database
    event = Event('Delete', name, physical_resource_id, with_database=True)
    event['DeletionPolicy'] = 'Drop'
    response = cfn_dbuser_provider.delete(event, {})
    assert response['Status'] == 'SUCCESS', response['Reason']

    with event.test_owner_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s', [name])
            rows = cursor.fetchall()
            assert len(rows) == 0, 'database %s still exists' % name


def test_invalid_delete():
    event = Event('Delete', "noop", 'postgresql:localhost:5432:postgres:%(name)s:%(name)s' % {'name': 'noop'})
    del event['ResourceProperties']['User']
    response = cfn_dbuser_provider.delete(event, {})
    assert response['Status'] == 'SUCCESS', response['Reason']


def test_string_port():
    event = Event('Create', "noop")
    event['ResourceProperties']['Port'] = '9543'
    PostgresDBUser(event)
