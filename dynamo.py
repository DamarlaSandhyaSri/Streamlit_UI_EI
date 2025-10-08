import boto3
from botocore.exceptions import ClientError
from botocore.config import Config
from typing import Dict, List, Optional, Any
from settings import AWS_REGION, DYNAMO_TABLE
from logger import get_logger
from boto3.dynamodb.conditions import Attr, Key
from datetime import datetime


def dynamo_format(value):
    if isinstance(value, str):
        return {"S": value}
    elif isinstance(value, (int, float)):
        return {"N": str(value)}
    elif isinstance(value, dict):
        return {"M": {k: dynamo_format(v) for k, v in value.items()}}
    elif isinstance(value, list):
        return {"L": [dynamo_format(v) for v in value]}
    elif isinstance(value, bool):
        return {"BOOL": value}
    elif value is None:
        return {"NULL": True}
    elif isinstance(value, datetime):
        return {"S": value.isoformat()}
    else:
        return {"S": str(value)}


logger = get_logger(__name__)

DYNAMODB_SERVICE = "dynamodb"
AWS_PROFILE = "Comm-Prop-Sandbox"

class DynamoDBClient:
    """
    A client class for interacting with AWS DynamoDB service.
    Handles AWS credentials and client configuration.
    """

    def __init__(self, profile_name: str = AWS_PROFILE, region: str = AWS_REGION, table_name: str = DYNAMO_TABLE):
        self.profile_name = profile_name
        self.region = region
        self.table_name = table_name
        self.config = Config(read_timeout=1000)
        
        try:
            self.credentials = self._get_frozen_credentials()
            self.client = self.get_client()
            # Initialize both client and resource for different operations
            self.resource = self._get_resource()
            self.table = self.resource.Table(table_name)
            logger.info(f"DynamoDB client initialized for table: {table_name}")
        except Exception as e:
            logger.error(f"Failed to initialize DynamoDB client: {e}")
            raise

    def _get_frozen_credentials(self):
        """Create AWS session and freeze credentials."""
        # session = boto3.Session(profile_name=self.profile_name)
        session = boto3.Session()
        credentials = session.get_credentials()
        return credentials.get_frozen_credentials()

    def get_client(self):
        """Create and return a configured boto3 DynamoDB client."""
        return boto3.client(
            DYNAMODB_SERVICE,
            region_name=self.region,
            config=self.config,
            aws_access_key_id=self.credentials.access_key,
            aws_secret_access_key=self.credentials.secret_key,
            aws_session_token=self.credentials.token,
        )

    def _get_resource(self):
        """Create and return a configured boto3 DynamoDB resource."""
        return boto3.resource(
            DYNAMODB_SERVICE,
            region_name=self.region,
            config=self.config,
            aws_access_key_id=self.credentials.access_key,
            aws_secret_access_key=self.credentials.secret_key,
            aws_session_token=self.credentials.token,
        )

    def upsert_item(self, item: Dict) -> bool:
        """Insert or update an item in the DynamoDB table using resource."""
        try:
            # Clean None values from item
            cleaned_item = {k: v for k, v in item.items() if v is not None}
            
            self.table.put_item(Item=cleaned_item)
            logger.debug(f"Upserted item for {item.get('URL')}")
            return True
        except ClientError as e:
            logger.exception("Failed to upsert item to DynamoDB", exc_info=e)
            return False
        

    def update_record_by_url(self, url: str, updates: Dict[str, Any]) -> bool:
        """
        Update specific fields for a record where URL matches the given URL.
        Uses URL as partition key and finds the correct DateTime sort key.
        """
        try:
            if not url:
                logger.error("URL is required for updating record")
                return False
                
            # Filter out None values from updates
            filtered_updates = {k: v for k, v in updates.items() if v is not None}
            
            if not filtered_updates:
                logger.warning(f"No valid updates provided for URL: {url}")
                return False

            # First, find the existing record to get the DateTime sort key
            try:
                # Query by partition key (URL) to get all items with this URL
                response = self.table.query(
                    KeyConditionExpression=Key('URL').eq(url)
                )
                
                if not response.get('Items'):
                    logger.error(f"No item found with URL: {url}")
                    return False
                
                # Get the most recent record (assuming you want to update the latest)
                # If there are multiple records with the same URL, this gets the first one
                existing_item = response['Items'][0]
                existing_datetime = existing_item.get('DateTime')
                
                if not existing_datetime:
                    logger.error(f"No DateTime found in existing record for URL: {url}")
                    return False
                
                logger.debug(f"Found existing record with DateTime: {existing_datetime}")
                
                # Build the update expression
                update_expression = "SET " + ", ".join(f"#{k} = :{k}" for k in filtered_updates)
                expression_attribute_names = {f"#{k}": k for k in filtered_updates}
                expression_attribute_values = {f":{k}": v for k, v in filtered_updates.items()}

                # Perform the update using both URL and DateTime as the composite key
                self.table.update_item(
                    Key={
                        "URL": url,
                        "DateTime": existing_datetime
                    },
                    UpdateExpression=update_expression,
                    ExpressionAttributeNames=expression_attribute_names,
                    ExpressionAttributeValues=expression_attribute_values,
                )
                
                logger.info(f"Successfully updated record for URL: {url} with DateTime: {existing_datetime}")
                return True
                
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code')
                error_message = e.response.get('Error', {}).get('Message')
                logger.error(f"Failed to update record for URL {url}: {error_code} - {error_message}")
                
                # If query fails, fall back to scan method
                if error_code in ['ValidationException', 'ResourceNotFoundException']:
                    logger.warning("Query failed, trying scan method as fallback")
                    return self._update_by_scan_method(url, filtered_updates)
                
                return False
                
        except Exception as e:
            logger.error(f"❌ Dynamo update failed for {url}: {e}")
            return False

    def _update_by_scan_method(self, url: str, updates: dict) -> bool:
        """
        Fallback method: scan for the item when query fails.
        """
        try:
            # Scan to find the record with matching URL
            response = self.table.scan(
                FilterExpression=Attr('URL').eq(url),
                Limit=1
            )
            
            if not response.get('Items'):
                logger.error(f"No item found with URL: {url} using scan")
                return False
            
            existing_item = response['Items'][0]
            existing_datetime = existing_item.get('DateTime')
            
            if not existing_datetime:
                logger.error(f"No DateTime found in scanned record for URL: {url}")
                return False
            
            # Build the update expression
            update_expression = "SET " + ", ".join(f"#{k} = :{k}" for k in updates)
            expression_attribute_names = {f"#{k}": k for k in updates}
            expression_attribute_values = {f":{k}": v for k, v in updates.items()}

            # Update using the composite key
            self.table.update_item(
                Key={
                    "URL": url,
                    "DateTime": existing_datetime
                },
                UpdateExpression=update_expression,
                ExpressionAttributeNames=expression_attribute_names,
                ExpressionAttributeValues=expression_attribute_values,
            )
            
            logger.info(f"Successfully updated record using scan method for URL: {url}")
            return True
            
        except Exception as e:
            logger.error(f"Scan method update failed for URL {url}: {e}")
            return False
            
            
    def _update_by_scan_and_replace(self, url: str, updates: dict) -> bool:
        """
        Alternative update method: scan for the item and replace it entirely.
        Used when the primary key structure doesn't match expectations.
        """
        try:
            # Find the existing item by scanning
            response = self.table.scan(
                FilterExpression=Attr('URL').eq(url),
                Limit=1
            )
            
            if not response.get('Items'):
                logger.error(f"No item found with URL: {url}")
                return False
            
            existing_item = response['Items'][0]
            
            # Merge updates with existing item
            updated_item = existing_item.copy()
            for key, value in updates.items():
                if value is not None:
                    updated_item[key] = value
            
            # Replace the entire item
            self.table.put_item(Item=updated_item)
            
            logger.info(f"Successfully updated record using scan-and-replace for URL: {url}")
            logger.debug(f"Updated fields: {[k for k, v in updates.items() if v is not None]}")
            
            return True
            
        except Exception as e:
            logger.error(f"Scan-and-replace update failed for URL {url}: {e}")
            return False


    def retrieve_limited(self, limit: int = 5) -> Dict:
        """Retrieve a limited number of items from the table."""
        try:
            response = self.table.scan(Limit=limit)
            logger.debug(f"Retrieved {len(response.get('Items', []))} items with limit {limit}")
            return response
        except ClientError as e:
            logger.exception("Failed to retrieve items from DynamoDB", exc_info=e)
            return {"Items": [], "Count": 0}

    def retrieve_all_with_data(self) -> List[Dict]:
        """Retrieve all records where Data field is not null using scan operation."""
        try:
            response = self.table.scan(
                FilterExpression=Attr('Data').exists() & Attr('Data').ne('')
            )
            
            items = response['Items']
            
            # Handle pagination if there are more items
            while 'LastEvaluatedKey' in response:
                response = self.table.scan(
                    FilterExpression=Attr('Data').exists() & Attr('Data').ne(''),
                    ExclusiveStartKey=response['LastEvaluatedKey']
                )
                items.extend(response['Items'])
            
            logger.info(f"Retrieved {len(items)} records with non-null Data field")
            return items
        
        except ClientError as e:
            logger.exception("Failed to retrieve records with Data from DynamoDB", exc_info=e)
            return []

    def retrieve_untagged_records(self) -> List[Dict]:
        """Retrieve records that need tagging (Tag is null, empty, or 'Untagged')."""
        try:
            response = self.table.scan(
                FilterExpression=(
                    Attr('Data').exists() & 
                    Attr('Data').ne('') & 
                    (Attr('Tag').not_exists() | 
                     Attr('Tag').eq('') | 
                     Attr('Tag').eq('Untagged') |
                     Attr('Tag').is_in([None]))
                )
            )
            
            items = response['Items']
            
            # Handle pagination
            while 'LastEvaluatedKey' in response:
                response = self.table.scan(
                    FilterExpression=(
                        Attr('Data').exists() & 
                        Attr('Data').ne('') & 
                        (Attr('Tag').not_exists() | 
                         Attr('Tag').eq('') | 
                         Attr('Tag').eq('Untagged') |
                         Attr('Tag').is_in([None]))
                    ),
                    ExclusiveStartKey=response['LastEvaluatedKey']
                )
                items.extend(response['Items'])
            
            logger.info(f"Retrieved {len(items)} untagged records")
            return items
            
        except ClientError as e:
            logger.exception("Failed to retrieve untagged records from DynamoDB", exc_info=e)
            return []

    # def update_item_attributes(self, url: str, updates: Dict) -> bool:
    #     """Update specific attributes of an item identified by URL."""
    #     try:
    #         # Build update expression dynamically
    #         update_expression = "SET "
    #         expression_attribute_values = {}
    #         expression_attribute_names = {}
            
    #         for key, value in updates.items():
    #             if value is not None:
    #                 attr_name = f"#{key}"
    #                 attr_value = f":{key}"
    #                 update_expression += f"{attr_name} = {attr_value}, "
    #                 expression_attribute_names[attr_name] = key
    #                 expression_attribute_values[attr_value] = value
            
    #         # Remove trailing comma
    #         update_expression = update_expression.rstrip(", ")
            
    #         if not expression_attribute_values:
    #             logger.warning(f"No valid updates provided for URL: {url}")
    #             return False
            
    #         self.table.update_item(
    #             Key={'URL': url},
    #             UpdateExpression=update_expression,
    #             ExpressionAttributeNames=expression_attribute_names,
    #             ExpressionAttributeValues=expression_attribute_values
    #         )
            
    #         logger.debug(f"Updated attributes for URL: {url}")
    #         return True
            
    #     except ClientError as e:
    #         logger.exception(f"Failed to update item attributes for URL {url}", exc_info=e)
    #         return False


    # def update_specific_fields(self, url: str, updates: Dict) -> bool:
    #     """Update only specific fields for a record identified by URL."""
    #     try:
    #         if not url:
    #             logger.error("URL is required for updating specific fields")
    #             return False
                
    #         # Build update expression dynamically
    #         update_expression_parts = []
    #         expression_attribute_values = {}
    #         expression_attribute_names = {}
            
    #         for key, value in updates.items():
    #             if value is not None:
    #                 attr_name = f"#{key.replace('-', '_')}"  # Handle special characters
    #                 attr_value = f":{key.replace('-', '_')}"
    #                 update_expression_parts.append(f"{attr_name} = {attr_value}")
    #                 expression_attribute_names[attr_name] = key
    #                 expression_attribute_values[attr_value] = value
            
    #         if not update_expression_parts:
    #             logger.warning(f"No valid updates provided for URL: {url}")
    #             return False
            
    #         update_expression = "SET " + ", ".join(update_expression_parts)
            
    #         # Use update_item to update specific fields only
    #         response = self.table.update_item(
    #             Key={'URL': url},
    #             UpdateExpression=update_expression,
    #             ExpressionAttributeNames=expression_attribute_names,
    #             ExpressionAttributeValues=expression_attribute_values,
    #             ReturnValues="UPDATED_NEW"
    #         )
            
    #         logger.info(f"Successfully updated fields for URL: {url}")
    #         logger.debug(f"Updated attributes: {response.get('Attributes', {})}")
    #         return True
            
    #     except ClientError as e:
    #         logger.exception(f"Failed to update specific fields for URL {url}", exc_info=e)
    #         return False





























