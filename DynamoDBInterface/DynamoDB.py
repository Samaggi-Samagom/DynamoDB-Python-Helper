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
        if isinstance(item, str):
            return self._items[0][item]
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
        query = self.get(at_column, a_value, is_secondary_index, secondary_index_name, consistent_read)

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

    def update(self, where: str, equals: Any, data_to_update: Dict[str, Any]):
        if not data_to_update:
            return

        expression = "SET "
        expression_attr_val = {}
        expression_attr_name = {}

        for i, (key, data) in enumerate(data_to_update.items()):
            expression += f"#{string.ascii_letters[2*i]} = :{string.ascii_letters[2*i+1]}, "
            expression_attr_name["#" + string.ascii_letters[2*i]] = key
            expression_attr_val[":" + string.ascii_letters[2*i+1]] = data

        expression = expression[:-2]

        key = {where: equals}
        self._db.db_resource.Table(self._table_name).update_item(
            Key=key,
            UpdateExpression=expression,
            ExpressionAttributeValues=expression_attr_val,
            ExpressionAttributeNames=expression_attr_name,
        )

    def scan(self, consistent_read: bool = False):
        scan_result = []
        temp = None

        while temp is None or "LastEvaluatedKey" in temp:
            if temp is None or temp["LastEvaluatedKey"] is None:
                temp = self._db.db_resource.Table(self._table_name).scan(
                    ConsistentRead=consistent_read
                )
            else:
                temp = self._db.db_resource.Table(self._table_name).scan(
                    ExclusiveStartKey=temp["LastEvaluatedKey"] if temp is not None else None,
                    ConsistentRead=consistent_read
                )

            if "Items" in temp and len(temp["Items"]) >= 1:
                scan_result += temp["Items"]

        return scan_result


class KeyValueTable(Table):

    def __init__(self, db, table_name: str, key_col_name: str, val_col_name: str):
        super().__init__(db, table_name)
        self._key_col_name = key_col_name
        self._val_col_name = val_col_name

    def value(self, for_key: str):
        res = self.get(self._key_col_name, equals=for_key)

        if not res.exists():
            return None

        return res.first()[self._val_col_name]

    def set(self, for_key: str, new_value: Any):
        self.update(
            where=self._key_col_name, equals=for_key,
            data_to_update={
                self._val_col_name: new_value
            }
        )


class Database:

    def __init__(self, global_data_table_name="global-data-table", global_data_table_config: Dict[str, str] = None):
        self.db_resource = boto3.resource("dynamodb")
        self._global_data_table_name = global_data_table_name

        if global_data_table_config is None:
            global_data_table_config = {
                "key_column_name": "data-id",
                "value_column_name": "value"
            }

        self._global_data_config: Dict[str, str] = global_data_table_config

    def table(self, table_name) -> Table:
        return Table(self, table_name)

    def key_value_table(self, table_name, key_column_name="data-id", value_column_name="value"):
        return KeyValueTable(self, table_name, key_column_name, value_column_name)

    def globals(self):
        return self.key_value_table(
            self._global_data_table_name,
            self._global_data_config["key_column_name"],
            self._global_data_config["value_column_name"]
        )
