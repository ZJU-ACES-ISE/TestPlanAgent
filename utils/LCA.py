import networkx as nx

def build_dominator_tree(graph, entry):
    """
    构建支配树
    :param graph: 有向无环图
    :param entry: 入口节点
    :return: 支配树
    """
    # 计算支配关系
    dominators = nx.immediate_dominators(graph, entry)
    # 构建支配树
    dom_tree = nx.DiGraph()
    for node, dom in dominators.items():
        if node != entry:
            dom_tree.add_edge(dom, node)
    return dom_tree

def dfs_order(tree, start):
    """
    计算树的 DFS 序
    :param tree: 树
    :param start: 起始节点
    :return: DFS 序字典
    """
    dfs_order_dict = {}
    index = 0
    def dfs(node):
        nonlocal index
        dfs_order_dict[node] = index
        index += 1
        for child in tree.successors(node):
            dfs(child)
    dfs(start)
    return dfs_order_dict

def find_lca_in_dom_tree(func_names, dom_tree, dfs_order_dict):
    """
    在支配树上找到 DFS 序最小和最大的节点的 LCA
    :param func_names: 函数名称列表
    :param dom_tree: 支配树
    :param dfs_order_dict: DFS 序字典
    :return: 最近公共祖先
    """
    min_dfs_index = float('inf')
    max_dfs_index = float('-inf')
    min_dfs_node = None
    max_dfs_node = None

    for func in func_names:
        if func in dfs_order_dict:
            index = dfs_order_dict[func]
            if index < min_dfs_index:
                min_dfs_index = index
                min_dfs_node = func
            if index > max_dfs_index:
                max_dfs_index = index
                max_dfs_node = func

    if min_dfs_node is None or max_dfs_node is None:
        return None

    # 找到最小和最大 DFS 序节点的 LCA
    ancestors_min = set(nx.ancestors(dom_tree, min_dfs_node))
    ancestors_min.add(min_dfs_node)
    ancestors_max = set(nx.ancestors(dom_tree, max_dfs_node))
    ancestors_max.add(max_dfs_node)
    common_ancestors = ancestors_min.intersection(ancestors_max)

    # 找到最近的公共祖先
    max_depth = -1
    lca = None
    for ancestor in common_ancestors:
        depth = len(nx.shortest_path(dom_tree, source=list(dom_tree.nodes())[0], target=ancestor))
        if depth > max_depth:
            max_depth = depth
            lca = ancestor

    return lca

def find_lca(func_names, graph):
    """
    主函数，找到函数的最近公共祖先
    :param func_names: 函数名称列表
    :param graph: 有向无环图
    :return: 最近公共祖先
    """
    # 假设图的第一个节点为入口节点
    entry = list(graph.nodes())[0]
    # 构建支配树
    dom_tree = build_dominator_tree(graph, entry)
    # 计算 DFS 序
    dfs_order_dict = dfs_order(dom_tree, entry)
    # 找到 LCA
    return find_lca_in_dom_tree(func_names, dom_tree, dfs_order_dict)

# 示例代码知识图
graph = nx.DiGraph()
graph.add_edges_from([
    ('func1', 'func2'),
    ('func1', 'func3'),
    ('func1', 'func4'),
    ('func2', 'func5'),
    ('func2', 'func6'),
    ('func3', 'func7'),
    ('func3', 'func8'),
    ('func7', 'func9'),
    ('func7', 'func10'),
])

# 示例函数名称
func_names = ['func5', 'func10', 'func9']
result = find_lca(func_names, graph)
print(f"最近公共祖先: {result}")