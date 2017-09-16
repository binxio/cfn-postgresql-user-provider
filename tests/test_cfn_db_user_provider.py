import sys
import uuid
import cfn_dbuser_provider

class Event(dict):

    def __init__(self, request_type, user, physical_resource_id=None):
        self.update({
            'RequestType': 'Create',
            'ResponseURL': 'http://pre-signed-S3-url-for-response',
            'StackId': 'arn:aws:cloudformation:us-west-2:EXAMPLE/stack-name/guid',
            'RequestId': 'request-%s' % str(uuid.uuid4()),
            'ResourceType': 'Custom::PostgresDBUser',
            'LogicalResourceId': 'Whatever',
            'ResourceProperties': {
                'User': user, 'Password': 'password', 'WithDatabase': False, 
		'Database': { 'User': 'postgres', 'Password': 'password', 'Host': 'localhost',
				'Port': 5432, 'DBName': 'postgres' }
            }})
        if physical_resource_id is not None:
            self['PhysicalResourceId'] = physical_resource_id


def test_create():
    # create a test user
    name = str(uuid.uuid4())
    event = Event('Create', name)
    response = cfn_dbuser_provider.create(event, {})
    assert response['Status'] == 'SUCCESS', response['Reason']
    assert 'PhysicalResourceId' in response
    physical_resource_id = response['PhysicalResourceId']

    assert 'Data' in response 

    # delete non existing user
    event = Event('Delete', name + "-", physical_resource_id)
    response = cfn_dbuser_provider.delete(event, {})
    assert response['Status'] == 'SUCCESS', response['Reason']

    # delete the created user
    event = Event('Delete', name, physical_resource_id)
    response = cfn_dbuser_provider.delete(event, {})
    assert response['Status'] == 'SUCCESS', response['Reason']
