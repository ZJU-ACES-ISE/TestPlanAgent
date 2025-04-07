from tasks.ReAct import ReAct
from tasks.TOT import TOT
from tasks.Embedding import Embedding
from tasks.Judge import Judge
class TaskFactory:
    """
    基于策略创建任务实例的工厂课程。
    """
    
    @staticmethod
    def create_task(config, task_type="generator", test_plan_path=None):
        """
        基于配置中指定的策略创建一个任务实例。
        
        Args:
            config (dict): 任务的配置字典
            
        Returns:
            BaseTask: 任务类的实例
            
        Raises:
            ValueError: 如果未确认策略
        """

        if task_type == "judge":
            return Judge(config, test_plan_path)
        
        # Otherwise create a generator task based on strategy
        if task_type != "generator":
            print(f"Warning: Unknown task type '{task_type}'. Defaulting to 'generator'.")
        
        strategy = config['Agent']['strategy']
        
        if strategy == 'InOut':
            # InOut is not implemented yet
            raise ValueError("InOut strategy is not implemented yet")
        elif strategy == 'Embedding':
            return Embedding(config)
        elif strategy == 'ReAct':
            return ReAct(config)
        elif strategy == 'TOT':
            return TOT(config)
        else:
            raise ValueError(f"Unknown strategy: {strategy}")