# cfn-database-user-provider
A CloudFormation custom resource provider for creating database schemas

One of the second biggest problem I encounter in creating immutable infrastructures, is creating database schemas. Database schemas and users are an essential part in bootstrapping an application landscape.

Although CloudFormation is very good in creating database servers, the mundane task of creating database schemas and users is left to nifty scripting, after the environment has been deployed leaving us with the problem of distributing credentials to the applications.  As we automated all the things, this is not a good thing.

Our [CloudFormation Secret Resource](https://github.com/binxio/cfn-custom-secret-provider), removed the problem of distributing secrets.  With this Custom CloudFormation Resource we put an end to that. Database schemas are defined as CloudFormation resources, just like their database servers.  

## How does it work?
It is quite easy: you specify a CloudFormation resource of the [Custom::PostgresDBUser](docs/Custom%3A%3APostgrsDBUser.md), as follows:

```json
  "Resources": {
    "KongUser": {
      "Type": "Custom::PostgresDBUser",
      "Properties": {

        "Name": "kong",
        "Password": { "Fn::GetAtt": [ "KongPassword", "Secret" ] },
	"CreateDatabase": True,

        "Database": {
		"Host": "postgres",
		"Port": 5432,
		"Database": "root",
		"User": "root",
		"Password": { "Fn::GetAtt": [ "DBPassword", "Secret" ]}
	}

        "ServiceToken": { "Fn::Join": [ ":", [ "arn:aws:lambda", { "Ref": "AWS::Region" }, { "Ref": "AWS::AccountId" }, "function:CFNCustomDBUserProvider" ] ]
        }
      }
    }
  }
```

After the deployment, the Postgres user 'kong' has been created together with a matching database 'kong'.



## Installation
To install this Custom Resource, type:

```sh
aws cloudformation create-stack \
	--capabilities CAPABILITY_IAM \
	--stack-name cfn-database-user-provider \
	--template-body file://cloudformation/cfn-custom-resource-provider.json 

aws cloudformation wait stack-create-complete  --stack-name cfn-database-user-provider 
```

This CloudFormation template will use our pre-packaged provider from `s3://binxio-public/lambdas/cfn-database-user-provider-latest.zip`.


## Demo
To install the simple sample of the Custom Resource, type:

```sh
aws cloudformation create-stack --stack-name cfn-database-user-provider-demo \
	--template-body file://cloudformation/demo-stack.json
aws cloudformation wait stack-create-complete  --stack-name cfn-database-user-provider-demo
```

## Conclusion
With this solution: 

- databases, schemas and users can be provisioned just like a database.
