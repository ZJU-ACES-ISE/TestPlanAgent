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
from prompt.prompts import PR_COMMENT_PROMPT, PR_FETCHER_PROMPT, REPO_ANALYZER_PROMPT
from prompt.testplan_prompt_v1 import PR_TEST_PLAN_FETCH_PROMPT, PR_TEST_PLAN_GENERATOR_PROMPT
from prompt.testplan_prompt_v2 import PR_NL_Content_Fetch_Prompt, PR_Code_Content_Fetch_Prompt, PR_Type_Impact_Scope_Determination_Prompt, PR_Test_Plan_Generate_Prompt
from tenacity import retry, stop_after_attempt, wait_exponential
from utils.tools import Change_Impact_Scope_Determination, Change_Type_Classification, DiffFormatter, GITHUB_GET_Files_And_Get_Func, Get_PR_NL_Content, Parse_PR_and_Remove_Test_Plan, Test_Plan_Generator, get_pr_diff, get_pr_metadata

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


def _github_pulls_create_review_comment_post_proc(response: dict) -> dict:
    if response["successfull"]:
        return {"message": "commented sucessfully"}
    return {"error": response["error"]}


def _github_list_commits_post_proc(response: dict) -> dict:
    if not response["successfull"]:
        return {"error": response["error"]}
    commits = []
    for commit in response.get("data", {}).get("details", []):
        commits.append(
            {
                "sha": commit["sha"],
                "author": commit["commit"]["author"]["name"],
                "message": commit["commit"]["message"],
                "date": commit["commit"]["author"]["date"],
            }
        )
    return {"commits": commits}


def _github_diff_post_proc(response: dict) -> dict:
    if not response["successfull"]:
        return {"error": response["error"]}
    return {"diff": DiffFormatter(response["data"]["details"]).parse_and_format()}


def _github_get_a_pull_request_post_proc(response: dict):
    if not response["successfull"]:
        return {"error": response["error"]}
    pr_content = response.get("data", {}).get("details", [])
    contents = pr_content.split("\n\n---")
    pr_content = ""
    for i, content in enumerate(contents):
        if "diff --git" in content:
            index = content.index("diff --git")
            content_filtered = content[:index]
            if i != len(contents) - 1:
                content_filtered += "\n".join(content.splitlines()[-4:])
        else:
            content_filtered = content
        pr_content += content_filtered
    return {
        "details": pr_content,
        "message": "PR content fetched successfully, proceed with getting the diff of PR or individual commits",
    }


def _github_list_review_comments_on_a_pull_request_post_proc(response: dict) -> dict:
    if not response["successfull"]:
        return {"error": response["error"]}
    comments = []
    for comment in response.get("data", {}).get("details", []):
        comments.append(
            {
                "diff_hunk": comment["diff_hunk"],
                "commit_id": comment["commit_id"],
                "body": comment["body"],
            }
        )
    return {"comments": comments}

