import os
import logging
import postgresql_schema_provider
import postgresql_user_provider


def handler(request, context):
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    if request['ResourceType'] == 'Custom::PostgreSQLSchema':
        return postgresql_schema_provider.handler(request, context)
    else:
        return postgresql_user_provider.handler(request, context)

