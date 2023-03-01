from __future__ import annotations

import copy
import enum
import string
import warnings
import csv
import boto3

from boto3.dynamodb.conditions import Key
from typing import List, Dict, Any, Callable, Set
from functools import partial as p
from decimal import Decimal


class FilterType(enum.Enum):
    EQUALS = p(lambda x, y: x == y)
    EQUALS_NON_CS = p(lambda x, y: x.lower() == y.lower())
    NOT_EQUAL = p(lambda x, y: x != y)
    CONTAINS = p(lambda x, y: y in x)
    NOT_CONTAIN = p(lambda x, y: y not in x)
    GREATER_THAN = p(lambda x, y: x > y)
    GREATER_THAN_EQUAL = p(lambda x, y: x >= y)
    LESS_THAN = p(lambda x, y: x < y)
    LESS_THAN_EQUAL = p(lambda x, y: x <= y)
    IN = p(lambda x, y: x in y)
    NOT_IN = p(lambda x, y: x not in y)


class Filter:

    def __init__(self, column: str, value: str, filter_type: FilterType, includes_empty: bool = False):
        self.val = value
        self.col = column
        self.filter_type = filter_type
        self.includes_empty = includes_empty

    def apply(self, data: List[Dict[str, Any]]):
        if self.includes_empty:
            return [d for d in data if self.col not in d or self.filter_type.value(d[self.col], self.val)]
        else:
            return [d for d in data if self.col in d and self.filter_type.value(d[self.col], self.val)]

    def __str__(self):
        return f"FILTER: On \"{self.col}\" of type \"{self.filter_type.name}\" for condition \"{self.val}\""


