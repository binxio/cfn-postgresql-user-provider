# Custom::PostgresDBUser
The `Custom::PostgresDBUser` resource creates 


## Syntax
To declare this entity in your AWS CloudFormation template, use the following syntax:

```json
{
  "Type" : "Custom::PostgresDBUser",
  "Properties" : {
        "Name": String,
        "Password": String,
	"WithDatabase": Bool,
	"DeletionPolicy": STRING,

        "Database": {
		"Host": STRING,
		"Port": INTEGER,
		"Database": STRING,
		"User": STRING,
		"Password": STRING,
		"PasswordName": STRING
	}

        "ServiceToken": STRING
  }
}
```

## Properties
You can specify the following properties:

- `Name` - of the user to create
- `Password` - of the user
- `WithDatabase` - [true|false] if a database is to be created with the same name
- `DeletionPolicy` - [Retain|Drop] when the resource is deleted
- `Database` - connection information of the database owner
-- `Host` - the database server is listening on.
-- `Port` - port the database server is listening on.
-- `Database` - name to connect to.
-- `User` - name of the database owner.
-- `Password` - to identify the user with.
-- `PasswordName` - name of the parameter in the store containing the password of the user


## Return values
There are no return values from this resources.