# import boto3
# from botocore.exceptions import ClientError
# from botocore.config import Config
# from typing import Dict, List, Optional, Any
# from src.settings import AWS_REGION, DYNAMO_TABLE
# from src.logger import get_logger
# from boto3.dynamodb.conditions import Attr, Key

# logger = get_logger(__name__)

# DYNAMODB_SERVICE = "dynamodb"
# AWS_PROFILE = "Comm-Prop-Sandbox"


# class DynamoDBClient:
#     """
#     A client class for interacting with AWS DynamoDB service.
#     Handles AWS credentials and client configuration.
#     """

#     def __init__(self, profile_name: str = AWS_PROFILE, region: str = AWS_REGION, table_name = DYNAMO_TABLE):
#         self.profile_name = profile_name
#         self.region = region
#         self.table_name = table_name
#         self.config = Config(read_timeout=1000)
#         self.credentials = self._get_frozen_credentials()
#         self.client = self.get_client()

#     def _get_frozen_credentials(self):
#         """
#         Create AWS session and freeze credentials.
#         """
#         session = boto3.Session(profile_name=self.profile_name)
#         credentials = session.get_credentials()
#         return credentials.get_frozen_credentials()

#     def get_client(self):
#         """
#         Create and return a configured boto3 DynamoDB client.
#         """
#         return boto3.client(
#             DYNAMODB_SERVICE,
#             region_name=self.region,
#             config=self.config,
#             aws_access_key_id=self.credentials.access_key,
#             aws_secret_access_key=self.credentials.secret_key,
#             aws_session_token=self.credentials.token,
#         )
    
