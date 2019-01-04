import boto3
import os
import pprint
import json
import secrets
import string
import requests
import sys
import psycopg2
import urllib3
import traceback

def handler(event, context):
    responseBody = {
        'Status': 'SUCCESS',
        'Reason': '',
        'PhysicalResourceId': event.get('PhysicalResourceId',event['LogicalResourceId']),
        'StackId': event['StackId'],
        'RequestId': event['RequestId'],
        'LogicalResourceId': event['LogicalResourceId']
    }

    print("Default response, to be sent to %s :" % event['ResponseURL'])
    pprint.pprint(responseBody) # for debugging
    print("Default response set, initiated by the stack %s, starting..." % event['ResourceProperties']['StackName'])

    try:
        smclient = boto3.client('secretsmanager')
        alphabet = string.ascii_letters + string.digits

        master_credential = json.loads(smclient.get_secret_value(SecretId=event['ResourceProperties']['RdsProperties']['MasterSecretId'])['SecretString'])

        if 'RdsProperties' in event['ResourceProperties']:
            if 'Execute' in event['ResourceProperties']['RdsProperties'] and (event['RequestType'] == "Create" or event['RequestType'] == "Update"):
                for execute_item in event['ResourceProperties']['RdsProperties']['Execute']:
                    database_name = execute_item['DatabaseName']
                    if database_name == "postgres":
                        conn = psycopg2.connect("host=%s dbname=postgres user=%s password=%s connect_timeout=10 options='-c statement_timeout=5000'" % (event['ResourceProperties']['RdsProperties']['EndpointAddress'], master_credential['username'], master_credential['password']))
                        conn.autocommit = True
                        for execute_script in execute_item['Scripts']:
                            try:
                                cur = conn.cursor()
                                print("Executing SQL in database 'postgres': %s" % execute_script)
                                cur.execute(execute_script)

                                cur.close()
                            except:
                                traceback.print_exc()

                    conn.close()
                for execute_item in event['ResourceProperties']['RdsProperties']['Execute']:
                    database_name = execute_item['DatabaseName']
                    if database_name != "postgres":
                        conn = psycopg2.connect("host=%s dbname=%s user=%s password=%s connect_timeout=10 options='-c statement_timeout=5000'" % (event['ResourceProperties']['RdsProperties']['EndpointAddress'], database_name, master_credential['username'], master_credential['password']))
                        conn.autocommit = True
                        for execute_script in execute_item['Scripts']:
                            try:
                                cur = conn.cursor()
                                print("Executing SQL in database '%s': %s" % (database_name, execute_script))
                                cur.execute(execute_script)

                                cur.close()
                            except:
                                traceback.print_exc()

                        conn.close()
            
            print("Finished executes, adding users")

            if 'DatabaseUsers' in event['ResourceProperties']['RdsProperties'] and (event['RequestType'] == "Create" or event['RequestType'] == "Update"):
                conn = psycopg2.connect("host=%s dbname=postgres user=%s password=%s connect_timeout=10 options='-c statement_timeout=5000'" % (event['ResourceProperties']['RdsProperties']['EndpointAddress'], master_credential['username'], master_credential['password']))
                conn.autocommit = True
                for database_user in event['ResourceProperties']['RdsProperties']['DatabaseUsers']:
                    
                    credential = {
                        'username': database_user['Name'],
                        'password': ''.join(secrets.choice(alphabet) for i in range(24))
                    }

                    try:
                        secretstate = smclient.describe_secret(SecretId=database_user['SecretId'])

                        # Edge case - if the secret is to be restored from scheduled deletion, the below action will recover if available
                        try:
                            smclient.restore_secret(SecretId=database_user['SecretId'])
                        except:
                            pass
                        
                        credential = json.loads(smclient.get_secret_value(SecretId=database_user['SecretId'])['SecretString'])
                    except:
                        response = smclient.create_secret(
                            Name=database_user['SecretId'],
                            ClientRequestToken=''.join(secrets.choice(alphabet) for i in range(32)),
                            Description="Generated secret for RDS",
                            SecretString=json.dumps(credential)
                        )
                    
                    cur = conn.cursor()
                    
                    try:
                        print("Executing SQL: CREATE USER \"%s\" WITH PASSWORD '<snipped>';" % (database_user['Name']))
                        cur.execute("CREATE USER \"%s\" WITH PASSWORD '%s';" % (database_user['Name'], credential['password']))
                    except:
                        traceback.print_exc()

                    try:
                        if 'Grants' in database_user:
                            for grant in database_user['Grants']:
                                print("Executing SQL: GRANT %s ON DATABASE \"%s\" TO \"%s\";" % (grant['Permissions'], grant['Database'], database_user['Name']))
                                cur.execute("GRANT %s ON DATABASE \"%s\" TO \"%s\";" % (grant['Permissions'], grant['Database'], database_user['Name']))
                    except:
                        traceback.print_exc()
                    
                    try:
                        if 'SuperUser' in database_user and database_user['SuperUser']:
                            print("Executing SQL: GRANT rds_superuser TO \"%s\";" % (database_user['Name']))
                            cur.execute("GRANT rds_superuser TO \"%s\";" % (database_user['Name']))
                    except:
                        traceback.print_exc()
                    
                    cur.close()
                conn.close()
            
            print("Finished DB users")
            
    except:
        traceback.print_exc()
        responseBody = {
            'Status': 'FAILED',
            'Reason': '',
            'PhysicalResourceId': event.get('PhysicalResourceId',event['LogicalResourceId']),
            'StackId': event['StackId'],
            'RequestId': event['RequestId'],
            'LogicalResourceId': event['LogicalResourceId']
        }
    
    print("About to put")
    requests.put(event['ResponseURL'], data=json.dumps(responseBody))
    print('Response = ' + json.dumps(responseBody))

    return True