def get_graph_testplan_1(repo_path):
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
                App.CODE_ANALYSIS_TOOL: pop_thought_from_request
            },
            "schema": {
                App.GITHUB: add_thought_to_request,
                App.FILETOOL: add_thought_to_request,
                App.CODE_ANALYSIS_TOOL: add_thought_to_request,
            }, 
            "post": {
                Action.GITHUB_CREATE_AN_ISSUE_COMMENT: _github_pulls_create_review_comment_post_proc,
                Action.GITHUB_CREATE_A_REVIEW_COMMENT_FOR_A_PULL_REQUEST: _github_pulls_create_review_comment_post_proc,
                Action.GITHUB_LIST_COMMITS_ON_A_PULL_REQUEST: _github_list_commits_post_proc,
                Action.GITHUB_GET_A_COMMIT: _github_diff_post_proc,
                Action.GITHUB_GET_A_PULL_REQUEST: _github_get_a_pull_request_post_proc,
                Action.GITHUB_LIST_REVIEW_COMMENTS_ON_A_PULL_REQUEST: _github_list_review_comments_on_a_pull_request_post_proc,
            },
        },
    )
    fetch_pr_nl_content_tools = [
        *toolset.get_tools(
            actions=[
                Get_PR_NL_Content,
                Parse_PR_and_Remove_Test_Plan
            ]
        )
    ]
    
    fetch_pr_code_content_tools = [
        *toolset.get_tools(
            actions=[
                GITHUB_GET_Files_And_Get_Func,
            ]
        )
    ]

    pr_type_impact_scope_determination_tools = [
        *toolset.get_tools(
            actions=[
                Change_Type_Classification,
                Change_Impact_Scope_Determination
            ]
        )
    ]

    pr_test_plan_generate_tools = [
        *toolset.get_tools(
            actions=[
                Test_Plan_Generator
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

    # pr自然语言内容提取agent
    fetch_pr_nl_content_agent_name = "Fetch-PR-NL-Content-Agent"
    fetch_pr_nl_content_agent = create_agent(PR_NL_Content_Fetch_Prompt, fetch_pr_nl_content_tools)
    fetch_pr_nl_content_agent_node = create_agent_node(fetch_pr_nl_content_agent, fetch_pr_nl_content_agent_name)

    # pr代码内容提取agent
    fetch_pr_code_content_agent_name = "Fetch-PR-Code-Content-Agent"
    fetch_pr_code_content_agent = create_agent(PR_Code_Content_Fetch_Prompt, fetch_pr_code_content_tools)
    fetch_pr_code_content_agent_node = create_agent_node(fetch_pr_code_content_agent, fetch_pr_code_content_agent_name)

    # pr类型影响范围确定agent
    pr_type_impact_scope_determination_agent_name = "PR-Type-Impact-Scope-Determination-Agent"
    pr_type_impact_scope_determination_agent = create_agent(PR_Type_Impact_Scope_Determination_Prompt, pr_type_impact_scope_determination_tools)
    pr_type_impact_scope_determination_agent_node = create_agent_node(pr_type_impact_scope_determination_agent, pr_type_impact_scope_determination_agent_name)

    # pr test plan编写agent
    pr_test_plan_generate_agent_name = "PR-Test-Plan-Generate-Agent"
    pr_test_plan_generate_agent = create_agent(PR_Test_Plan_Generate_Prompt, pr_test_plan_generate_tools)
    pr_test_plan_generate_agent_node = create_agent_node(pr_test_plan_generate_agent, pr_test_plan_generate_agent_name)

    # 向github上传评论
    # comment_on_pr_agent_name = "Draft-Testplan-And-Comment-On-PR-Agent"
    # comment_on_pr_agent = create_agent(PR_TEST_PLAN_GENERATOR_PROMPT, comment_on_pr_tools)
    # comment_on_pr_agent_node = create_agent_node(comment_on_pr_agent, comment_on_pr_agent_name)

    workflow = StateGraph(AgentState)

    # 添加工作流节点
    workflow.add_edge(START, fetch_pr_nl_content_agent_name)
    workflow.add_node(fetch_pr_nl_content_agent_name, fetch_pr_nl_content_agent_node)
    workflow.add_node(fetch_pr_code_content_agent_name, fetch_pr_code_content_agent_node)
    workflow.add_node(pr_type_impact_scope_determination_agent_name, pr_type_impact_scope_determination_agent_node)
    workflow.add_node(pr_test_plan_generate_agent_name, pr_test_plan_generate_agent_node)
    # workflow.add_node(comment_on_pr_agent_name, comment_on_pr_agent_node)
    
    workflow.add_node("fetch_pr_nl_content_tools_node", ToolNode(fetch_pr_nl_content_tools))
    workflow.add_node("fetch_pr_code_content_tools_node", ToolNode(fetch_pr_code_content_tools))
    workflow.add_node("pr_type_impact_scope_determination_tools_node", ToolNode(pr_type_impact_scope_determination_tools))
    workflow.add_node("pr_test_plan_generate_tools_node", ToolNode(pr_test_plan_generate_tools))
    
    # workflow.add_node("comment_on_pr_tools_node", ToolNode(comment_on_pr_tools))

    def fetch_pr_nl_content_router(
        state,
    ) -> t.Literal["fetch_pr_nl_content_tools_node", "continue", "fetch_pr_code_content_node"]:
        messages = state["messages"]
        for message in reversed(messages):
            if isinstance(message, AIMessage):
                last_ai_message = message
                break
        else:
            last_ai_message = messages[-1]

        if last_ai_message.tool_calls:
            return "fetch_pr_nl_content_tools_node"
        if "PR CONTENT FETCHED AND TEST PLAN REMOVED" in last_ai_message.content:
            return "fetch_pr_code_content_node"
        return "continue"

    workflow.add_conditional_edges(
        "fetch_pr_nl_content_tools_node",
        lambda x: x["sender"],
        {fetch_pr_nl_content_agent_name: fetch_pr_nl_content_agent_name},
    )
    workflow.add_conditional_edges(
        fetch_pr_nl_content_agent_name,
        fetch_pr_nl_content_router,
        {
            "continue": fetch_pr_nl_content_agent_name,
            "fetch_pr_nl_content_tools_node": "fetch_pr_nl_content_tools_node",
            "fetch_pr_code_content_node": fetch_pr_code_content_agent_name,
        },
    )

    def fetch_pr_code_content_router(
        state,
    ) -> t.Literal["fetch_pr_code_content_tools_node", "continue", "pr_type_impact_scope_determination_node"]:
        messages = state["messages"]
        for message in reversed(messages):
            if isinstance(message, AIMessage):
                last_ai_message = message
                break
        else:
            last_ai_message = messages[-1]

        if last_ai_message.tool_calls:
            return "fetch_pr_code_content_tools_node"
        if "CODE CONTENT FETCHED AND FUNCTIONS EXTRACTED" in last_ai_message.content:
            return "pr_type_impact_scope_determination_node"
        return "continue"

    workflow.add_conditional_edges(
        "fetch_pr_code_content_tools_node",
        lambda x: x["sender"],
        {fetch_pr_code_content_agent_name: fetch_pr_code_content_agent_name},
    )
    workflow.add_conditional_edges(
        fetch_pr_code_content_agent_name,
        fetch_pr_code_content_router,
        {
            "continue": fetch_pr_code_content_agent_name,
            "fetch_pr_code_content_tools_node": "fetch_pr_code_content_tools_node",
            "pr_type_impact_scope_determination_node": pr_type_impact_scope_determination_agent_name,
        },
    )

    def pr_type_impact_scope_determination_router(
        state,
    ) -> t.Literal["pr_type_impact_scope_determination_tools_node", "continue", "pr_test_plan_generate_node"]:
        messages = state["messages"]
        for message in reversed(messages):
            if isinstance(message, AIMessage):
                last_ai_message = message
                break
        else:
            last_ai_message = messages[-1]

        if last_ai_message.tool_calls:
            return "pr_type_impact_scope_determination_tools_node"
        if "PR TYPE AND IMPACT SCOPE DETERMINED" in last_ai_message.content:
            return "pr_test_plan_generate_node"
        return "continue"

    workflow.add_conditional_edges(
        "pr_type_impact_scope_determination_tools_node",
        lambda x: x["sender"],
        {pr_type_impact_scope_determination_agent_name: pr_type_impact_scope_determination_agent_name},
    )
    workflow.add_conditional_edges(
        pr_type_impact_scope_determination_agent_name,
        pr_type_impact_scope_determination_router,
        {
            "continue": pr_type_impact_scope_determination_agent_name,
            "pr_type_impact_scope_determination_tools_node": "pr_type_impact_scope_determination_tools_node",
            "pr_test_plan_generate_node": pr_test_plan_generate_agent_name,
        },
    )

    def pr_test_plan_generate_router(
        state,
    ) -> t.Literal["pr_test_plan_generate_tools_node", "continue", "__end__"]:
        messages = state["messages"]
        for message in reversed(messages):
            if isinstance(message, AIMessage):
                last_ai_message = message
                break
        else:
            last_ai_message = messages[-1]

        if last_ai_message.tool_calls:
            return "pr_test_plan_generate_tools_node"
        
        if "TEST PLAN DRAFTED AND SUBMITTED" in last_ai_message.content:
            return "__end__"
        return "continue"

    workflow.add_conditional_edges(
        "pr_test_plan_generate_tools_node",
        lambda x: x["sender"],
        {pr_test_plan_generate_agent_name: pr_test_plan_generate_agent_name},
    )
    workflow.add_conditional_edges(
        pr_test_plan_generate_agent_name,
        pr_test_plan_generate_router,
        {
            "continue": pr_test_plan_generate_agent_name,
            "pr_test_plan_generate_tools_node": "pr_test_plan_generate_tools_node",
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
            "post": {
                Action.GITHUB_CREATE_AN_ISSUE_COMMENT: _github_pulls_create_review_comment_post_proc,
                Action.GITHUB_CREATE_A_REVIEW_COMMENT_FOR_A_PULL_REQUEST: _github_pulls_create_review_comment_post_proc,
                Action.GITHUB_LIST_COMMITS_ON_A_PULL_REQUEST: _github_list_commits_post_proc,
                Action.GITHUB_GET_A_COMMIT: _github_diff_post_proc,
                Action.GITHUB_GET_A_PULL_REQUEST: _github_get_a_pull_request_post_proc,
                Action.GITHUB_LIST_REVIEW_COMMENTS_ON_A_PULL_REQUEST: _github_list_review_comments_on_a_pull_request_post_proc,
            },
        },
    )
    fetch_pr_tools = [
        *toolset.get_tools(
            actions=[
                Action.GITHUB_GET_A_PULL_REQUEST,
                Action.GITHUB_LIST_COMMITS_ON_A_PULL_REQUEST,
                Action.GITHUB_GET_A_COMMIT,
                get_pr_diff,
                get_pr_metadata,
            ]
        )
    ]

    comment_on_pr_tools = [
        *toolset.get_tools(
            actions=[
                Action.GITHUB_CREATE_A_REVIEW_COMMENT_FOR_A_PULL_REQUEST,
            ]
        )
    ]
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

    fetch_pr_agent_name = "Fetch-PR-Agent"
    fetch_pr_agent = create_agent(PR_TEST_PLAN_FETCH_PROMPT, fetch_pr_tools)
    fetch_pr_agent_node = create_agent_node(fetch_pr_agent, fetch_pr_agent_name)

    comment_on_pr_agent_name = "Draft-Testplan-And-Comment-On-PR-Agent"
    comment_on_pr_agent = create_agent(PR_TEST_PLAN_GENERATOR_PROMPT, comment_on_pr_tools)
    comment_on_pr_agent_node = create_agent_node(comment_on_pr_agent, comment_on_pr_agent_name)

    workflow = StateGraph(AgentState)

    workflow.add_edge(START, fetch_pr_agent_name)
    workflow.add_node(fetch_pr_agent_name, fetch_pr_agent_node)
    workflow.add_node(comment_on_pr_agent_name, comment_on_pr_agent_node)
    
    workflow.add_node("fetch_pr_tools_node", ToolNode(fetch_pr_tools))
    workflow.add_node("comment_on_pr_tools_node", ToolNode(comment_on_pr_tools))

    def fetch_pr_router(
        state,
    ) -> t.Literal["fetch_pr_tools_node", "continue", "commnet_on_pr"]:
        messages = state["messages"]
        for message in reversed(messages):
            if isinstance(message, AIMessage):
                last_ai_message = message
                break
        else:
            last_ai_message = messages[-1]

        if last_ai_message.tool_calls:
            return "fetch_pr_tools_node"
        if "TEST PLAN INFO GATHERED" in last_ai_message.content:
            return "commnet_on_pr"
        return "continue"

    workflow.add_conditional_edges(
        "fetch_pr_tools_node",
        lambda x: x["sender"],
        {fetch_pr_agent_name: fetch_pr_agent_name},
    )
    workflow.add_conditional_edges(
        fetch_pr_agent_name,
        fetch_pr_router,
        {
            "continue": fetch_pr_agent_name,
            "fetch_pr_tools_node": "fetch_pr_tools_node",
            "commnet_on_pr": comment_on_pr_agent_name,
        },
    )

    def comment_on_pr_router(
        state,
    ) -> t.Literal["comment_on_pr_tools_node", "continue", "__end__"]:
        messages = state["messages"]
        for message in reversed(messages):
            if isinstance(message, AIMessage):
                last_ai_message = message
                break
        else:
            last_ai_message = messages[-1]

        if last_ai_message.tool_calls:
            return "comment_on_pr_tools_node"
        
        if "TEST PLAN DRAFTED" in last_ai_message.content:
            return "__end__"
        return "continue"

    workflow.add_conditional_edges(
        "comment_on_pr_tools_node",
        lambda x: x["sender"],
        {comment_on_pr_agent_name: comment_on_pr_agent_name},
    )
    workflow.add_conditional_edges(
        comment_on_pr_agent_name,
        comment_on_pr_router,
        {
            "continue": comment_on_pr_agent_name,
            "comment_on_pr_tools_node": "comment_on_pr_tools_node",
            "__end__": END,
        },
    )

    graph = workflow.compile()

    return graph, toolset

def get_graph_review(repo_path):
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
            "post": {
                Action.GITHUB_CREATE_AN_ISSUE_COMMENT: _github_pulls_create_review_comment_post_proc,
                Action.GITHUB_CREATE_A_REVIEW_COMMENT_FOR_A_PULL_REQUEST: _github_pulls_create_review_comment_post_proc,
                Action.GITHUB_LIST_COMMITS_ON_A_PULL_REQUEST: _github_list_commits_post_proc,
                Action.GITHUB_GET_A_COMMIT: _github_diff_post_proc,
                Action.GITHUB_GET_A_PULL_REQUEST: _github_get_a_pull_request_post_proc,
                Action.GITHUB_LIST_REVIEW_COMMENTS_ON_A_PULL_REQUEST: _github_list_review_comments_on_a_pull_request_post_proc,
            },
        },
    )

    fetch_pr_tools = [
        *toolset.get_tools(
            actions=[
                Action.GITHUB_GET_A_PULL_REQUEST,
                Action.GITHUB_LIST_COMMITS_ON_A_PULL_REQUEST,
                Action.GITHUB_GET_A_COMMIT,
                get_pr_diff,
                get_pr_metadata,
            ]
        )
    ]

    repo_analyzer_tools = [
        *toolset.get_tools(
            actions=[
                Action.CODE_ANALYSIS_TOOL_GET_CLASS_INFO,
                Action.CODE_ANALYSIS_TOOL_GET_METHOD_BODY,
                Action.CODE_ANALYSIS_TOOL_GET_METHOD_SIGNATURE,
                # Action.FILETOOL_LIST_FILES,
                Action.FILETOOL_OPEN_FILE,
                Action.FILETOOL_SCROLL,
                # Action.FILETOOL_FIND_FILE,
                Action.FILETOOL_SEARCH_WORD,
            ]
        )
    ]

    comment_on_pr_tools = [
        *toolset.get_tools(
            actions=[
                Action.GITHUB_GET_A_COMMIT,
                Action.GITHUB_CREATE_A_REVIEW_COMMENT_FOR_A_PULL_REQUEST,
                Action.GITHUB_CREATE_AN_ISSUE_COMMENT,
            ]
        )
    ]

    if model == Model.CLAUDE:
        client = ChatBedrock(
            credentials_profile_name="default",
            model_id="anthropic.claude-3-5-sonnet-20240620-v1:0",
            region_name="us-east-1",
            model_kwargs={"temperature": 0, "max_tokens": 8192},
        )
    else:
        client = ChatOpenAI(
            model="gpt-4o-mini",
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

    fetch_pr_agent_name = "Fetch-PR-Agent"
    fetch_pr_agent = create_agent(PR_FETCHER_PROMPT, fetch_pr_tools)
    fetch_pr_agent_node = create_agent_node(fetch_pr_agent, fetch_pr_agent_name)

    repo_analyzer_agent_name = "Repo-Analyzer-Agent"
    repo_analyzer_agent = create_agent(REPO_ANALYZER_PROMPT, repo_analyzer_tools)
    repo_analyzer_agent_node = create_agent_node(repo_analyzer_agent, repo_analyzer_agent_name)

    comment_on_pr_agent_name = "Comment-On-PR-Agent"
    comment_on_pr_agent = create_agent(PR_COMMENT_PROMPT, comment_on_pr_tools)
    comment_on_pr_agent_node = create_agent_node(comment_on_pr_agent, comment_on_pr_agent_name)

    workflow = StateGraph(AgentState)

    workflow.add_edge(START, fetch_pr_agent_name)
    workflow.add_node(fetch_pr_agent_name, fetch_pr_agent_node)
    workflow.add_node(repo_analyzer_agent_name, repo_analyzer_agent_node)
    workflow.add_node(comment_on_pr_agent_name, comment_on_pr_agent_node)
    
    workflow.add_node("fetch_pr_tools_node", ToolNode(fetch_pr_tools))
    workflow.add_node("repo_analyzer_tools_node", ToolNode(repo_analyzer_tools))
    workflow.add_node("comment_on_pr_tools_node", ToolNode(comment_on_pr_tools))

    def fetch_pr_router(
        state,
    ) -> t.Literal["fetch_pr_tools_node", "continue", "analyze_repo"]:
        messages = state["messages"]
        for message in reversed(messages):
            if isinstance(message, AIMessage):
                last_ai_message = message
                break
        else:
            last_ai_message = messages[-1]

        if last_ai_message.tool_calls:
            return "fetch_pr_tools_node"
        if "ANALYZE REPO" in last_ai_message.content:
            return "analyze_repo"
        return "continue"

    workflow.add_conditional_edges(
        "fetch_pr_tools_node",
        lambda x: x["sender"],
        {fetch_pr_agent_name: fetch_pr_agent_name},
    )
    workflow.add_conditional_edges(
        fetch_pr_agent_name,
        fetch_pr_router,
        {
            "continue": fetch_pr_agent_name,
            "fetch_pr_tools_node": "fetch_pr_tools_node",
            "analyze_repo": repo_analyzer_agent_name,
        },
    )

    def repo_analyzer_router(
        state,
    ) -> t.Literal["repo_analyzer_tools_node", "continue", "comment_on_pr"]:
        messages = state["messages"]
        for message in reversed(messages):
            if isinstance(message, AIMessage):
                last_ai_message = message
                break
        else:
            last_ai_message = messages[-1]

        if last_ai_message.tool_calls:
            return "repo_analyzer_tools_node"
        if "ANALYSIS COMPLETED" in last_ai_message.content:
            return "comment_on_pr"
        return "continue"

    workflow.add_conditional_edges(
        "repo_analyzer_tools_node",
        lambda x: x["sender"],
        {repo_analyzer_agent_name: repo_analyzer_agent_name},
    )
    workflow.add_conditional_edges(
        repo_analyzer_agent_name,
        repo_analyzer_router,
        {
            "continue": repo_analyzer_agent_name,
            "repo_analyzer_tools_node": "repo_analyzer_tools_node",
            "comment_on_pr": comment_on_pr_agent_name,
        },
    )

    def comment_on_pr_router(
        state,
    ) -> t.Literal["comment_on_pr_tools_node", "continue", "analyze_repo", "__end__"]:
        messages = state["messages"]
        for message in reversed(messages):
            if isinstance(message, AIMessage):
                last_ai_message = message
                break
        else:
            last_ai_message = messages[-1]

        if last_ai_message.tool_calls:
            return "comment_on_pr_tools_node"
        if "ANALYZE REPO" in last_ai_message.content:
            return "analyze_repo"
        if "REVIEW COMPLETED" in last_ai_message.content:
            return "__end__"
        return "continue"

    workflow.add_conditional_edges(
        "comment_on_pr_tools_node",
        lambda x: x["sender"],
        {comment_on_pr_agent_name: comment_on_pr_agent_name},
    )
    workflow.add_conditional_edges(
        comment_on_pr_agent_name,
        comment_on_pr_router,
        {
            "continue": comment_on_pr_agent_name,
            "analyze_repo": repo_analyzer_agent_name,
            "comment_on_pr_tools_node": "comment_on_pr_tools_node",
            "__end__": END,
        },
    )

    graph = workflow.compile()

    return graph, toolset
