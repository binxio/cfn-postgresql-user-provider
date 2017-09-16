# Custom::PostgresDBUser
The `Custom::PostgresDBUser` resource creates 


## Syntax
To declare this entity in your AWS CloudFormation template, use the following syntax:

```json
{
  "Type" : "Custom::PostgresDBUser",
  "Properties" : {
  }
}
```

## Properties
You can specify the following properties:

- `Name`  - the name of the parameter in the Parameter Store (required)

## Return values
With 'Fn::GetAtt' the following values are available:

- `PostgresDBUser` - the generated secret value.
- `Arn` - the AWS Resource name of the parameter

For more information about using Fn::GetAtt, see [Fn::GetAtt](http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/intrinsic-function-reference-getatt.html).
