# cfn-postgres-dbuser-provider

The second biggest problem I encounter in creating immutable infrastructures, is creating database schemas. Database schemas and users are an essential part in bootstrapping an application landscape.  Our [CloudFormation Secret Resource](https://github.com/binxio/cfn-custom-secret-provider), 
removed the problem of distributing secrets.  

Although CloudFormation is very good in creating database servers, the mundane task of creating database schemas and users is left to nifty scripting, 
after the environment has been deployed leaving us with the problem of distributing credentials to the applications. As we automated all the things, this is not a good thing. With this Custom CloudFormation Resource we put an end to that. Database schemas are defined as CloudFormation resources, just like their database servers.  


## How does it work?
It is quite easy: you specify a CloudFormation resource of the [Custom::PostgresDBUser](docs/PostgresDBUser.md), as follows:

```yaml
  KongUser:
    Type: Custom::PostgresDBUser
    Properties:
      Name: kong
      Password: !GetAtt 'KongPassword.Secret'
      WithDatabase: true
      DeletionPolicy: Retain
      Database:                   # the database to create the new database in
        Host: postgres
        Port: 5432
        Database: root
        User: root
        PasswordParameterName: /postgres/root/PGPASSWORD
      ServiceToken: !Sub 'arn:aws:lambda:${AWS::Region}:${AWS::AccountId}:function:binxiokong-io-cfn-dbuser-provider-vpc-${AppVPC}'

```

After the deployment, the Postgres user 'kong' has been created together with a matching database 'kong'. The password for the root database user has been obtained by querying the Parameter `/postgres/root/PGPASSWORD`. 
If you just want to create a user with which you can login to the PostgreSQL database server, without a database, specify `WithDatabase` as `false`. 

The RetainPolicy by default is `Retain`. This means that the login to the database is disabled. If you specify drop, it will be dropped and your data will be lost.

## Installation
To install this Custom Resource, type:

```sh
export VPC_ID=$(aws ec2  --output text --query 'Vpcs[?IsDefault].VpcId' describe-vpcs)
export SUBNET_ID=$(aws ec2 --output text --query Subnets[0].SubnetId \
			describe-subnets --filters Name=vpc-id,Values=$VPC_ID)
export SG_ID=$(aws ec2 --output text --query "SecurityGroups[*].GroupId" \
			describe-security-groups --group-names default  --filters Name=vpc-id,Values=$VPC_ID)

aws cloudformation create-stack \
	--capabilities CAPABILITY_IAM \
	--stack-name cfn-dbuser-provider \
	--parameters "ParameterKey=VPC,ParameterValue=$VPC_ID ParameterKey=Subnet,ParameterValue=$SUBNET_ID ParameterKey=SecurityGroup,ParameterValue=$SG_ID" \
	--template-body file://cloudformation/cfn-custom-resource-provider.json 

aws cloudformation wait stack-create-complete  --stack-name cfn-dbuser-provider 
```
Note that this uses the default VPC, subnet and security group. As the Lambda functions needs to connect to the database. You will need to 
install this lambda for each vpc that you want to be able to create database users.

This CloudFormation template will use our pre-packaged provider from `s3://binxio-public/lambdas/cfn-dbuser-provider-latest.zip`.


## Demo
To install the simple sample of the Custom Resource, type:

```sh
aws cloudformation create-stack --stack-name cfn-database-user-provider-demo \
	--template-body file://cloudformation/demo-stack.json
aws cloudformation wait stack-create-complete  --stack-name cfn-database-user-provider-demo
```
It will create a postgres database too, so it is quite time consuming...

## Conclusion
With this solution users and databases can be provisioned just like a database.
