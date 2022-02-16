import logging
import os
import uuid

import psycopg2
import pytest
from psycopg2.extensions import AsIs

from postgresql import handler

logging.basicConfig(level=logging.INFO)


def test_create_schema(pg_users):
    user1, user2 = pg_users
    schema1 = "schema_{}".format(str(uuid.uuid4()).replace("-", ""))
    request = Request("Create", schema1, user1)
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]

    # rename to schema2 and change owner to user2
    schema2 = schema1.replace("schema_", "schema2_")
    request = Request("Update", schema2, user2, response["PhysicalResourceId"])
    request["OldResourceProperties"] = {"Schema": schema1, "Owner": user1}
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]

    # change schema name back
    request = Request("Update", schema1, user2, response["PhysicalResourceId"])
    request["OldResourceProperties"] = {"Schema": schema2}
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]

    request = Request("Delete", schema1, user2, response["PhysicalResourceId"])
    request["ResourceProperties"]["DeletionPolicy"] = "Drop"
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]


def test_drop_schema(pg_users):
    user1, user2 = pg_users
    schema1 = "schema_{}".format(str(uuid.uuid4()).replace("-", ""))
    request = Request("Create", schema1, user1)
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]

    request = Request("Delete", schema1, user2, response["PhysicalResourceId"])
    request["ResourceProperties"]["DeletionPolicy"] = "Drop"
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
            # cursor.execute("DROP OWNED BY %s CASCADE", [AsIs(name)])
            for n in [name, name2]:
                cursor.execute("DROP ROLE %s", [AsIs(n)])
            connection.commit()


class Request(dict):
    def __init__(self, request_type, schema, owner, physical_resource_id=None):
        self.update(
            {
                "RequestType": request_type,
                "ResponseURL": "https://httpbin.org/put",
                "StackId": "arn:aws:cloudformation:us-west-2:EXAMPLE/stack-name/guid",
                "RequestId": "request-%s" % str(uuid.uuid4()),
                "ResourceType": "Custom::PostgreSQLSchema",
                "LogicalResourceId": "Whatever",
                "ResourceProperties": {
                    "Schema": schema,
                    "Owner": owner,
                    "Database": {
                        "User": "postgres",
                        "Password": "password",
                        "Host": os.getenv("DOCKER0", "localhost"),
                        "Port": os.getenv("DBPORT", 5432),
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
