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
def get(key: str, equals: Any, is_secondary_index: Optional[bool] = False, secondary_index_name: Optional[str] = None, consistent_read: Optional[bool] = False):
```
> `key`- The query key (i.e. the name of the column to be queried).  
> `equals` - The value to match in the query (i.e. the value we want the value at `key` to equal).  
> `is_secondary_index` - If the `key` is the _primary key_ or _hash key_, this should be set to `False`.  
> `secondary_index_name` - If the name of the secondary index does not match DynamoDB default, do not provide this 
> otherwise.  
> `consistent_read` - Whether `consistent_read` should be set in Boto3 (see DynamoDB docs for more details).

#### Example 1
The following example is trying to get data from table `my-user-table` by querying for where `user-id` (primary key) 
equals `a_user_id` (we are finding the data for the user whose `user-id` is `a_user_id`).

```python
from DynamoDBInterface import DynamoDB
db = DynamoDB.Database()

result = db.table("my-user-table").get(
    "user-id", equals="a_user_id"
)
```

#### Example 2
The following example is also trying to get data from the same table (`my-user-table`) but is querying using `username` 
instead (we are finding the data for the user whose `username` is `a_username`).

```python
from DynamoDBInterface import DynamoDB
db = DynamoDB.Database()

result = db.table("my-user-table").get(
    "username", equals="a_username",
    is_secondary_index=True
)
```

> **Important:** This will result in an exception being thrown (and subsequent crash) if `username` isn't created as a 
> global secondary index for the table.

### Check if a value exists
The `there_exists()` function provides a shortcut way for checking if a row where a key matches a certain value exists. 
The function signature is as follows:
```python
def there_exists(a_value: Any, at_column: str, is_secondary_index: bool = False, secondary_index_name: str = None, consistent_read: bool = False):
```

> `a_value` - The value we are trying to match.  
> `at_column` - The name of the column that we want to check.
>
> Similar to `get()`, if we are checking in a column that is not a primary key, `is_secondary_index` _must_ be set to 
> `true`.

#### Example 1
We want to check if a username already exists.
```python
from DynamoDBInterface import DynamoDB
db = DynamoDB.Database()

username_already_exists = db.table("my-user-table").there_exists(
    "a-username", at_column="username",
    is_secondary_index=True
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
The `update()` will add or make changes to field in a row referenced by a primary key. The function signature is as 
follows:
```python
def update(where: str, equals: Any, data_to_update: Dict[str, Any]):
```
> `where` - Similar to `key` in the `get()` function.
> 
> **Note:** Unlike `get()`, the row that you wish to update _cannot_ be referenced using a secondary index.

#### Example 1
The user we created from [the section above](#writing-data) no longer lives in Somerset and has moved to the East 
Anglia.

```python
from DynamoDBInterface import DynamoDB
db = DynamoDB.Database()

db.table("my-user-table").update(
    where="user-id", equals="another_id",
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
    where="user-id", equals="another_id",
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

### Scanning the Table
Scanning the table will return all the rows in the table. The function signature is as follows:
```python
def scan(consistent_read: bool = False):
```

> **Important Note:** DynamoDB handles returning large amounts of data in different way to small amount of data. The 
> `scan()` function is written to handle both cases, but its behaviour is still untested when DynamoDB returns data 
> larger than 1MB.

#### Example:
```python
from DynamoDBInterface import DynamoDB
db = DynamoDB.Database()

all_users_data = db.table("my-user-table").scan()
```

## DatabaseQueryResult Class
When the `get()` function [above](#get-data) is called, it returns the `DatabaseQueryResult` object which represents 
the response from DynamoDB.

> `DatabaseQueryResult` implements `__getitem__()` so referencing an index in the result can be done directly like a 
> normal list (with square brackets surround a number).

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
result.all() # Returns all the value as a proper list, will return [] (empty list) if data doesn't exist
```

> Note that result **always** act like a list (even when you're querying using primary key and there's supposed to only 
> be one row returned). Therefore, even when accessing fields from result that only has one value, you will have to 
> either use `first()` to reference the first (and only) row or do `result[0]` before accessing. For example:
> `user_region = result.first()["region"]` or `user_region = result[0]["region"]`

