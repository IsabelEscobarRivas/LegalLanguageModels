# test_s3.py
import logging
import boto3
from botocore.exceptions import ClientError
import os

def upload_file(file_name, bucket, object_name=None):
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    # If S3 object_name not specified, use file_name
    if object_name is None:
        object_name = os.path.basename(file_name)

    # Create S3 client with credentials
    s3_client = boto3.client(
        's3',
        region_name='us-east-2',
        aws_access_key_id='AKIAZQ3DPFQNUUTQS25I',
        aws_secret_access_key='DM7YmMG4ZGEaxrjq9tgdFr90XLq4Mj6Vly0l0b0p0'
    )

    try:
        response = s3_client.upload_file(file_name, bucket, object_name)
        logging.info(f"Upload Successful: {file_name} to {bucket}/{object_name}")
        return True
    except ClientError as e:
        logging.error(e)
        return False

# Create test file
with open('6.21V2 Final Pl - Mr. Camila Da Silva Rosa (TABS) Cl_RevInc.pdf', 'w') as f:
    f.write('test content')

# Try upload
success = upload_file('6.21V2 Final Pl - Mr. Camila Da Silva Rosa (TABS) Cl_RevInc.pdf', 'xploreimmigration')
if success:
    print("Upload completed successfully")
else:
    print("Upload failed")