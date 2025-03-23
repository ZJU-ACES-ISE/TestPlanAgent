import ast
import json
import pickle
import requests
# from composio import ComposioToolSet, Action
# from utils.tools import get_pr_diff

# tool_set = ComposioToolSet(entity_id="Jessica")

# result = tool_set.execute_action(
#    action = get_pr_diff,
#    params = {"owner": "getsentry", "repo": "snuba", "pull_number": "3353", "thought": "no"},
#    entity_id = "Jessica",
# )

# with open("diff.json", "w") as f:
#     json.dump(result, f)


# Get the action schema
# action_schema = tool_set.get_action_schemas(actions=[Action.FILETOOL_FIND_FILE])

# Print the parameters in a readable format
# print(json.dumps(action_schema[0].parameters.properties, indent=2))

# file_find_result = tool_set.execute_action(
#     action=Action.FILETOOL_OPEN_FILE,
#     params={"file_path": "test_projects/mindcv/scripts/gen_benchmark.py"},
#     entity_id="Jessica",
# )

# print(file_find_result)

# st = '### Thought: I have identified the core functionality of the new migration order validator in the `validator.py` file, specifically the checks implemented for validating the migration order for the operations involved. The test should ensure that various migration combinations follow the established validation rules without errors. \n\n### Test Steps:\n```\n1. Set up the test environment:\n   - Ensure that the Snuba project is correctly set up and that the necessary dependencies are installed.\n   - Make sure the Clickhouse server is running and configured correctly for testing.\n\n2. Create test cases for the migration order validation:\n   - Implement a test file named `test_validator.py` under the `tests/migrations` directory.\n   - Within this file, import necessary modules including `pytest` and the relevant validator functions from the `validator` module.\n\n3. Define Migration Test Structures:\n   - Use `pytest.mark.parametrize` to parametrize tests for the validation scenarios based on various migration operations.\n   - Include cases where migrations are in the correct order and cases where they are not.\n\n4. Execute the tests:\n   - For operations such as `AddColumn`, `CreateTable`, and `DropColumn`, create local and distributed operations using mock data.\n   - Input the migration scenarios into the `validate_migration_order` function defined in the `validator.py`.\n\n5. Validate the outcomes:\n   - Assert that the validator raises `InvalidMigrationOrderError` for invalid migration orders with appropriate error messages.\n   - Log the outcomes of the tests to ensure that the validator is functioning as expected.\n\n6. Run the test suite:\n   - Use the pytest runner to execute all tests in the `tests/migrations/test_validator.py`.\n   - Confirm that all tests pass successfully, indicating that the migration order validation logic is working as intended.\n\n7. Review and document:\n   - After running the tests, review the results for any failures and document any potential issues uncovered during testing for further resolution.\n   - Update the test documentation to reflect any changes made during the validation of migration order implementation.\n```'

# thought = ''.join(st.split('Thought')[1].split('Test Steps')[0].split(':')[1:]).strip()
# test_step = st.split('Test Steps')[1].splitlines()

# # print(thought)
# print(test_step)

# with open('./CKG/rec_movies_graph.pkl', 'rb') as f:
#     CKG = pickle.load(f)

# with open('./CKG/rec_movies_graph_1.pkl', 'rb') as f:
#     CKG_1 = pickle.load(f)

# 提取节点
# nodes_CKG = set(CKG.nodes())  # 假设 CKG 是一个图对象
# nodes_CKG_1 = set(CKG_1.nodes())  # 假设 CKG_1 是一个图对象

# 找出 CKG_1 中有而 CKG 中没有的节点
# unique_nodes_CKG_1 = nodes_CKG_1 - nodes_CKG

# 输出结果
# print("Nodes in CKG_1 but not in CKG:", unique_nodes_CKG_1)

# result = result.replace("\"","").replace("\\", "").replace("\n", "\\n").replace("\r", "\\n")


# res = '{"xx": "x\\nx"}'

# # Finally parse with json
# parsed_json = json.loads(res)
# print(parsed_json)

url = "https://api.github.com/repos/getsentry/snuba/pulls/653/files"

response = requests.get(url)

print(response.text)