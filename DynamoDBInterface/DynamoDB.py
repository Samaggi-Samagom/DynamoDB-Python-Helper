import string
from typing import Any, Dict
from boto3.dynamodb.conditions import Key
import boto3


class DatabaseQueryResult:

    def __init__(self, data):
        self._data = data
        self._items = data["Items"] if "Items" in data else None

    def exists(self):
        return self._items is not None and len(self._items) != 0

    def first(self):
        return self._items[0]

    def last(self):
        return self._items[-1]

    def __getitem__(self, item):
        return self._items[item]

    def length(self):
        return len(self._items)

    def __len__(self):
        return self.length()

    def is_unique(self):
        return self.length() == 1

    def value(self):
        return self.first()["value"]

    def all(self):
        return self._items if self._items is not None else []


class Table:
    def __init__(self, db, table_name: str):
        self._table_name = table_name
        self._db: Database = db

    def there_exists(self, a_value: Any, at_column: str, is_secondary_index: bool = False,
                     secondary_index_name: str = None, consistent_read: bool = False):
        query = self.get(a_value, at_column, is_secondary_index, secondary_index_name, consistent_read)

        return query.exists()

    def get(self, key: str, equals: Any, is_secondary_index: bool = False, secondary_index_name: str = None,
            consistent_read: bool = False) -> DatabaseQueryResult:
        if secondary_index_name is not None and not is_secondary_index:
            raise RuntimeError("Illegal argument, secondary index name provided unexpectedly.")
        if not is_secondary_index:
            query = self._db.db_resource.Table(self._table_name).query(
                KeyConditionExpression=Key(key).eq(equals),
                ConsistentRead=consistent_read,
            )
        else:
            index_name = secondary_index_name if secondary_index_name is not None else (key + "-index")
            query = self._db.db_resource.Table(self._table_name).query(
                IndexName=index_name,
                KeyConditionExpression=Key(key).eq(equals),
                ConsistentRead=consistent_read
            )

        return DatabaseQueryResult(query)

    def write(self, values: Dict[str, Any]):
        self._db.db_resource.Table(self._table_name).put_item(
            Item=values
        )

    def update(self, where: str, equals: Any, data_to_update: Dict[str, Any], is_secondary_index: bool = False,
               index_name: str = None):
        if not data_to_update:
            return

        expression = "SET "
        expression_attr_val = {}
        expression_attr_name = {}

        for i, (key, data) in enumerate(data_to_update.items()):
            expression += f":{string.ascii_letters[2*i]} = :{string.ascii_letters[2*i+1]}, "
            expression_attr_name[string.ascii_letters[2*i]] = key
            expression_attr_val[string.ascii_letters[2*i+1]] = data

        expression = expression[:-2]

        self._db.db_resource.Table(self._table_name).update_item(
            Key={where: equals},
            UpdateExpression=expression,
            ExpressionAttributeValues=expression_attr_val,
            ExpressionAttributeNames=expression_attr_name,
            IndexName=index_name if is_secondary_index else None
        )

    def scan(self, consistent_read: bool = False):
        scan_result = []
        temp = None

        while "LastEvaluatedKey" in temp or temp is None:
            temp = self._db.db_resource.Table(self._table_name).scan(
                ExclusiveStartKey=temp["LastEvaluatedKey"] if temp is not None else None,
                ConsistentRead=consistent_read
            )

            if "Items" in temp and len(temp["Items"]) >= 1:
                scan_result += temp["Items"]

        return scan_result


class Database:

    def __init__(self):
        self.db_resource = boto3.resource("dynamodb")

    def table(self, table_name) -> Table:
        return Table(self, table_name)
