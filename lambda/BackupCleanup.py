import json
import boto3
from datetime import datetime, timedelta
from boto3.dynamodb.conditions import Key
import dateutil.tz

def lambda_handler(event, context):
    timestamp = int(datetime.now().timestamp())
        
    ## EC2 AMI AND SNAPSHOT CLEANUP
    ec2 = boto3.client('ec2')
    amis = ec2.describe_images(Filters=[
        {
            'Name': 'tag-key',
            'Values': ['BackupDeleteBy']
        }
    ])

    for ami in amis["Images"]:
        try:
            delete_by = ami["Description"]
            if(timestamp > int(delete_by)):
                # Deregister AMI
                ec2.deregister_image(ImageId=ami["ImageId"])
                for snap in ami["BlockDeviceMappings"]:
                    # Delete snapshots
                    ec2.delete_snapshot(SnapshotId=snap["Ebs"]["SnapshotId"])
        except:
            print("ERROR DELETING AMIS AND SNAPSHOTS")
            
            
    ## RDS SECTION
    rds = boto3.client('rds')
    snapshots = rds.describe_db_snapshots(
        SnapshotType="manual"
    )
    for snapshot in snapshots["DBSnapshots"]:
        if(snapshot["DBSnapshotIdentifier"].startswith("backupscheduler")):
            try:
                delete_by = int(snapshot["DBSnapshotIdentifier"].split("-")[-1])
                if(timestamp > delete_by):
                    rds.delete_db_snapshot(DBSnapshotIdentifier=snapshot["DBSnapshotIdentifier"])
            except:
                continue