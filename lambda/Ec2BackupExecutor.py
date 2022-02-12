import json
import boto3
from datetime import datetime, timedelta
from boto3.dynamodb.conditions import Key
import dateutil.tz

def lambda_handler(event, context):
    timestamp = int(datetime.now().timestamp())
    dynamodb = boto3.resource("dynamodb")

    table = dynamodb.Table("BackupScheduler")
    
    ## EC2 SECTION ##
    response = table.query(
        KeyConditionExpression=Key("resourceType").eq("ec2ami")
    )
    result = response["Items"]
    ec2 = boto3.client("ec2")
    for res in result:
        localTime = dateutil.tz.gettz(res["timezone"])
        curLocalHour = datetime.now(tz=localTime).hour
        if(res["backupWindowStart"] <= curLocalHour and curLocalHour <= res["backupWindowEnd"]):
            if(res["nextExecution"] < timestamp or res["nextExecution"] == 0):
                custom_filter = [{"Name":"tag:BackupScheduler", "Values": [res["resourceTag"]]}]
                response = ec2.describe_instances(Filters=custom_filter)
                if(len(response["Reservations"]) < 1):
                    continue
                instances = response["Reservations"][0]["Instances"]
                for instance in instances:
                    name_format = instance["InstanceId"] + "_" + str(timestamp)
                    try:
                        retainMultiplier = (1 if res["retainUnit"] == "hours" else 24)
                        delete_by = int((datetime.now() + timedelta(hours=int(retainMultiplier * res["retainNumber"]))).timestamp())
                        ec2.create_image(
                            InstanceId=instance["InstanceId"], 
                            Name=name_format, 
                            Description=str(delete_by),
                            # DryRun=True,
                            NoReboot=(False if res["withReboot"] == "yes" else True),
                            TagSpecifications=[
                                {
                                    "ResourceType": "image",
                                    "Tags": [
                                        {
                                            "Key": "Name",
                                            "Value": "Backup_" + instance["InstanceId"]
                                        },
                                        {
                                            "Key": "BackupScheduler",
                                            "Value": res["resourceTag"]
                                        },
                                        {
                                            "Key": "BackupDeleteBy",
                                            "Value": str(delete_by)
                                        }
                                    ]
                                },
                                {
                                    "ResourceType": "snapshot",
                                    "Tags": [
                                        {
                                            "Key": "Name",
                                            "Value": "Backup_" + instance["InstanceId"]
                                        },
                                        {
                                            "Key": "BackupScheduler",
                                            "Value": res["resourceTag"]
                                        }
                                    ]
                                },
                            ]
                        )
                    except:
                        continue
                        ## NEED TO DO SOME ERROR LOG PROCESSING HERE
                    update_next_execution(table, res)
def update_next_execution(table, res):
    hourMultiplier = (1 if res["frequencyUnit"] == "hours" else 24)
    _ = table.update_item(
        Key={
            "resourceType": res["resourceType"],
            "resourceTag": res["resourceTag"]
        },
        UpdateExpression="set nextExecution=:ne",
        ExpressionAttributeValues={
            ":ne": int((datetime.now() + timedelta(hours=int(hourMultiplier * res["frequencyNumber"]-1), minutes=59)).timestamp())
        }
    )