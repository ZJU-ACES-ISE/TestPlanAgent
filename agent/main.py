import os
import json

from agent.multi_agent import get_graph_testplan_1
from agent.test_plan_agent import get_graph_testplan
from utils.Serialization import AIMessageEncoder
from utils.inputs import from_github
from langchain_core.messages import HumanMessage
from utils.tools import get_pr_metadata

from composio import Action

def main() -> None:
    """Run the agent."""
    owner, repo_name, pull_number = from_github()

    repo_path = f"/home/veteran/projects/multiAgent/{repo_name}"

    graph, _ = get_graph_testplan(repo_path)

    humanMessage_pr_agent = f"You have {owner}/{repo_name} cloned at your current working directory. Review PR {pull_number} on this repository and create comments on the same PR"
    humanMessage_testplan_agent = f"You have cloned {owner}/{repo_name} into your current working directory. Review PR {pull_number} on this repository and write a test plan, then create a comment on the same PR with the review and test plan"
    humanMessage_testplan_agent_v1 = f"You have cloned {owner}/{repo_name} into your current working directory. Review PR {pull_number} on this repository and write a test plan, then create a comment on the same PR with the review and test plan"
    run_result = graph.invoke(
        {
            "messages": [
                HumanMessage(
                    content=humanMessage_testplan_agent_v1
                )
            ]
        },
        {"recursion_limit": 50},
    )
    
    with open("./log/run_result.txt", "w") as f:
        # json.dump(run_result['messages'][-1], f, cls=AIMessageEncoder, indent=4)
        f.write(str(run_result))

    # print(json.dumps(run_result['messages'][-1], cls=AIMessageEncoder, indent=4))
    print(run_result)


if __name__ == "__main__":
    main()


    # composio_toolset.execute_action(
    #     action=Action.FILETOOL_GIT_CLONE,
    #     params={"repo_name": f"{owner}/{repo_name}"},
    # )
    # composio_toolset.execute_action(
    #     action=Action.FILETOOL_CHANGE_WORKING_DIRECTORY,
    #     params={"path": repo_path},
    # )
    # composio_toolset.execute_action(
    #     action=Action.CODE_ANALYSIS_TOOL_CREATE_CODE_MAP,
    #     params={},
    # )

    # response = composio_toolset.execute_action(
    #     action=get_pr_metadata,
    #     params={
    #         "owner": "ComposioHQ",
    #         "repo": "composio",
    #         "pull_number": "766",
    #         "thought": "Get the metadata for the PR",
    #     },
    # )
    # base_commit = response["data"]["metadata"]["base"]["sha"]

    # composio_toolset.execute_action(
    #     action=Action.FILETOOL_GIT_CLONE,
    #     params={
    #         "repo_name": "ComposioHQ/composio",
    #         "just_reset": True,
    #         "commit_id": base_commit,
    #     },
    # )