# Custom::PostgreSQLExtension
The `Custom::PostgresSQLExtension` resource creates a postgres Extension in the mentioned database.


## Syntax
To declare this entity in your AWS CloudFormation template, use the following syntax:

```yaml
Type: Custom::PostgreSQLExtension
Properties:
  Extension: STRING
  DeletionPolicy: STRING
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

- `Extension` - the name of a valid postgresql database extensions
- `DeletionPolicy` - when the resource is deleted. Default: `Drop`
- `Database` - connection information of the database owner
  - `Host` - the database server is listening on.
  - `Port` - port the database server is listening on.
  - `Database` - name of the database to connect to.
  - `User` - name of the database owner.
  - `Password` - to identify the user with. 
  - `PasswordParameterName` - name of the parameter in the store containing the password of the user

Either `Password` or `PasswordParameterName` is required.

## Return values
There are no return values from this resources.

