import json
from langchain_core.messages.ai import AIMessage

class AIMessageEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, AIMessage):
            return {
                "content": obj.content,
                "tool_calls": obj.tool_calls,
                "invalid_tool_calls": obj.invalid_tool_calls,
                "usage_metadata": obj.usage_metadata,
                # 添加其他需要序列化的属性
            }
        return super().default(obj)

