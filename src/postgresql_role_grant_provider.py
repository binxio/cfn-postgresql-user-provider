import logging

from postgresql_user_provider import PostgreSQLUser
from psycopg2.extensions import AsIs

log = logging.getLogger()

request_schema = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type": "object",
    "oneOf": [{"required": ["Database", "Grantee", "Role"]}],
    "properties": {
        "Database": {"$ref": "#/definitions/connection"},
        "Grantee": {
            "type": "string",
            "pattern": "^[_A-Za-z][A-Za-z0-9_$]*$",
            "description": "to grant role to",
        },
        "Role": {
            "type": "string",
            "pattern": "^[_A-Za-z][A-Za-z0-9_$]*$",
            "description": "to grant",
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


class PostgreSQLRoleGrant(PostgreSQLUser):
    def __init__(self):
        super(PostgreSQLRoleGrant, self).__init__()
        self.request_schema = request_schema

    def is_supported_resource_type(self):
        return self.resource_type == "Custom::PostgreSQLRoleGrant"

    @property
    def grantee(self):
        return self.get("Grantee")

    @property
    def role(self):
        return self.get("Role")

    def grant_role(self):
        log.info("grant role %s to %s", self.role, self.grantee)
        with self.connection.cursor() as cursor:
            cursor.execute("GRANT %s to %s", [AsIs(self.role), AsIs(self.grantee)])
        self.physical_resource_id = f"grant:{self.dbname}:{self.role}:{self.grantee}"

    def revoke_role(self):
        log.info("revoke role %s from %s", self.role, self.grantee)
        with self.connection.cursor() as cursor:
            cursor.execute("REVOKE %s FROM %s", [AsIs(self.role), AsIs(self.grantee)])

    def create(self):
        try:
            self.connect()
            self.grant_role()
        except Exception as e:
            self.physical_resource_id = "could-not-create"
            self.fail("Failed to grant role, %s" % e)
        finally:
            self.close()

    def update(self):
        try:
            self.connect()
            self.grant_role()
        except Exception as e:
            self.fail("Failed to grant role, %s" % e)
        finally:
            self.close()

    def delete(self):
        if self.physical_resource_id == "could-not-create" or self.deletion_policy == "retain":
            self.success("role was never granted")
            return

        try:
            self.connect()
            self.revoke_role()
        except Exception as e:
            return self.fail("failed to revoke role %s", e)
        finally:
            self.close()


provider = PostgreSQLRoleGrant()


def handler(request, context):
    return provider.handle(request, context)
