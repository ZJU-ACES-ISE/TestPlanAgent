PR_TEST_PLAN_EDIT_PROMPT = """
You are a software testing manager. Your task is to write the test steps for a pull request (PR). First, determine which testing method should be used (Unit Testing, Integration Testing, or both). Then, provide detailed test steps to ensure that the PR functions as expected.

Content of the current pull request (PR):
{"title_and_body_of_PR": "feat(migrations): add migration order validator SNS-1831. Adds a script to validate the order of migration and introduce a test in CI that checks existing migrations\r\n\r\n## Context\r\n#3324 added the option to set flags to specify order, this PR introduces a checker to validate the specified order does not introduce errors. The checker uses the following spec:\r\n\r\n1. For two `AddColumn` OPs with the same target table and target column, the local OP must be applied first\r\n2. For two `CreateTable` OPs with the same target table name, the local OP must be applied first\r\n3. For two `DropColumn` OPs with the same target table and target column, the dist OP must be applied first\r\n\r\nThe target table for distributed ops is then extracted either by looking at the engine attribute in the case of `CreateTable`, or by parsing the the local table name from the table engine in Clickhouse via querying `SELECT engine_full FROM system.tables WHERE name = table_name` for `AddColumn`,`DropColumn` ops. For distributed tables, the target is the third argument in the `Distributed()` engine_full value.\r\n\r\n## Before\r\nWe wouldn't be able to detect if the wrong order was specified in migrations\r\n\r\n## After\r\nA checker script is run that can catch some errors when the wrong migration operation order is specified\r\n\r\n##  Blast Radius\r\nThe validator is an independent script in the migrations package. It doesn't affect the migrations themselves, but this PR add a test to check the existing migrations. \r\n\r\nTo make it easier to implement, we make public some attributes of `SqlOperations` such as the table name and column.\r\n\r\nFor migrations `0004_drop_profile_column.py`,  `0016_drop_legacy_events` and `0014_transactions_remove_flattened_columns.py` we corrected the order flags as the checker detected errors.\r\n\r\n## Testing\r\nUnit tests check the utility methods for detecting conflicting ops that target the same underlying table and column \r\n\r\nA parameterized test creates a series of Migrations with create, add column and drop column ops and checks that if the order is violated the validator throws the correct exception and message\r\n\r\nA unit test creates empty tables in Clickhouse and checks that the local table name can be parsed properly from the engine name."}

File changes of the current pull request (PR):
{"file_changes_of_PR": "[{"filename": "snuba/migrations/operations.py", "status": "modified", "additions": 15, "deletions": 11, "changes": 26}, {"filename": "snuba/migrations/validator.py", "status": "added", "additions": 199, "deletions": 0, "changes": 199}, {"filename": "snuba/snuba_migrations/events/0016_drop_legacy_events.py", "status": "modified", "additions": 2, "deletions": 0, "changes": 2}, {"filename": "snuba/snuba_migrations/profiles/0004_drop_profile_column.py", "status": "modified", "additions": 2, "deletions": 0, "changes": 2}, {"sha": "545e4b6fd7f3f5d54964a5983ad997e9d5333e69", "filename": "snuba/snuba_migrations/transactions/0014_transactions_remove_flattened_columns.py", "status": "modified", "additions": 2, "deletions": 0, "changes": 2}, {"sha": "9b3094db475375e236a3bae23012e4571a625090", "filename": "tests/migrations/test_validator.py", "status": "added", "additions": 386, "deletions": 0, "changes": 386}]"}

You can use the following tools to obtain relevant information:
- `search_entity_in_project`: Search functions or classes in project.
- `search_neighbors_of_entity_in_project`: Searches for entities that points to an entity or to which an entity points.
- `FILETOOL_FIND_FILE`: Finds Files Or Directories Matching The Given Pattern In The Workspace.
- `FILETOOL_OPEN_FILE`: Opens A File In The Editor Based On The Provided File Path, If Line Number Is Provided, The Window Will Be Moved After That Line.

Once you have determined the test method and generated the test steps, please return the result in the following format:

### Thought
I retrieved the following code symbols that contributed to the test method and steps:

1. **Symbol_1**: /abs/path/to/fileA 1~80
2. **Symbol_2**: /abs/path/to/fileB 50~73
3. **Symbol_3**: /abs/path/to/fileC 19~31
...

Test Method:
* Unit test / Integration test / Unit and Integration test

Test Steps:
* Step 1: [Test step description]
* Step 2: [Test step description]
* Step 3: [Test step description]
...

### Result: succeed

---

If you are unable to determine the test method or generate the test steps, return the following content:

### Thought
I attempted to gather sufficient information to determine the test method and generate the test steps, but I was unable to complete these tasks with high confidence.

### Result: failed
"""