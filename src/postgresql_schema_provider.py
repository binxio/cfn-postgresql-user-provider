import logging

from postgresql_user_provider import PostgreSQLUser
from psycopg2.extensions import AsIs

log = logging.getLogger()

request_schema = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type": "object",
    "oneOf": [{"required": ["Database", "Schema", "Owner"]}],
    "properties": {
        "Database": {"$ref": "#/definitions/connection"},
        "Schema": {
            "type": "string",
            "pattern": "^[_A-Za-z][A-Za-z0-9_$]*$",
            "description": "to create",
        },
        "Owner": {
            "type": "string",
            "pattern": "^[_A-Za-z][A-Za-z0-9_$]*$",
            "description": "owner of the schema",
        },
        "DeletionPolicy": {
            "type": "string",
            "default": "Retain",
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


class PostgreSQLSchema(PostgreSQLUser):
    def __init__(self):
        super(PostgreSQLSchema, self).__init__()
        self.request_schema = request_schema

    def is_supported_resource_type(self):
        return self.resource_type == "Custom::PostgreSQLSchema"

    @property
    def schema(self):
        return self.get("Schema")

    @property
    def old_schema(self):
        return self.get_old("Schema", self.schema)

    @property
    def owner(self):
        return self.get("Owner")

    @property
    def old_owner(self):
        return self.get_old("Owner", self.owner)

    @property
    def deletion_policy(self):
        return self.get("DeletionPolicy")

    def create_schema(self):
        log.info("create schema %s ", self.schema)
        with self.connection.cursor() as cursor:
            if self.owner != self.dbowner:
                cursor.execute("GRANT %s to %s", [AsIs(self.owner), AsIs(self.dbowner)])
            cursor.execute(
                "CREATE SCHEMA %s AUTHORIZATION %s",
                [AsIs(self.schema), AsIs(self.owner)],
            )

    def drop_schema(self):
        if self.deletion_policy == "Drop":
            log.info("drop schema %s ", self.schema)
            with self.connection.cursor() as cursor:
                cursor.execute("DROP SCHEMA %s CASCADE", [AsIs(self.schema)])

    def update_schema(self):
        if self.owner != self.old_owner:
            log.info("alter schema %s owner to %s", self.old_schema, self.owner)
            with self.connection.cursor() as cursor:
                cursor.execute(
                    "ALTER SCHEMA %s OWNER TO %s",
                    [AsIs(self.old_schema), AsIs(self.owner)],
                )

        if self.schema != self.old_schema:
            log.info("alter schema %s rename to %s", self.old_schema, self.schema)
            with self.connection.cursor() as cursor:
                cursor.execute(
                    "ALTER SCHEMA %s RENAME TO %s",
                    [AsIs(self.old_schema), AsIs(self.schema)],
                )

    def create(self):
        try:
            self.connect()
            self.create_schema()
            self.physical_resource_id = self.logical_resource_id
        except Exception as e:
            self.physical_resource_id = "could-not-create"
            self.fail("Failed to create schema, %s" % e)
        finally:
            self.close()

    def update(self):
        try:
            self.connect()
            self.update_schema()
        except Exception as e:
            self.fail("Failed to update the schema, %s" % e)
        finally:
            self.close()

    def delete(self):
        if self.physical_resource_id == "could-not-create":
            self.success("schema was never created")
            return

        try:
            self.connect()
            self.drop_schema()
        except Exception as e:
            return self.fail("failed to drop schema %s", e)
        finally:
            self.close()


provider = PostgreSQLSchema()


def handler(request, context):
    return provider.handle(request, context)
