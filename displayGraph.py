
from agent.agent import get_graph_testplan
from utils.inputs import from_github

def main() -> None:
    """Run the agent."""
    _, repo_name, _ = from_github()

    repo_path = f"/home/veteran/projects/multiAgent/{repo_name}"

    graph, _= get_graph_testplan(repo_path)

    try:
        graph_path = "/home/veteran/projects/multiAgent/TestPlanAgent/result/pr_testplan_agent_graph.png"
        graph.get_graph().draw_png(graph_path)
    except Exception as e:
        print(f"Error in drawing graph : {e}")

if __name__ == "__main__":
    main()