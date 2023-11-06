import logging
import os
import uuid

import psycopg2

from postgresql import handler

logging.basicConfig(level=logging.INFO)


def test_create_extension():
    extension1 = "btree_gin"
    request = Request("Create", extension1)
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]

    # rename to extension2
    extension2 = "btree_gist"
    request = Request("Update", extension2, response["PhysicalResourceId"])
    request["OldResourceProperties"] = {"Extension": extension1}
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]

    request = Request("Delete", extension2, response["PhysicalResourceId"])
    request["ResourceProperties"]["DeletionPolicy"] = "Drop"
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]


def test_drop_extension():
    extension1 = "pgcrypto"
    request = Request("Create", extension1)
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]

    request = Request("Delete", extension1, response["PhysicalResourceId"])
    request["ResourceProperties"]["DeletionPolicy"] = "Drop"
    response = handler(request, {})
    assert response["Status"] == "SUCCESS", response["Reason"]


class Request(dict):
    def __init__(self, request_type, extension, physical_resource_id=None):
        self.update(
            {
                "RequestType": request_type,
                "ResponseURL": "https://httpbin.org/put",
                "StackId": "arn:aws:cloudformation:us-west-2:EXAMPLE/stack-name/guid",
                "RequestId": "request-%s" % str(uuid.uuid4()),
                "ResourceType": "Custom::PostgreSQLExtension",
                "LogicalResourceId": "Whatever",
                "ResourceProperties": {
                    "Extension": extension,
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
