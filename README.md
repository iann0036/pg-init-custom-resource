# Postgres Database Initialization Custom Resource

This custom resource is built to initialize a Postgres database with the initial data structures and users it needs to operate correctly. It's designed to be flexible enough that you can add your own commands or any other properties needed.

## Installation

In order to compile the required libraries for the Lambda, you'll need a static build of the psycopg2 library. I recommend the [instructions from jkehler](https://github.com/jkehler/awslambda-psycopg2) in order to include the library. You'll also need to satisfy the other requirements in the `requirements.txt` file.

Alternatively, a precompiled zip can be found [here](http://kablamo-rds-custom-resource.s3-website-ap-southeast-2.amazonaws.com/app.zip).

## Usage

The custom resource will use the endpoint, username and password provided to execute your defined SQL statements on the databases, with the `postgres` database executions being prioritized above others. It will then create the database users with grants and will randomly generate credentials for that user, placing the credentials in AWS Secrets Manager.

Here's an example of the format that is expected:

```
  DatabaseInit: 
    Type: "Custom::DatabaseInit"
    Properties: 
      ServiceToken: !GetAtt DatabaseInitLambda.Arn
      StackName: !Ref "AWS::StackName"
      RdsProperties:
        EndpointAddress: !GetAtt DatabaseInstance.Endpoint.Address
        DBUsername: "databasemasterusername"
        DBPassword: "databasemasterpassword"
        Execute:
          - DatabaseName: "postgres"
            Scripts:
            - 'CREATE DATABASE "mydb";'
          - DatabaseName: "mydb"
            Scripts:
            - 'CREATE EXTENSION IF NOT EXISTS "uuid-ossp";'
        DatabaseUsers:
        - Name: mysuperuser
          SuperUser: true
          SecretId: "mysuperusercredential"
        - Name: myapp
          SecretId: "myappcredential"
          Grants:
          - Database: postgres
            Permissions: CONNECT
          - Database: mydb
            Permissions: ALL PRIVILEGES
```

I've included a sample CloudFormation template with a test database in the repo to help you get started. It will only deploy in the Sydney region unless you commit the Lambda package to your own bucket and modify the template accordingly. You'll also need to ensure that the Lambda is deployed into 2 or more subnets with access to a NAT gateway.

If you have any bugs / feature requests, feel free to raise an issue and pull requests are welcomed.