class DatabaseQueryResult:

    def __init__(self, data, source_table):
        self._data = copy.deepcopy(data)
        self._items = data["Items"] if "Items" in data else None
        self._table: Table = source_table
        self.__i = 0
        self.__i_mode = "NONE"

    def exists(self) -> bool:
        return self._items is not None and len(self._items) != 0

    def dump(self):
        return self._data

    def first(self) -> Dict[str, Any]:
        return self._items[0] if len(self._items) > 0 else {}

    def last(self) -> Dict[str, Any]:
        return self._items[-1]

    def unique(self, key: str, ignores_empty: bool = True) -> Set[Any]:
        return set([x[key] if key in x else None for x in self._items if key in x and ignores_empty])

    def strip(self, keys:List[str] = None, key:str = None) -> DatabaseQueryResult:
        if keys is None and key is None:
            raise KeyError("Strip must receive either `keys` or `key` to strip")

        data = copy.deepcopy(self.all())
        for elem in data:
            for x in (keys if keys is not None else [key]):
                if x in elem:
                    del elem[x]

        return DatabaseQueryResult({"Items": data}, self._table)

    def select_columns(self, columns:List[str]) -> DatabaseQueryResult:
        data = copy.deepcopy(self.all())
        for elem in data:
            for x in self.columns():
                if x in elem and x not in columns:
                    del elem[x]

        return DatabaseQueryResult({"Items": data}, self._table)

    def apply(self, function: Callable[[Any], Any], *args, new_col: str = None) -> DatabaseQueryResult:
        if len(args) == 0:
            raise RuntimeError("Must provide a column to apply function to.")
        if new_col is None:
            if len(args) > 1:
                warnings.warn("Calling `.apply()` with multiple columns but `new_col` not provided. Data will "
                              "overwrite the first column provided.")
            new_col = args[0]

        param_error = False

        data = copy.deepcopy(self.all())
        for elem in data:
            args_data = [elem[col] for col in args if col in elem]
            if len(args_data) == len(args):
                elem[new_col] = function(*args_data)
            else:
                param_error = True

        if param_error:
            warnings.warn("Function was not applied on some row as value required does not exist for all column(s)")

        return DatabaseQueryResult({"Items": data}, self._table)

    def count_occurrence(self, key: str) -> Dict[Any, int]:
        count = {}
        for item in self._items:
            if item[key] not in count:
                count[item[key]] = 1
            else:
                count[item[key]] += 1
        return count

    def num_unique(self, key: str, ignores_empty: bool = True) -> int:
        return len(self.unique(key, ignores_empty))

    def column(self, key: str, includes_empty: bool = False, replace_empty: Any = None) -> List[Any]:
        if replace_empty is not None and not includes_empty:
            raise KeyError("Value for `replace_empty` provided but `includes_empty` is False")
        return [v[key] if key in v else replace_empty for v in self._items if key in v or includes_empty]

    def columns(self) -> Set[str]:
        columns = []
        for row in self.all():
            columns += row.keys()
        return set(columns)

    def count_empty(self, key: str) -> int:
        return len([True for x in self._items if key not in x])

    def join(self, _with: DatabaseQueryResult, using: str) -> DatabaseQueryResult:
        if using not in self.columns():
            return self

        if _with.num_unique(using) + _with.count_empty(using) != _with.length():
            warnings.warn(f"WARNING: Completing JOIN using non-unique key on right.\nJOIN requested on {_with._table.name()} using {using}")

        new_items = copy.deepcopy(self._items)

        for item in new_items:
            if using in item:
                item.update(_with.get_where(using, item[using]))

        return DatabaseQueryResult({"Items": new_items}, self._table)

    def get(self, value: str) -> Dict[str, Any]:
        return self.get_where(self._table.hash_key(), value)

    def get_where(self, key: str, value: str) -> Dict[str, Any]:
        return self.filter(key, value, FilterType.EQUALS).first()

    def __getitem__(self, item):
        if isinstance(item, str):
            if self.length() == 1:
                return self._items[0][item]
            elif self.length() != 0:
                raise TypeError("Cannot call __get_item__() with string parameters as query returns more than one "
                                "result.")
            else:
                raise IndexError("Cannot call __get_item__() as query returned no result.")
        return self._items[item]

    def __setitem__(self, key, value) -> None:
        if isinstance(key, str):
            if self.length() == 1:
                self._items[0][key] = value
            elif self.length() != 0:
                raise TypeError("Cannot call __setitem__() with string parameters as query returns more than one "
                                "result.")
            else:
                raise IndexError("Cannot call __setitem__() as query returned no result.")

    def length(self) -> int:
        return len(self._items)

    def __len__(self) -> int:
        return self.length()

    def is_unique(self) -> bool:
        return self.length() == 1

    def value(self) -> Any:
        return self.first()["value"]

    def all(self) -> List[Dict[str, Any]]:
        return self._items if self._items is not None else []

    def filter(self, column: str, value: Any, filter_type: FilterType = FilterType.EQUALS,
               includes_empty: bool = False) -> FilteredResponse:
        return self.filter_using(Filter(column, value, filter_type, includes_empty))

    def filter_using(self, f: Filter) -> FilteredResponse:
        return FilteredResponse(self, f)

    def fill_empty(self, with_data: Any = None) -> DatabaseQueryResult:
        new_data = []
        for data in self.all():
            new_row = {}
            for key in self.columns():
                new_row[key] = data[key] if key in data else with_data
            new_data.append(new_row)
        return DatabaseQueryResult({"Items": new_data}, self._table)

    def sort(self, using: str | List[str]) -> DatabaseQueryResult:
        data = copy.deepcopy(self._data)
        if type(using) == str:
            new_data = sorted(data, key=lambda x: x[using])
        elif type(using) == list:
            new_data = sorted(data, key=lambda x: tuple([x[k] for k in using]))
        else:
            raise RuntimeError("Invalid Sort Key")

        return DatabaseQueryResult({"Items": new_data}, self._table)

    def to_csv(self, file_name: str, col_order_left: List[str] = None, col_order_right: List[str] = None) -> None:
        if col_order_left is None:
            col_order_left = []
        if col_order_right is None:
            col_order_right = []

        col_order_right = list(set(col_order_right) - set(col_order_left))
        norm_col = sorted(list(set(self.columns()) - set(col_order_right) - set(col_order_left)))
        columns = col_order_left + norm_col + col_order_right

        with open(file_name, "w") as f:
            writer = csv.DictWriter(f, columns)
            writer.writeheader()
            writer.writerows(self.fill_empty().all())

    def __next__(self):
        if self.__i_mode == "DICT":
            if self.__i >= len(self.first()) - 1:
                raise StopIteration
            self.__i += 1
            key = list(self._items[0].keys())[self.__i]
            value = self._items[0][key]
            return key, value
        else:
            if self.__i >= self.length() - 1:
                raise StopIteration
            self.__i += 1
            return self[self.__i]

    def __iter__(self):
        self.__i = -1

        if self.length() == 1:
            self.__i_mode = "DICT"
        else:
            self.__i_mode = "LIST"

        return self

    def __contains__(self, item):
        if self.length() == 0:
            raise IndexError("Cannot call __contains__() as query returned no result.")
        if isinstance(item, dict) and self.length() > 1:
            return item in self._items
        if self.length() == 1:
            return item in self._items[0]
        elif self.length() > 1:
            raise TypeError("Cannot call __contains__() when query returns more than one result.")


