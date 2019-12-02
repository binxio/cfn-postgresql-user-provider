import logging
import uuid

import psycopg2
import pytest
from psycopg2.extensions import AsIs

from postgresql import handler

logging.basicConfig(level=logging.INFO)


def test_grant_role(pg_users):
    user1, user2 = pg_users
    request = Request("Create", role=user1, grantee=user2)
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]
    assert response["PhysicalResourceId"] == f'grant:postgres:{user1}:{user2}'

    request = Request("Update", role=user1, grantee=user2, physical_resource_id=response["PhysicalResourceId"])
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]
    assert response["PhysicalResourceId"] == f'grant:postgres:{user1}:{user2}'

    request = Request("Delete", user1, user2, response["PhysicalResourceId"])
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]

@pytest.fixture
def pg_users():
    uid = str(uuid.uuid4()).replace("-", "")
    name = f'user_{uid}'
    name2 = f'user2_{uid}'
    r = Request('Create', name, name)
    with r.db_connection() as connection:
        with connection.cursor() as cursor:
            for n in [name, name2]:
                cursor.execute(
                    "CREATE ROLE %s LOGIN ENCRYPTED PASSWORD %s", [AsIs(n), n]
                )
        connection.commit()

        yield (name, name2)

        with connection.cursor() as cursor:
            for n in [name, name2]:
                cursor.execute("DROP ROLE %s", [AsIs(n)])
            connection.commit()




class Request(dict):
    def __init__(self, request_type, role, grantee, physical_resource_id=None):
        self.update(
            {
                "RequestType": request_type,
                "ResponseURL": "https://httpbin.org/put",
                "StackId": "arn:aws:cloudformation:us-west-2:EXAMPLE/stack-name/guid",
                "RequestId": "request-%s" % str(uuid.uuid4()),
                "ResourceType": "Custom::PostgreSQLRoleGrant",
                "LogicalResourceId": "Whatever",
                "ResourceProperties": {
                    "Role": role,
                    "Grantee": grantee,
                    "Database": {
                        "User": "postgres",
                        "Password": "password",
                        "Host": "localhost",
                        "Port": 5432,
                        "DBName": "postgres",
                    },
                },
            }
        )
        if physical_resource_id is not None:
            self["PhysicalResourceId"] = physical_resource_id

    def db_connection(self):
        p = self["ResourceProperties"]
        args = {
            "host": p["Database"]["Host"],
            "port": p["Database"]["Port"],
            "dbname": p["Database"]["DBName"],
            "user": p["Database"]["User"],
            "password": p["Database"]["Password"],
        }
        return psycopg2.connect(**args)
