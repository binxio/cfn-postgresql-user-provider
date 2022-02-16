import logging
import os

from postgresql_user_provider import PostgreSQLUser
from psycopg2.extensions import AsIs

log = logging.getLogger()

log.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

request_schema = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type": "object",
    "oneOf": [{"required": ["Database", "Extension"]}],
    "properties": {
        "Database": {"$ref": "#/definitions/connection"},
        "Extension": {
            "type": "string",
            "pattern": "^[A-Za-z0-9_]*$",
            "description": "postgres extension",
        },
        "DeletionPolicy": {
            "type": "string",
            "default": "Drop",
            "enum": ["Drop", "Retain"],
        },
    },
    "definitions": {
        "connection": {
            "type": "object",
            "oneOf": [
                {"required": ["DBName", "Host", "Port", "User", "Password"]},
                {
                    "required": [
                        "DBName",
                        "Host",
                        "Port",
                        "User",
                        "PasswordParameterName",
                    ]
                },
            ],
            "properties": {
                "DBName": {"type": "string", "description": "the name of the database"},
                "Host": {"type": "string", "description": "the host of the database"},
                "Port": {
                    "type": "integer",
                    "default": 5432,
                    "description": "the network port of the database",
                },
                "User": {
                    "type": "string",
                    "description": "the username of the database owner",
                },
                "Password": {
                    "type": "string",
                    "description": "the password of the database owner",
                },
                "PasswordParameterName": {
                    "type": "string",
                    "description": "the name of the database owner password in the Parameter Store.",
                },
            },
        }
    },
}


class PostgreSQLExtension(PostgreSQLUser):
    def __init__(self):
        super(PostgreSQLExtension, self).__init__()
        self.request_schema = request_schema

    def is_supported_resource_type(self):
        return self.resource_type == "Custom::PostgreSQLExtension"

    @property
    def database(self):
        return self.dbname

    @property
    def extension(self):
        return self.get("Extension")

    @property
    def old_extension(self):
        return self.get_old("Extension", self.extension)

    @property
    def extension(self):
        return self.get("Extension")

    @property
    def deletion_policy(self):
        return self.get("DeletionPolicy")

    def create_extension(self):
        log.info("creating extension %s for database %s ", self.extension, self.database)
        with self.connection.cursor() as cursor:
            cursor.execute("Create Extension if not exists %s", [AsIs(self.extension)])

    def update_extension(self):
        if self.extension != self.old_extension:
            log.info("removing old extension %s and implementing %s on database %s", self.old_extension, self.extension, self.database)
            log.info("drop extension %s ", self.extension)
            with self.connection.cursor() as cursor:
                cursor.execute("DROP EXTENSION IF EXISTS %s CASCADE", [AsIs(self.old_extension)])
            log.info("creating extension %s on database %s ", self.extension, self.database)
            with self.connection.cursor() as cursor:
                cursor.execute("Create Extension if not exists %s", [AsIs(self.extension)])

    def drop_extension(self):
        log.info("drop extension %s ", self.extension)
        with self.connection.cursor() as cursor:
            cursor.execute("DROP EXTENSION IF EXISTS %s CASCADE", [AsIs(self.extension)])

    def create(self):
        try:
            self.connect()
            self.create_extension()
            self.physical_resource_id = self.logical_resource_id
        except Exception as e:
            self.physical_resource_id = "could-not-create"
            self.fail("Failed to create extension, %s" % e)
        finally:
            self.close()

    def update(self):
        try:
            self.connect()
            self.update_extension()
        except Exception as e:
            self.fail("Failed to update the extension, %s" % e)
        finally:
            self.close()

    def delete(self):
        if self.physical_resource_id == "could-not-create" or self.deletion_policy == "Retain":
            self.success("extension was never created")
            return

        try:
            self.connect()
            self.drop_extension()
        except Exception as e:
            return self.fail("Failed to drop extension %s" % e)
        finally:
            self.close()


provider = PostgreSQLExtension()


def handler(request, context):
    return provider.handle(request, context)
