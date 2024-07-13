from typing import Annotated, Literal

Operator = Literal["+", "-", "*", "/"]
import sys
import os

# 获取当前脚本所在目录的上级目录的绝对路径
parent_dir = os.path.dirname(os.path.abspath(__file__))
grand_parent_dir = os.path.dirname(parent_dir)

# 将上级目录添加到Python的搜索路径中
sys.path.insert(0, grand_parent_dir)
from load_env import load_env

load_env()


from pydantic import BaseModel, Field


class CalculatorInput(BaseModel):
    a: Annotated[int, Field(description="The first number.")]
    b: Annotated[int, Field(description="The second number.")]
    operator: Annotated[Operator, Field(description="The operator.")]


def calculator(input: Annotated[CalculatorInput, "Input to the calculator."]) -> int:
    if input.operator == "+":
        return input.a + input.b
    elif input.operator == "-":
        return input.a - input.b
    elif input.operator == "*":
        return input.a * input.b
    elif input.operator == "/":
        return int(input.a / input.b)
    else:
        raise ValueError("Invalid operator")


import os

from autogen import ConversableAgent

# Let's first define the assistant agent that suggests tool calls.
assistant = ConversableAgent(
    name="Assistant",
    system_message="You are a helpful AI assistant. "
                   "You can help with simple calculations. "
                   "Return 'TERMINATE' when the task is done.",
    llm_config={"config_list": [{"model": "gpt-3.5-turbo-0125", "api_key": os.environ["OPENAI_API_KEY"],
                                 "price": [0.00365, 0.0146]}]},
)

# The user proxy agent is used for interacting with the assistant agent
# and executes tool calls.
user_proxy = ConversableAgent(
    name="User",
    llm_config=False,
    human_input_mode="ALWAYS",
)

# Register the tool signature with the assistant agent.
assistant.register_for_llm(name="calculator", description="A calculator tool that accepts nested expression as input")(
    calculator
)

# Register the tool function with the user proxy agent.
user_proxy.register_for_execution(name="calculator")(calculator)

from autogen import register_function

# Register the calculator function to the two agents.
register_function(
    calculator,
    caller=assistant,  # The assistant agent can suggest calls to the calculator.
    executor=user_proxy,  # The user proxy agent can execute the calculator calls.
    name="calculator",  # By default, the function name is used as the tool name.
    description="A simple calculator",  # A description of the tool.
)
chat_result = user_proxy.initiate_chat(assistant, message="What is 6 * 81 + 78")
print(chat_result)
