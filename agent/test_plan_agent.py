import operator
import os
import typing as t
from enum import Enum

import dotenv
from langchain_aws import ChatBedrock
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from prompt.test_plan_prompt_v3 import PR_TEST_PLAN_EDIT_PROMPT

from tenacity import retry, stop_after_attempt, wait_exponential
from utils.tools import search_entity_in_project, search_neighbors_of_entity_in_project
from composio_langgraph import Action, App, ComposioToolSet, WorkspaceType

dotenv.load_dotenv()

class Model(str, Enum):
    CLAUDE = "claude"
    OPENAI = "openai"

model = Model.OPENAI

def add_thought_to_request(request: t.Dict[str, t.Any]) -> t.Dict[str, t.Any]:
    request["thought"] = {
        "type": "string",
        "description": "Provide the thought of the agent in a small paragraph in concise way. This is a required field.",
        "required": True,
    }
    return request

def pop_thought_from_request(request: t.Dict[str, t.Any]) -> t.Dict[str, t.Any]:
    request.pop("thought", None)
    return request

def get_graph_testplan(repo_path):
    toolset = ComposioToolSet(
        # workspace_config=WorkspaceType.Docker(persistent=True),
        workspace_config=WorkspaceType.Host(persistent=True),
        metadata={
            App.CODE_ANALYSIS_TOOL: {
                "dir_to_index_path": repo_path,
            }
        },
        processors={
            "pre": {
                App.GITHUB: pop_thought_from_request,
                App.FILETOOL: pop_thought_from_request,
                App.CODE_ANALYSIS_TOOL: pop_thought_from_request,
            },
            "schema": {
                App.GITHUB: add_thought_to_request,
                App.FILETOOL: add_thought_to_request,
                App.CODE_ANALYSIS_TOOL: add_thought_to_request,
            },
        #     "post": {
        #         Action.GITHUB_CREATE_AN_ISSUE_COMMENT: _github_pulls_create_review_comment_post_proc,
        #         Action.GITHUB_CREATE_A_REVIEW_COMMENT_FOR_A_PULL_REQUEST: _github_pulls_create_review_comment_post_proc,
        #         Action.GITHUB_LIST_COMMITS_ON_A_PULL_REQUEST: _github_list_commits_post_proc,
        #         Action.GITHUB_GET_A_COMMIT: _github_diff_post_proc,
        #         Action.GITHUB_GET_A_PULL_REQUEST: _github_get_a_pull_request_post_proc,
        #         Action.GITHUB_LIST_REVIEW_COMMENTS_ON_A_PULL_REQUEST: _github_list_review_comments_on_a_pull_request_post_proc,
        #     },
        },
    )
    test_plan_edit_tools = [
        *toolset.get_tools(
            actions=[
                search_entity_in_project,
                search_neighbors_of_entity_in_project,
                Action.FILETOOL_FIND_FILE,
                Action.FILETOOL_OPEN_FILE
            ]
        )
    ]

    # comment_on_pr_tools = [
    #     *toolset.get_tools(
    #         actions=[
    #             Action.GITHUB_CREATE_A_REVIEW_COMMENT_FOR_A_PULL_REQUEST,
    #         ]
    #     )
    # ]
    if model == Model.CLAUDE:
        client = ChatBedrock(
            credentials_profile_name="default",
            model_id="anthropic.claude-3-5-sonnet-20240620-v1:0",
            region_name="us-east-1",
            model_kwargs={"temperature": 0, "max_tokens": 8192},
        )
    else:
        client = ChatOpenAI(
            model="gpt-4o",
            temperature=0,
            # max_completion_tokens=4096,
            api_key=os.environ["OPENAI_API_KEY"],
            base_url="https://api.gptsapi.net/v1"
        )

    class AgentState(t.TypedDict):
        messages: t.Annotated[t.Sequence[BaseMessage], operator.add]
        sender: str

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
    )
    def invoke_with_retry(agent, state):
        return agent.invoke(state)

    def create_agent_node(agent, name):
        def agent_node(state):
            if model == Model.CLAUDE and isinstance(state["messages"][-1], AIMessage):
                state["messages"].append(HumanMessage(content="Placeholder message"))

            try:
                result = invoke_with_retry(agent, state)
            except Exception as e:
                print(f"Failed to invoke agent after 3 attempts: {str(e)}")
                result = AIMessage(
                    content="I apologize, but I encountered an error and couldn't complete the task. Please try again or rephrase your request.",
                    name=name,
                )
            if not isinstance(result, ToolMessage):
                if isinstance(result, dict):
                    result_dict = result
                else:
                    result_dict = result.dict()
                result = AIMessage(
                    **{
                        k: v
                        for k, v in result_dict.items()
                        if k not in ["type", "name"]
                    },
                    name=name,
                )
            return {"messages": [result], "sender": name}

        return agent_node

    def create_agent(system_prompt, tools):
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )
        llm = client
        if tools:
            # return prompt | llm.bind_tools(tools)
            return prompt | llm.bind_tools(tools)
        else:
            return prompt | llm



    test_plan_edit_agent_name = "Test-Plan-Edit-Agent"
    test_plan_edit_agent = create_agent(PR_TEST_PLAN_EDIT_PROMPT, test_plan_edit_tools)
    test_plan_edit_agent_node = create_agent_node(test_plan_edit_agent, test_plan_edit_agent_name)

    # comment_on_pr_agent_name = "Draft-Testplan-And-Comment-On-PR-Agent"
    # comment_on_pr_agent = create_agent(PR_TEST_PLAN_GENERATOR_PROMPT, comment_on_pr_tools)
    # comment_on_pr_agent_node = create_agent_node(comment_on_pr_agent, comment_on_pr_agent_name)

    workflow = StateGraph(AgentState)

    workflow.add_edge(START, test_plan_edit_agent_name)
    workflow.add_node(test_plan_edit_agent_name, test_plan_edit_agent_node)
    
    # workflow.add_node(comment_on_pr_agent_name, comment_on_pr_agent_node)
    
    workflow.add_node("test_plan_edit_tools_node", ToolNode(test_plan_edit_tools))

    # workflow.add_node("comment_on_pr_tools_node", ToolNode(comment_on_pr_tools))

    def fetch_pr_router(
        state,
    ) -> t.Literal["test_plan_edit_tools_node", "continue", "__end__"]:
        messages = state["messages"]
        for message in reversed(messages):
            if isinstance(message, AIMessage):
                last_ai_message = message
                break
        else:
            last_ai_message = messages[-1]

        if last_ai_message.tool_calls:
            return "test_plan_edit_tools_node"
        if "Result: succeed" in last_ai_message.content:
            return "__end__"
        return "continue"

    workflow.add_conditional_edges(
        "test_plan_edit_tools_node",
        lambda x: x["sender"],
        {test_plan_edit_agent_name: test_plan_edit_agent_name},
    )
    workflow.add_conditional_edges(
        test_plan_edit_agent_name,
        fetch_pr_router,
        {
            "continue": test_plan_edit_agent_name,
            "test_plan_edit_tools_node": "test_plan_edit_tools_node",
            "__end__": END,
        },
    )

    # def comment_on_pr_router(
    #     state,
    # ) -> t.Literal["comment_on_pr_tools_node", "continue", "__end__"]:
    #     messages = state["messages"]
    #     for message in reversed(messages):
    #         if isinstance(message, AIMessage):
    #             last_ai_message = message
    #             break
    #     else:
    #         last_ai_message = messages[-1]

    #     if last_ai_message.tool_calls:
    #         return "comment_on_pr_tools_node"
        
    #     if "TEST PLAN DRAFTED" in last_ai_message.content:
    #         return "__end__"
    #     return "continue"

    # workflow.add_conditional_edges(
    #     "comment_on_pr_tools_node",
    #     lambda x: x["sender"],
    #     {comment_on_pr_agent_name: comment_on_pr_agent_name},
    # )
    # workflow.add_conditional_edges(
    #     comment_on_pr_agent_name,
    #     comment_on_pr_router,
    #     {
    #         "continue": comment_on_pr_agent_name,
    #         "comment_on_pr_tools_node": "comment_on_pr_tools_node",
    #         "__end__": END,
    #     },
    # )

    graph = workflow.compile()

    return graph, toolset
