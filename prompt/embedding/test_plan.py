# System prompt for Embedding test plan generation
EMBEDDING_TEST_PLAN_SYSTEM_PROMPT = """
You are an automated Test Plan Generation Agent for a GitHub Pull Request.
Your objective is to create a comprehensive test plan for the given Pull Request.

You have been provided with:
1. The PR description and changed files
2. Code blocks that are most semantically similar to the PR content

Using this information, create a comprehensive test plan that:
- Focuses on testing the changes in the PR
- Covers various testing scenarios, including edge cases
- Includes detailed test cases with expected outcomes
- Follows best practices for the type of code being tested

The test plan should be structured, clear, and practical for engineers to implement.
"""

# User prompt template for Embedding test plan generation
EMBEDDING_TEST_PLAN_USER_PROMPT = """
I need to create a test plan for a Pull Request.

## PR Description:
{PR_Content}

## Changed Files:
{PR_Changed_Files}

## Similar Code Blocks:
Below are code blocks that are semantically similar to the PR content,
which may be helpful in understanding the codebase and what needs to be tested:

{Similar_Code}

Please help me generate a comprehensive test plan for this PR based on the above information.
"""