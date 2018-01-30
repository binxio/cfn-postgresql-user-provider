# Custom::PostgresDBUser
The `Custom::PostgresDBUser` resource creates a postgres database user with or without a database.


## Syntax
To declare this entity in your AWS CloudFormation template, use the following syntax:

```json
{
  "Type" : "Custom::PostgresDBUser",
  "Properties" : {
        "Name": String,
        "Password": String,
        "PasswordParameterName": String,
    	"WithDatabase": Bool,
    	"DeletionPolicy": STRING,

        "Database": {
            "Host": STRING,
            "Port": INTEGER,
            "Database": STRING,
            "User": STRING,
            "Password": STRING,
            "PasswordParameterName": STRING
        }

        "ServiceToken": STRING
  }
}
```

## Properties
You can specify the following properties:

- `Name` - of the user to create
- `Password` - of the user 
- `PasswordParameterName` - name of the parameter in the store containing the password of the user
- `WithDatabase` - [true|false] if a database is to be created with the same name
- `DeletionPolicy` - [Retain|Drop] when the resource is deleted
- `Database` - connection information of the database owner
-- `Host` - the database server is listening on.
-- `Port` - port the database server is listening on.
-- `Database` - name to connect to.
-- `User` - name of the database owner.
-- `Password` - to identify the user with. 
-- `PasswordParameterName` - name of the parameter in the store containing the password of the user

Either `Password` or `PasswordParameterName` is required.

## Return values
There are no return values from this resources.

