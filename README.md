# DynamoDB Python Helper
This piece of code allows assists with interaction between Python codes running on Lambda and DynamoDB. This is done by 
simplifying syntax for frequently used interactions (like getting, writing and updating), so that the code is more 
readable and shorter than with only `boto3` (which the code is based on).

# Installation

#### Installation with `pip`
To install, run the following command in terminal
```bash
pip install git+https://github.com/Samaggi-Samagom/DynamoDB-Python-Helper@master
```

#### Using `requirements.txt`
Or add the following line to `requirements.txt`
```requirements.txt
git+https://github.com/Samaggi-Samagom/DynamoDB-Python-Helper@main
```
> Once added, do not forget to run
> ```bash
> pip install -r requirements.txt
> ```

# Policies
It is required that the lambda function that wishes to use any of the functions have been attached with a
```yaml
Policies:
  - DynamoDBCrudPolicy:
      TableName: "*"
```
> You may replace the wildcard `*` with a table name if smaller scope is required (and if you only wish to access that 
> table.)

Multiple policies can be attached if you wish to provide access to multiple specific tables. For example:
```yaml
Policies:
  - DynamoDBCrudPolicy:
      TableName: "my-first-table"
  - DynamoDBCrudPolicy:
      TableName: "my-second-table"
```

# Documentation
## Database Class
Use the `Database` class to initialise the code. The class does not perform any action by itself apart from 
initialising the _boto3 database resource_. The class is also used to create reference to a table via the 
[Table](#Table Class) class.

The class can be initialised globally
```python
from DynamoDBInterface import DynamoDB

db = DynamoDB.Database()
```

Or inside individual functions
```python
from DynamoDBInterface import DynamoDB

def my_lambda_function(event, context):
    db = DynamoDB.Database()
```

### (Optional) Setting Database Globals
A database can be initialised with a defined globals table. A globals table is a `KeyValueTable`
(see [docs](#keytablevalue-class)) that can be called using the `.globals()` shortcut. The globals table can be defined 
when initialising the database object by providing the name of the globals table.

```python
from DynamoDBInterface import DynamoDB

db = DynamoDB.Database("my-globals-table")
```

With the globals set, the following call would be made

```python
from DynamoDBInterface import DynamoDB
db = DynamoDB.Database("my-globals-table")

db.globals().value("id-1")
```

This is exactly equivalent to:

```python
from DynamoDBInterface import DynamoDB
db = DynamoDB.Database("my-globals-table")

db.key_value_table("my-globals-table").value("id-1")
```


## Table Class
The `Table` class represents tables in a DynamoDB database. A `Table` _object_ represents a specific table in the 
database. 

### Initialisation
The `Table` object should only be created directly from the `Database` object.

```python
from DynamoDBInterface import DynamoDB
db = DynamoDB.Database()

my_table = db.table("my-table")
```

### Get Data
To get data from a table, the `get()` function can be called on the Table object. The function signature is as follows:

```python
def get(key: str, equals: Any, consistent_read: bool = False):
```
> `key`- The query key (i.e. the name of the column to be queried).  
> `equals` - The value to match in the query (i.e. the value we want the value at `key` to equal).   
> `consistent_read` - Whether `consistent_read` should be set in Boto3 (see DynamoDB docs for more details).

#### Example 1
The following example is trying to get data from table `my-user-table` by querying for where `user-id` (primary key) 
equals `a_user_id` (we are finding the data for the user whose `user-id` is `a_user_id`).

```python
from DynamoDBInterface import DynamoDB
db = DynamoDB.Database()

result = db.table("my-user-table").get("a_user_id")
```

#### Example 2
The following example is also trying to get data from the same table (`my-user-table`) but is querying using `username` 
instead (we are finding the data for the user whose `username` is `a_username`).

```python
from DynamoDBInterface import DynamoDB
db = DynamoDB.Database()

result = db.table("my-user-table").get(
    "username", equals="a_username"
)
```

> **Important:** This will result in an exception being thrown (and subsequent crash) if `username` isn't created as a 
> global secondary index for the table.

### Check If a Value Exists
The `there_exists()` function provides a shortcut way for checking if a row where a key matches a certain value exists. 
The function signature is as follows:
```python
def there_exists(a_value: Any, at_column: str, consistent_read: bool = False):
```

> `a_value` - The value we are trying to match.  
> `at_column` - The name of the column that we want to check.
>
> Similar to `get()`, if we are checking in a column that is not a primary key, `is_secondary_index` _must_ be set to 
> `true`.

#### Example 1
Checking if a user-id (primary/hash key) already exists.

```python
from DynamoDBInterface import DynamoDB
db = DynamoDB.Database()

id_already_exists = db.table("my-user-table").there_exists("a_user_id")
```

#### Example 2
Checking if a username already exists.
```python
from DynamoDBInterface import DynamoDB
db = DynamoDB.Database()

username_already_exists = db.table("my-user-table").there_exists(
    "a-username", at_column="username",
)

if username_already_exists:
    print("The username already exists!")
```

### Writing Data
The `write()` function will write a row into the database table. The function signature is as follows:

```python
def write(values: Dict[str, Any]):
```

> Writing data **will replace any data that already exists with the same primary key** without warning. Ensure that 
> there is currently no data with the same primary key before proceeding. Use `uuid.uuid4()` for similar for primary 
> key if possible.

#### Example
The following example is writing a new user to `my-user-table`.

```python
from DynamoDBInterface import DynamoDB
db = DynamoDB.Database()

db.table("my-user-table").write(
    {
        "user-id": "another_id",
        "username": "new_username",
        "favourite-character": "Paddington",
        "favourite-snack": "Oreos",
        "region": "Somerset"
    }
)
```

> As DynamoDB is not strict about columns, you can provide as much or as little fields as you want (it will show up 
> empty on the console if there's no data, and it will automatically add a new column if you provide a new field). 
> However, you **must** always provide the _primary key_ (`user-id` in this case) or else this will fail.

### Updating Data
The `update()` will add or make changes to field in a row. The function signature is as 
follows:
```python
def update(where: str, equals: Any, data_to_update: Dict[str, Any]):
```
> `key` - The query key (i.e. the name of the column to be queried).  
> `equals` - The value to match in the query (i.e. the value we want the value at `key` to equal).  
> `data_to_update` - The data to update the row with.

> **Important Note**: If a change involves incrementing/decrementing values or manipulation of numeric values in ways 
> that consistencies might be an issue (e.g. decrementing available ticket count) then 
> [relative updates](#relative-update--general-) should be used instead.

#### Example 1
The user we created from [the section above](#writing-data) no longer lives in Somerset and has moved to the East 
Anglia.

```python
from DynamoDBInterface import DynamoDB
db = DynamoDB.Database()

db.table("my-user-table").update(
    "key",
    data_to_update={
        "region": "East Anglia"
    }
)
```

#### Example 2
The user we just updated moved back to Somerset and also changed their username to `newnew_username`. They have also 
just registered that email address (which was not on the database before).

```python
from DynamoDBInterface import DynamoDB
db = DynamoDB.Database()

db.table("my-user-table").update(
    "another_id",
    data_to_update={
        "region": "Somerset",
        "username": "newnew_username",
        "email": "emailAddress@anEmailProvider.com"
    }
)
```

> When providing data that hasn't existed before, the update function would, similar to the write function, create a 
> new _column_ in the database automatically. If the field already exists, it will be updated.
> 
> **Important:** Updating the primary key is unsafe. If absolutely necessary, make a copy of the data (call `get()` 
> then `write()` under the new primary key) then delete the old data (see below).

#### Example 3
We have the user's username (which is a secondary index) and wish to update their email address.

```python
from DynamoDBInterface import DynamoDB
db = DynamoDB.Database()

db.table("my-user-table").update(
    "username", equals="a_username",
    data_to_update={
        "email": "newEmailAddress@anEmailProvider.com"
    }
)
```

> Due to DynamoDB's limitations, updating by secondary indexes involves first getting data to obtain the hash key. This 
> incurs significant performance penalty, therefore it is advised that if the hash key is available then the hash key 
> should be used instead.

### Relative Update (General)
Applies a certain update numerical value of a single field in a _consistent_ way. The function signature is as follows:

```python
def relative_update(self, key: str, equals: str, update: str, by: int, using_operation: str) -> None:
```
> `key` - The query key (i.e. the name of the column to be queried).  
> `equals` - The value to match in the query (i.e. the value we want the value at `key` to equal).  
> `update` - The column in the row that will be updated.  
> `by` - The amount to update the field by.
> `using_operation` - The operator to apply.

### Relative Update (Increment/Decrement)
Increment/Decrement numerical value in a field in a _consistent_ way by a specific amount. The function signature is as 
follows:
```python
def increment(self, key: str, equals: str, value_key: str, by: int) -> None:
def decrement(self, key: str, equals: str, value_key: str, by: int) -> None:
```
> `key` - The query key (i.e. the name of the column to be queried).  
> `equals` - The value to match in the query (i.e. the value we want the value at `key` to equal).  
> `value_key` - The name of the column in the row that will be updated.  
> `by` - The amount to update the field by.

#### Example 1
We want to increase the number of ticket count for two users in the `my-user-table` (where `user-id` is the hash key) 
and decrement the two tickets from the `my-ticket-count-table` (where `ticket-name` is a secondary index).
```python
from DynamoDBInterface import DynamoDB
db = DynamoDB.Database()

db.table("my-user-table").increment("a-user-id", value_key="num-tickets", by=1)
db.table("my-user-table").increment("another-user-id", value_key="num-tickets", by=1)
db.table("my-ticket-count-table").decrement("ticket-name", equals="a-ticket-name", value_key="num-available", by=2)
```

> **Note:** as of v1.3.18, `.increment()`, `.decrement()` and `.relative_update()` has not been overriden correctly 
> with `.globals()` yet. Avoid using these functions through `.globals()`.

### Scanning the Table
Scanning the table will return all the rows in the table. The function signature is as follows:
```python
def scan(consistent_read: bool = False):
```

#### Example:
```python
from DynamoDBInterface import DynamoDB
db = DynamoDB.Database()

all_users_data = db.table("my-user-table").scan()
```

## KeyTableValue Class
`KeyValueTable` is a subclass of `Table` class (see [here](#table-class)) but with special properties. `KeyValueTable` 
only supports DynamoDB tables with specific formats. By default the table might look like this:

| data-id | value |
|---------|-------|
| id-1    | hello |

In this case, the value of `"hello"` can simply be retrieved using:

```python
from DynamoDBInterface import DynamoDB
db = DynamoDB.Database()

res = db.key_value_table("my-key-value-table").value("id-1")  # Returns "hello"  
```

### Custom Table Format
By default `KeyValueTable` expects two columns: `data-id` and `value`. However, when initialising the table from the 
database, this can be overriden. For example for the following table:

| data-name | data-value |
|-----------|------------|
| id-1      | hello      |

```python
from DynamoDBInterface import DynamoDB
db = DynamoDB.Database()

res = db.key_value_table("my-key-value-table", key_column_name="data-name", value_column_name="data-value")  # Returns "hello"
```

## DatabaseQueryResult Class
When the `get()` function [above](#get-data) is called, it returns the `DatabaseQueryResult` object which represents 
the response from DynamoDB.

> `DatabaseQueryResult` implements `__getitem__()` so referencing an index in the result can be done directly like a 
> normal list (with square brackets surrounding a number).

The functions available on `DatabaseQueryResult` is as follows:

```python
from DynamoDBInterface import DynamoDB
db = DynamoDB.Database()

result = db.table("my-user-table").get(
    "user-id", equals="a_user_id"
)

result.exists() # True if a row exists where field "username" equals "a_username"
result.first() # Returns the first returned row from the query
result.last() # Returns the last returned row from the query
result.length() # Returns the number of rows returned
result.is_unique() # True if length()==1
result.all() # Returns all the value as a list, will return [] (empty list) if data doesn't exist
```

> Note that result **always** act like a list (even when you're querying using primary key and there's supposed to only 
> be one row returned). Therefore, even when accessing fields from result that only has one value, you will have to 
> either use `first()` to reference the first (and only) row or do `result[0]` before accessing. For example:
> `user_region = result.first()["region"]` or `user_region = result[0]["region"]`