class FilteredResponse(DatabaseQueryResult):

    def __init__(self, original_query_response: DatabaseQueryResult, current_filter: Filter, filter_stack: list = None,
                 last_filtered: DatabaseQueryResult = None):
        if filter_stack is None:
            filter_stack = []

        self._filter_stack = filter_stack + [current_filter]
        self._original_data = original_query_response

        if last_filtered is not None:
            data = copy.deepcopy(last_filtered.dump())
            if "Items" not in data:
                super().__init__(data, original_query_response._table)
                return
            data["Items"] = current_filter.apply(data["Items"])
            super().__init__(data, original_query_response._table)
        else:
            data = copy.deepcopy(original_query_response.dump())
            if "Items" not in data:
                super().__init__(data, original_query_response._table)
                return
            for f in self._filter_stack:
                data["Items"] = f.apply(data["Items"])
            super().__init__(data, original_query_response._table)

    def filter_stack(self) -> List[str]:
        return [str(f) for f in self._filter_stack]

    def filter_using(self, f: Filter) -> FilteredResponse:
        return FilteredResponse(self._original_data, f, self._filter_stack, self)


class Table:
    def __init__(self, db, table_name: str):
        self._table_name = table_name
        self._db: Database = db

    def name(self) -> str:
        return self._table_name

    def hash_key(self) -> str:
        return self._db.db_resource.Table(self._table_name).key_schema[0]["AttributeName"]

    def gsi(self) -> Dict[str, str]:
        gsi_map = {}
        for x in self._db.db_resource.Table(self._table_name).global_secondary_indexes:
            gsi_map[x["KeySchema"][0]["AttributeName"]] = x["IndexName"]
        return gsi_map

    def there_exists(self, a_value: Any, at_column: str = None, consistent_read: bool = False) -> bool:
        if at_column is None:
            at_column = self.hash_key()
        query = self.get(key=at_column, equals=a_value, consistent_read=consistent_read)

        return query.exists()

    def get(self, key: str = None, equals: Any = None, is_secondary_index: bool = None,
            secondary_index_name: str = None, consistent_read: bool = False) -> DatabaseQueryResult:
        if equals is None:
            equals = key
            key = None
        if equals is None:
            raise RuntimeError("`equals` must not be None.")
        if secondary_index_name is not None and not is_secondary_index:
            raise RuntimeError("Illegal argument, secondary index name provided unexpectedly.")

        if is_secondary_index is False or key is None or key == self.hash_key():
            if key is None:
                key = self.hash_key()

            query = self._db.db_resource.Table(self._table_name).query(
                KeyConditionExpression=Key(key).eq(equals),
                ConsistentRead=consistent_read,
            )
        else:
            gsi = self.gsi()
            if key not in gsi.keys():
                raise RuntimeError("Key is not a secondary index!")
            if secondary_index_name is None:
                secondary_index_name = self.gsi()[key]
            query = self._db.db_resource.Table(self._table_name).query(
                IndexName=secondary_index_name,
                KeyConditionExpression=Key(key).eq(equals),
                ConsistentRead=consistent_read
            )

        return DatabaseQueryResult(query, self)

    def write(self, values: Dict[str, Any]) -> None:
        values = self.__convert_to_decimal(values)

        self._db.db_resource.Table(self._table_name).put_item(
            Item=values
        )

    def delete(self, where: str, equals: Any) -> None:
        self._db.db_resource.Table(self._table_name).delete_item(Key={where: equals})

    def __convert_to_decimal(self, x):
        if isinstance(x, float) or isinstance(x, int) and not isinstance(x, bool):
            return Decimal(str(x))
        if isinstance(x, list):
            new_list = []
            for v in x:
                new_list.append(self.__convert_to_decimal(v))
            return new_list
        if isinstance(x, dict):
            new_dict = {}
            for key, value in x.items():
                new_dict[key] = self.__convert_to_decimal(value)
            return new_dict
        return x

    def update(self, key: str = None, equals: Any = None, data_to_update: Dict[str, Any] = None) -> None:
        if not data_to_update or data_to_update is None:
            return

        data_to_update = self.__convert_to_decimal(data_to_update)

        if equals is None:
            equals = key
            key = None
        if equals is None:
            raise RuntimeError("`equals` must not be None.")

        if key is not None and key != self.hash_key():
            data = self.get(key=key, equals=equals)
            if not data.exists():
                raise RuntimeError("Data with that value is not found. Use `write()` instead.")
            equals = data[self.hash_key()]

        key = self.hash_key()

        expression = "SET "
        expression_attr_val = {}
        expression_attr_name = {}

        for i, (k, d) in enumerate(data_to_update.items()):
            expression += f"#{string.ascii_letters[2 * i]} = :{string.ascii_letters[2 * i + 1]}, "
            expression_attr_name["#" + string.ascii_letters[2 * i]] = k
            expression_attr_val[":" + string.ascii_letters[2 * i + 1]] = d

        expression = expression[:-2]

        self._db.db_resource.Table(self._table_name).update_item(
            Key={key: equals},
            UpdateExpression=expression,
            ExpressionAttributeValues=expression_attr_val,
            ExpressionAttributeNames=expression_attr_name,
        )

    def relative_update(self, where: str, equals: str, update: str, by: int, using_operation: str) -> None:
        expression = f"SET #a = #a {using_operation} :b"
        expression_attr_name = {
            "#a": update
        }
        expression_attr_val = {
            ":b": by
        }

        key = {where: equals}
        self._db.db_resource.Table(self._table_name).update_item(
            Key=key,
            UpdateExpression=expression,
            ExpressionAttributeValues=expression_attr_val,
            ExpressionAttributeNames=expression_attr_name
        )

    def increment(self, where: str, equals: str, value_key: str, by: int) -> None:
        self.relative_update(where, equals, update=value_key, by=by, using_operation="+")

    def decrement(self, where: str, equals: str, value_key: str, by: int) -> None:
        self.relative_update(where, equals, update=value_key, by=by, using_operation="-")

    def scan(self, consistent_read: bool = False) -> DatabaseQueryResult:
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

        return DatabaseQueryResult({"Items": scan_result}, self)


class KeyValueTable(Table):

    def __init__(self, db, table_name: str, key_col_name: str, val_col_name: str):
        super().__init__(db, table_name)
        self._key_col_name = key_col_name
        self._val_col_name = val_col_name

    def value(self, for_key: str) -> Any:
        res = self.get(self._key_col_name, equals=for_key)

        if not res.exists():
            return None

        return res.first()[self._val_col_name]

    def set(self, for_key: str, new_value: Any) -> None:
        self.update(
            for_key,
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

    def key_value_table(self, table_name, key_column_name="data-id", value_column_name="value") -> KeyValueTable:
        return KeyValueTable(self, table_name, key_column_name, value_column_name)

    def globals(self) -> KeyValueTable:
        return self.key_value_table(
            self._global_data_table_name,
            self._global_data_config["key_column_name"],
            self._global_data_config["value_column_name"]
        )
