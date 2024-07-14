import os
import sys
from typing import *

from pydantic import BaseModel, Field
import argparse

ignore_paths = ["/.git", "/.classes.tmp", "/target", "/.idea"]
project_parser = argparse.ArgumentParser(description="Command in project")
subparsers = project_parser.add_subparsers(dest="subcommand")  # save subcommands in "args.subcommand"

all_files_parser = subparsers.add_parser("all_files", help="Show all files in project")


class Project:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self._files = []
        for path, dirs, files in os.walk(base_dir):
            ignore = False
            for ignore_path in ignore_paths:
                if path.removeprefix(base_dir).startswith(ignore_path):
                    ignore = True
                    break
            if ignore:
                continue
            for f in files:
                self._files.append(os.path.join(path.replace(base_dir, ''), f))
        if len(self._files) == 0:
            raise Exception(f"No files found in {base_dir}")

    def content_of_file(self, file_path: Annotated[str, "The path of the file to be opened. e.g. "
                                                        "org/jetbrains/java/PsiClass.java"]
                        ) -> str:
        for f_name in self._files:
            if f_name.endswith(file_path):
                file_path = self.base_dir + f_name if f_name.startswith("/") else os.path.join(self.base_dir, f_name)
                with open(file_path, "r") as f:
                    return f.read()
        raise FileNotFoundError(f"No such file {file_path}")

    def all_files(self) -> List[str]:
        return self._files

    def command(self, cmd: Annotated[str, "The command to be executed. e.g. all_files. Type -h show help"]) -> str:
        _args = project_parser.parse_args(cmd.split(" "))
        if _args.subcommand == "all_files":
            return "\n".join(self.all_files())


def test_content_of_file(_project: Project) -> None:
    from autogen import ConversableAgent

    # Let's first define the assistant agent that suggests tool calls.
    assistant = ConversableAgent(
        name="Assistant",
        system_message="You are a file manager. "
                       "You can help look content of files. "
                       "Return 'TERMINATE' when the task is done.",
        llm_config={"config_list": [{"model": "gpt-3.5-turbo-0125", "api_key": os.environ["OPENAI_API_KEY"],
                                     "price": [0.00365, 0.0146]}]},
    )

    # The user proxy agent is used for interacting with the assistant agent
    # and executes tool calls.
    user_proxy = ConversableAgent(
        name="User",
        llm_config=False,
        # is_termination_msg=lambda msg: msg.startswith("TERMINATE"),
        human_input_mode="NEVER",
    )
    from functools import partial
    from autogen import register_function

    # Register the calculator function to the two agents.
    register_function(
        partial(_project.content_of_file),
        caller=assistant,  # The assistant agent can suggest calls to the calculator.
        executor=user_proxy,  # The user proxy agent can execute the calculator calls.
        name="content_of_file",  # By default, the function name is used as the tool name.
        description="A tool that show the content of specified file.",  # A description of the tool.
    )
    register_function(
        partial(_project.command),
        caller=assistant,  # The assistant agent can suggest calls to the calculator.
        executor=user_proxy,  # The user proxy agent can execute the calculator calls.
        name="command",  # By default, the function name is used as the tool name.
        description="A tool that execute command such \"all_files\" to show all file names in project",
        # A description of the tool.
    )
    chat_result = user_proxy.initiate_chat(
        assistant,
        message="How many files in this project?",
        max_turns=4
    )
    print(chat_result)


def test_command(_project: Project) -> None:
    _project.command("-h")


if __name__ == '__main__':
    import os
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--base-dir", help="base dir of the project", required=True)
    args = parser.parse_args()
    project = Project(args.base_dir)
    # print(project.content_of_file("org/apache/commons/lang3/math/NumberUtils.java"))

    # 获取当前脚本所在目录的上级目录的绝对路径
    parent_dir = os.path.dirname(os.path.abspath(__file__))
    grand_parent_dir = os.path.dirname(parent_dir)

    # 将上级目录添加到Python的搜索路径中
    sys.path.insert(0, grand_parent_dir)
    from load_env import load_env

    load_env()

    # test_content_of_file(project)
    test_command(project)
