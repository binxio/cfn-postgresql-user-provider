# Custom::PostgreSQLSchema
The `Custom::PostgreSQLSchema` resource creates a postgres schema and assigns an owner


## Syntax
To declare this entity in your AWS CloudFormation template, use the following syntax:

```yaml
Type: Custom::PostgreSQLSchema
Properties:
  Schema: String
  OWner: String
  DeletionPolicy: Retain/Drop
  Database:
    Host: STRING
    Port: INTEGER
    Database: STRING
    User: STRING
    Password: STRING
    PasswordParameterName: STRING
  ServiceToken: !Sub 'arn:aws:lambda:${AWS::Region}:${AWS::AccountId}:function:binxio-cfn-dbuser-provider-vpc-${AppVPC}'
```

## Properties
You can specify the following properties:

- `Schema` - to create
- `Owner` - of the schema
- `DeletionPolicy` - when the resource is deleted
- `Database` - connection information of the database owner
  - `Host` - the database server is listening on.
  - `Port` - port the database server is listening on.
  - `Database` - name to connect to.
  - `User` - name of the database owner.
  - `Password` - to identify the user with. 
  - `PasswordParameterName` - name of the parameter in the store containing the password of the user

Either `Password` or `PasswordParameterName` is required.

## Return values
There are no return values from this resources.