#     def upsert_item(self, item: Dict) -> bool:
#         """
#         Insert or update an item in the DynamoDB table.
#         """
#         try:
#             self.client.put_item(TableName = DYNAMO_TABLE, Item=item)
#             logger.debug(f"Upserted item for {item.get('url')}")
#             return True
#         except ClientError as e:
#             logger.exception("Failed to upsert item to DynamoDB", exc_info=e)
#             return False
        
#     def retrieve_limited(self, limit: int = 5) -> Dict:
#         """
#         Retrieve a limited number of items from the table.
#         """
#         try:
#             response = self.client.scan(
#                 TableName=DYNAMO_TABLE,
#                 Limit=limit
#             )
#             logger.debug(f"Retrieved {len(response.get('Items', []))} items with limit {limit}")
#             return response
#         except ClientError as e:
#             logger.exception("Failed to retrieve items from DynamoDB", exc_info=e)
#             return {"Items": [], "Count": 0}

#     def retrieve_all_with_data(self) -> List[Dict]:
#         """
#         Retrieve all records where Data field is not null using scan operation.
#         """
#         try:
#             response = self.table.scan(
#                 FilterExpression=Attr('Data').exists() & Attr('Data').ne('')
#             )
            
#             items = response['Items']
            
#             # Handle pagination if there are more items
#             while 'LastEvaluatedKey' in response:
#                 response = self.table.scan(
#                     FilterExpression=Attr('Data').exists() & Attr('Data').ne(''),
#                     ExclusiveStartKey=response['LastEvaluatedKey']
#                 )
#                 items.extend(response['Items'])
            
#             logger.info(f"Retrieved {len(items)} records with non-null Data field")
#             return items
            
#         except ClientError as e:
#             logger.exception("Failed to retrieve records with Data from DynamoDB", exc_info=e)
#             return []
        