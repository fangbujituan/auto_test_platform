"""
检查 Middleware 中间件属性

运行: python shell/check_middleware.py
"""

from langchain.agents.middleware import AgentMiddleware, SummarizationMiddleware
import inspect

print("=" * 80)
print("AgentMiddleware 基类分析")
print("=" * 80)

print("\nAgentMiddleware 签名:")
print(inspect.signature(AgentMiddleware.__init__))

print("\nAgentMiddleware 方法:")
for name in dir(AgentMiddleware):
    if not name.startswith('_'):
        print(f"  {name}")

print("\nAgentMiddleware 属性:")
for name in dir(AgentMiddleware):
    if name.startswith('_') and not name.startswith('__'):
        print(f"  {name}")

print("\n" + "=" * 80)
print("SummarizationMiddleware 分析")
print("=" * 80)

print("\nSummarizationMiddleware 签名:")
print(inspect.signature(SummarizationMiddleware.__init__))

print("\nSummarizationMiddleware 方法:")
for name in dir(SummarizationMiddleware):
    if not name.startswith('_'):
        print(f"  {name}")

print("\nSummarizationMiddleware 属性:")
for name in dir(SummarizationMiddleware):
    if name.startswith('_') and not name.startswith('__'):
        print(f"  {name}")

print("\n" + "=" * 80)
print("wrap_tool_call 检查")
print("=" * 80)

print(f"\nAgentMiddleware.wrap_tool_call: {hasattr(AgentMiddleware, 'wrap_tool_call')}")
print(f"SummarizationMiddleware.wrap_tool_call: {hasattr(SummarizationMiddleware, 'wrap_tool_call')}")

if hasattr(AgentMiddleware, 'wrap_tool_call'):
    print(f"\nAgentMiddleware.wrap_tool_call type: {type(getattr(AgentMiddleware, 'wrap_tool_call'))}")
