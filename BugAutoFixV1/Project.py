import os
import subprocess
import sys
from typing import *

import dotenv
from dotenv import load_dotenv, find_dotenv
from pydantic import BaseModel, Field
import argparse

_ = load_dotenv(find_dotenv())

ignore_paths = ["/.git", "/.classes.tmp", "/target", "/.idea"]
project_parser = argparse.ArgumentParser(description="Command in project", exit_on_error=False)
subparsers = project_parser.add_subparsers(dest="subcommand")  # save subcommands in "args.subcommand"

all_files_parser = subparsers.add_parser("all_files", help="Show all files in project")
count_files_parser = subparsers.add_parser("count_files", help="Count all files in project")
run_test_parser = subparsers.add_parser("run_test", help="Run test in project, return value is test result."
                                                         "After running test, use 'failed_test' to check test that "
                                                         "failed")
failed_test_parser = subparsers.add_parser("failed_test", help="Show failed test. Must use after run 'run_test'")
D4J_RELEVANT = "d4j.classes.relevant"
D4J_EXEC = os.environ.get("DEFECTS4J_EXEC")
D4J_FAILING_TEST = "failing_tests"


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
        _d4j_file_name = os.path.join(base_dir, "defects4j.build.properties")
        if not os.path.exists(_d4j_file_name):
            raise FileNotFoundError("No defects4j.build.properties file found")
        self._d4j_configs = dotenv.dotenv_values(_d4j_file_name)
        self._relevant_classes = self._d4j_configs.get(D4J_RELEVANT)

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

    def run_test(self):
        result = subprocess.run(f"{D4J_EXEC} test -r", shell=True,
                                stderr=subprocess.PIPE, stdout=subprocess.PIPE, cwd=self.base_dir)
        stdout = result.stdout.decode("utf-8")
        stderr = result.stderr.decode("utf-8")
        failed_count = int(stdout.splitlines()[0].split(":")[-1].strip())
        if failed_count:
            return stdout
        else:
            return "success"

    def failed_test(self):
        _failing_file = os.path.join(self.base_dir, D4J_FAILING_TEST)
        if not os.path.exists(_failing_file):
            raise FileNotFoundError(_failing_file)
        with open(_failing_file, "r") as f:
            return f.read()

    def command(self, cmd: Annotated[str, "The command to be executed. Type -h show help"]) -> str:
        try:
            _args, _unknown = project_parser.parse_known_args(cmd.split(" "))
        except SystemExit:
            return project_parser.format_help()
        if _args.subcommand == "all_files":
            return "\n".join(self.all_files())
        elif _args.subcommand == "count_files":
            return str(len(self.all_files()))
        elif _args.subcommand == "run_test":
            return self.run_test()
        elif _args.subcommand == "failed_test":
            return self.failed_test()


def test_llm(_project: Project) -> None:
    from autogen import ConversableAgent

    # Let's first define the assistant agent that suggests tool calls.
    assistant = ConversableAgent(
        name="Assistant",
        system_message="You are a project manager. "
                       "You can manage Java project. "
                       "You cannot run command directly, you can only use some pre-defined commands",
                       # "Return 'TERMINATE' when the task is done.",
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
        description="A tool that execute **custom** commands (**Not** a shell)." + project_parser.format_help(),
        # A description of the tool.
    )
    chat_result = user_proxy.initiate_chat(
        assistant,
        message="Run test in project and tell me which test failed",
        max_turns=4
    )
    print(chat_result)


def test_command(_project: Project) -> None:
    _project.command("-h")


def test_run_test(_project: Project) -> None:
    _project.run_test()


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

    test_llm(project)
    # test_command(project)
    # test_run_test(project)
