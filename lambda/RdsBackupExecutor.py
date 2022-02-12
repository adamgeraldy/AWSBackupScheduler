import json
import boto3
from datetime import datetime, timedelta
from boto3.dynamodb.conditions import Key
import dateutil.tz

def lambda_handler(event, context):
    timestamp = int(datetime.now().timestamp())
    dynamodb = boto3.resource("dynamodb")
    
    table = dynamodb.Table("BackupScheduler")

    ## RDS SECTION ##
    rds = boto3.client("rds")
    db_instances = rds.describe_db_instances()
    for instance in db_instances["DBInstances"]:
        for tag in instance["TagList"]:
            if(tag["Key"] == "BackupScheduler"):
                response = table.query(
                    KeyConditionExpression=
                        Key('resourceType').eq("rds") & Key('resourceTag').eq(tag["Value"])
                )
                if(len(response["Items"]) > 0):
                    res = response["Items"][0]
                    localTime = dateutil.tz.gettz(res["timezone"])
                    curLocalHour = datetime.now(tz=localTime).hour
                    if(res["backupWindowStart"] <= curLocalHour and curLocalHour <= res["backupWindowEnd"]):
                        if(res["nextExecution"] < timestamp or res["nextExecution"] == 0):
                            retainMultiplier = (1 if res["retainUnit"] == "hours" else 24)
                            delete_by = int((datetime.now() + timedelta(hours=int(retainMultiplier * res["retainNumber"]))).timestamp())
                            name_format = "backupscheduler-" + instance["DBInstanceIdentifier"] + "-" + str(delete_by)
                            try:
                                rds.create_db_snapshot(
                                    DBSnapshotIdentifier=name_format,
                                    DBInstanceIdentifier=instance["DBInstanceIdentifier"],
                                    Tags=[
                                        {
                                            "Key": "BackupScheduler",
                                            "Value": res["resourceTag"]
                                        },
                                        {
                                            "Key": "BackupDeleteBy",
                                            "Value": str(delete_by)
                                        },
                                        {
                                            "Key": "BackupTime",
                                            "Value": str(timestamp)
                                        }
                                    ]
                                )
                            except:
                                continue
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