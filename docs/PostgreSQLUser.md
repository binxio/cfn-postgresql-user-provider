# Custom::PostgresDBUser
The `Custom::PostgresDBUser` resource creates a postgres database user with or without a database.


## Syntax
To declare this entity in your AWS CloudFormation template, use the following syntax:

```yaml
Type: Custom::PostgreSQLUser
Properties:
  Name: String
  Password: String
  PasswordParameterName: String
  WithDatabase: true/false
  DeletionPolicy: Retain/Drop
  Database:
    Host: STRING
    Port: INTEGER
    DBName: STRING
    DBNameParameterName: STRING
    User: STRING
    UserParameterName: STRING
    Password: STRING
    PasswordParameterName: STRING
  ServiceToken: !Sub 'arn:aws:lambda:${AWS::Region}:${AWS::AccountId}:function:binxio-cfn-dbuser-provider-vpc-${AppVPC}'
```

## Properties
You can specify the following properties:

- `Name` - of the user to create
- `Password` - of the user
- `PasswordParameterName` - name of the parameter in the store containing the password of the user
- `WithDatabase` - if a database is to be created with the same name, defaults to true
- `DeletionPolicy` - when the resource is deleted
- `Database` - connection information of the database owner
-- `Host` - the database server is listening on.
-- `Port` - port the database server is listening on.
-- `DBName` - name to connect to.
-- `DBNameParameterName` - name of the parameter in the store containing the database name to connect to.
-- `User` - name of the database owner.
-- `UserParameterName` - name of the parameter in the store containing the database owner.
-- `Password` - to identify the user with.
-- `PasswordParameterName` - name of the parameter in the store containing the password of the user

Either `DBName` or `DBNameParameterName`, `User` or `UserParameterName`, `Password` or `PasswordParameterName` is required.

## Return values
There are no return values from this resources.
