import os
import subprocess
import sys
import uuid
from typing import *

import dotenv
from dotenv import load_dotenv, find_dotenv
from pydantic import BaseModel, Field
import argparse
import javalang

_ = load_dotenv(find_dotenv())

ignore_paths = ["/.git", "/.classes.tmp", "/target", "/.idea"]
project_parser = argparse.ArgumentParser(description="Command in project", exit_on_error=False)
subparsers = project_parser.add_subparsers(dest="subcommand")  # save subcommands in "args.subcommand"

all_files_parser = subparsers.add_parser("all_files", help="Show all files in project")
count_files_parser = subparsers.add_parser("count_files", help="Count all files in project")
run_test_parser = subparsers.add_parser("run_test", help="Run test in project, return value is test result.")
# undo_all_parser = subparsers.add_parser("undo_all", help="Undo all changes.")
D4J_RELEVANT_KEY = "d4j.classes.relevant"
D4J_SRC_PATH_KEY = "d4j.dir.src.classes"
D4J_TEST_PATH_KEY = "d4j.dir.src.tests"
D4J_TRIGGER_KEY = "d4j.tests.trigger"
D4J_EXEC = os.environ.get("DEFECTS4J_EXEC")
if not D4J_EXEC:
    raise Exception("D4J_EXEC env variable is not set")
D4J_FAILING_TEST = "failing_tests"
DEBUG_LOG_NAME = "bugDetect.log"


class Project:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self._files = []
        self.undo_all_files()
        _d4j_file_name = os.path.join(base_dir, "defects4j.build.properties")
        if not os.path.exists(_d4j_file_name):
            raise FileNotFoundError("No defects4j.build.properties file found")
        self._d4j_configs = dotenv.dotenv_values(_d4j_file_name)
        self._relevant_classes = self._d4j_configs.get(D4J_RELEVANT_KEY).split(",")
        self._src_path = self._d4j_configs.get(D4J_SRC_PATH_KEY)
        self._test_path = self._d4j_configs.get(D4J_TEST_PATH_KEY)
        self._trigger_test_methods = self._d4j_configs.get(D4J_TRIGGER_KEY)
        self._trigger_tests = [self._trigger_test_methods.split("::")[0]
                               for _test_method in self._trigger_test_methods.split(",")]
        for path, dirs, files in os.walk(base_dir):
            ignore = False
            for ignore_path in ignore_paths:
                if path.removeprefix(base_dir).startswith(ignore_path):
                    ignore = True
                    break
            if ignore:
                continue
            for f in files:
                if f.endswith(".java"):
                    _f_path = os.path.join(path.replace(base_dir, ''), f)
                    _class_name = (_f_path.removesuffix(".java").removesuffix("/").removeprefix("/")
                                   .removeprefix(self._src_path).removeprefix(self._test_path)
                                   .removesuffix("/").removeprefix("/")
                                   .replace("/", "."))
                    if _class_name in self._relevant_classes or _class_name in self._trigger_tests:
                        self._files.append(_f_path)
        if len(self._files) == 0:
            raise Exception(f"No files found in {base_dir}")

    def trigger_test_methods(self):
        return self._trigger_test_methods

    def _find_file(self, file: str) -> str:
        for f_name in self._files:
            if f_name.endswith(file) or f_name.replace("/java", "").endswith(file):
                file_path = self.base_dir + f_name if f_name.startswith("/") else os.path.join(self.base_dir, f_name)
                return file_path
        raise FileNotFoundError(f"No such file {file}")

    def content_of_file(self, file_path: Annotated[str, "The path of the file to be opened. e.g. "
                                                        "org/jetbrains/java/PsiClass.java"]
                        ) -> str:
        file_path = self._find_file(file_path)
        with open(file_path, "r") as f:
            return f.read()

    def content_of_method(
            self,
            file_path: Annotated[str, "The path of the file to be opened. e.g. org/jetbrains/java/PsiClass.java"],
            class_name: Annotated[str, "The class name which contains the method you want."],
            method_name: Annotated[str, "The method name."]
    ) -> str:
        _content = self.content_of_file(file_path)
        _tree = javalang.parse.parse(_content)
        class_name = class_name.split(".")[-1]
        _classes = [clazz for clazz in _tree.types if clazz.name == class_name]
        if len(_classes) == 0:
            raise Exception(f"No class named {class_name} in {file_path}")
        _class = _classes[0]
        _methods = [method for method in _class.methods if method.name == method_name]
        if len(_methods) == 0:
            raise Exception(f"No method named {method_name} in {file_path}")
        _method = _methods[0]
        _content_lines = _content.splitlines()
        _start_line = _method.position.line - 1
        _end_line = min(_method.body[-1].position.line + 2, len(_content_lines))
        _result_lines = _content_lines[_start_line:_end_line]
        _result = ""
        for index, line in enumerate(_result_lines):
            _result += line + "// line " + str(index + _start_line + 1) + "\n"
        return _result

    def modify_file(
            self,
            file_path: Annotated[str, "Path of file to change."],
            start_line: Annotated[int, "Start line number to replace with new code."],
            end_line: Annotated[int, "End line number to replace with new code."],
            new_code: Annotated[str, "New piece of code to replace old code with. Remember about providing indents."],
    ) -> str:
        if "test" in file_path or "Test" in file_path:
            raise Exception("Test files can not be modified")
        file_path = self._find_file(file_path)
        with open(file_path, "r+") as file:
            file_contents = file.readlines()
            file_contents[start_line - 1: end_line] = [new_code + "\n"]
            file.seek(0)
            file.truncate()
            file.write("".join(file_contents))
        return "modify success"

    def replace_file(self, file_path: Annotated[str, "The path of the file to be modified."],
                     old_content: Annotated[str, "The old content to be modified"],
                     new_content: Annotated[str, "The content of the modified file."]) -> str:
        if "test" in file_path or "Test" in file_path:
            raise Exception("Test files can not be modified")
        file_path = self._find_file(file_path)
        with open(file_path, "r") as f:
            text = f.read()
        text.replace(old_content, new_content)
        with open(file_path, "w") as f:
            f.write(text)
        return "replace success"

    def undo_all_files(self):
        subprocess.run("git reset HEAD --hard", shell=True,
                       stderr=subprocess.PIPE, stdout=subprocess.PIPE, cwd=self.base_dir)
        return "undo all success"

    def all_files(self) -> List[str]:
        return self._files

    def run_test(self):
        # noinspection PyBroadException
        try:
            os.remove(os.path.join(self.base_dir, D4J_FAILING_TEST))
        except Exception as _:
            pass
        # noinspection PyBroadException
        try:
            os.remove(os.path.join(self.base_dir, DEBUG_LOG_NAME))
        except Exception as _:
            pass
        result = subprocess.run(f"{D4J_EXEC} test -r", shell=True,
                                stderr=subprocess.PIPE, stdout=subprocess.PIPE, cwd=self.base_dir)
        stdout = result.stdout.decode("utf-8")
        stderr = result.stderr.decode("utf-8")
        if stdout == "":
            lines = stderr.splitlines()
            result_lines = []
            for line in lines:
                if "[javac]" in line:
                    result_lines.append(line.replace(self.base_dir, ""))
            _result = "\n".join(result_lines)
            if len(_result) > 4096:
                _result = _result[:4096]
            return _result
        failed_count = int(stdout.splitlines()[0].split(":")[-1].strip())
        if failed_count:
            return self.failed_test()
        else:
            return "success"

    def failed_test(self):
        _failing_file = os.path.join(self.base_dir, D4J_FAILING_TEST)
        if not os.path.exists(_failing_file):
            raise FileNotFoundError(_failing_file)
        with open(_failing_file, "r") as f:
            _lines = f.read().splitlines()
        _result_lines = []
        _this_test_end = False
        for line in _lines:
            if line.startswith("---"):
                _this_test_end = False
            if line.endswith("(Native Method)"):
                _this_test_end = True
            if not _this_test_end:
                _result_lines.append(line)
        return "\n".join(_result_lines)

    def debug_info(
            self, test_class_name: Annotated[str, "The test class name. "
                                                  "e.g. org.apache.commons.lang3.math.NumberUtilsTest"],
            method_name: Annotated[str, "The test method name. e.g. testMethod"],
            start_line: Annotated[int, "The line in specified method that debug info start."
                                       " -1 means start at the beginning of the method."] = -1,
            end_line: Annotated[int, "The line in specified method that debug info end. "
                                     "-1 means end at the end of the method."] = -1,
    ) -> str:
        _result_list = []
        with open(os.path.join(self.base_dir, DEBUG_LOG_NAME), "r") as f:
            lines = f.read().splitlines()
        _started = False
        for line in lines:
            if line.startswith("----------") and line.endswith("----------"):
                continue
            if line.startswith(f"{test_class_name}:{method_name}"):
                if start_line != -1:
                    if line.removeprefix(f"{test_class_name}:{method_name}:") == str(start_line):
                        _started = True
                else:
                    _started = True
                if _started and end_line != -1 \
                        and int(line.removeprefix(f"{test_class_name}:{method_name}:")) > end_line:
                    # should end when current line gt end_line
                    break
            elif (_started and
                  (line.startswith(test_class_name) or  # Other method line
                   (not line.startswith("{") and line.split(":")[0].endswith("Test")))):  # other Test class
                break
            if _started:
                _result_list.append(line)
        if len(_result_list) == 0:
            raise Exception("No such debug info found! Run all tests to generate debug info.")
        return "\n".join(_result_list)

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
        elif _args.subcommand == "undo_all":
            return self.undo_all_files()


def test_group_chat(_project: Project) -> None:
    import autogen
    from autogen import ConversableAgent, GroupChat, GroupChatManager, \
        register_function
    from functools import partial

    llm_config = {"config_list": [{"model": "gpt-3.5-turbo", "api_key": os.environ["OPENAI_API_KEY"],
                                   "price": [0.00365, 0.0146]}],
                  "cache_seed": None}
    bug_fixer = ConversableAgent(
        name="Bug fixer",
        system_message="You are a bug fixer. Your goal is to pass all the test in the project."
                       "You can ask your assistants to interpret the program",
        llm_config=llm_config
    )
    testcase_explainer = ConversableAgent(
        name="Testcase explainer",
        system_message="You are a testcase explainer. Your goal is to explain testcases in the project and help"
                       "bug fixer to pass all the test in the project.",
        llm_config=llm_config
    )
    programming_assistant = ConversableAgent(
        name="Programming assistant",
        system_message="You are a programming assistant. Your goal is to help bug fixer edit the files in the project.",
        llm_config=llm_config
    )
    command_executor = ConversableAgent(
        name="Command executor",
        llm_config=False,
        # is_termination_msg=lambda msg: msg.startswith("TERMINATE"),
        human_input_mode="NEVER",
    )
    group_chat = GroupChat(
        agents=[bug_fixer, testcase_explainer, programming_assistant, command_executor],
        messages=[],
        max_round=6,
    )
    group_chat_manager = GroupChatManager(
        groupchat=group_chat,
        llm_config=False,
        human_input_mode="ALWAYS"
    )

    def auto_reply_function(recipient, messages, sender, config):
        if "callback" in config and config["callback"] is not None:
            callback = config["callback"]
            callback(sender, recipient, messages[-1])
        return True, "No command to execute!"  # required to ensure the agent communication flow continues

    command_executor.register_reply(
        [autogen.Agent, None],
        reply_func=auto_reply_function,
        config={"callback": None},
        position=-1,
    )
    content_of_method_description = "A tool that shows the content of method. " \
                                    "Source methods and test methods are both supported." \
                                    "If there is an error here, it may mean that your " \
                                    "last modification cases a compile error, try to redo your modification."
    content_of_method_f = partial(_project.content_of_method)
    testcase_explainer.register_for_llm(name="content_of_method",
                                        description=content_of_method_description)(content_of_method_f)
    bug_fixer.register_for_llm(name="content_of_method",
                               description=content_of_method_description)(content_of_method_f)
    command_executor.register_for_execution(name="content_of_method")(content_of_method_f)
    register_function(
        partial(_project.command),
        caller=programming_assistant,  # The assistant agent can suggest calls to the calculator.
        executor=command_executor,  # The user proxy agent can execute the calculator calls.
        name="command",  # By default, the function name is used as the tool name.
        description="A tool that execute **custom** commands (**Not** a shell)." + project_parser.format_help(),
        # A description of the tool.
    )
    register_function(
        partial(_project.debug_info),
        caller=bug_fixer,  # The assistant agent can suggest calls to the calculator.
        executor=command_executor,  # The user proxy agent can execute the calculator calls.
        name="debug_info",  # By default, the function name is used as the tool name.
        description="A tool that can show debug information of last test. "
                    "You can choose start line and end line from a test method.",
    )

    chat_result = command_executor.initiate_chat(
        group_chat_manager,
        message="Fix the bug(s) in this project. Your goal is to pass all the tests in the project."
    )
    print(chat_result)


def test_llm(_project: Project) -> None:
    from autogen import ConversableAgent

    # Let's first define the assistant agent that suggests tool calls.
    assistant = ConversableAgent(
        name="Assistant",
        system_message="You are a bug locator, "
                       "and your goal is to **locate (not fix)** the buggy method or the buggy line. "
                       "Note that bugs may not necessarily occur at the location of the exception, "
                       "and may be caused by code implementation that does not match the expected situation",
        # "Use 'run_test' tool to run tests after your fix."
        # "You **cannot modify test cases** during repair, nor can you do hard coding.",
        # "Return 'TERMINATE' when the task is done.",
        llm_config={"config_list": [{"model": "gpt-3.5-turbo", "api_key": os.environ["OPENAI_API_KEY"],
                                     "price": [0.00365, 0.0146]}],
                    "cache_seed": None},
    )

    # The user proxy agent is used for interacting with the assistant agent
    # and executes tool calls.
    user_proxy = ConversableAgent(
        name="User",
        llm_config=False,
        # is_termination_msg=lambda msg: msg.startswith("TERMINATE"),
        human_input_mode="NEVER",
    )

    def auto_reply_function(recipient, messages, sender, config):
        if "callback" in config and config["callback"] is not None:
            callback = config["callback"]
            callback(sender, recipient, messages[-1])
        # if "tool_calls" in messages[-1]:
        #     return False, None
        print(f"Messages sent to: {recipient.name} | num messages: {len(messages)}")
        _test_result = project.run_test()
        if _test_result != "success":
            return True, "Test failed!\n" + _test_result
        return False, None  # required to ensure the agent communication flow continues

    from functools import partial
    import autogen
    from autogen import register_function

    user_proxy.register_reply(
        [autogen.Agent, None],
        reply_func=auto_reply_function,
        config={"callback": None},
        position=-1,
    )

    # Register the calculator function to the two agents.
    # register_function(
    #     partial(_project.content_of_file),
    #     caller=assistant,  # The assistant agent can suggest calls to the calculator.
    #     executor=user_proxy,  # The user proxy agent can execute the calculator calls.
    #     name="content_of_file",  # By default, the function name is used as the tool name.
    #     description="A tool that show the content of specified file.",  # A description of the tool.
    # )
    # register_function(
    #     partial(_project.modify_file),
    #     caller=assistant,  # The assistant agent can suggest calls to the calculator.
    #     executor=user_proxy,  # The user proxy agent can execute the calculator calls.
    #     name="modify_source_file",  # By default, the function name is used as the tool name.
    #     description="A tool that can modify lines in specified **SOURCE** file. "
    #                 "This tool is **NOT allowed to modify the test files**",  # A description of the tool.
    # )
    # register_function(
    #     partial(_project.replace_file),
    #     caller=assistant,  # The assistant agent can suggest calls to the calculator.
    #     executor=user_proxy,  # The user proxy agent can execute the calculator calls.
    #     name="replace_source_file",  # By default, the function name is used as the tool name.
    #     description="A tool that can replace the content of **SOURCE** file. "
    #                 "This tool is **NOT allowed to modify the test files**",  # A description of the tool.
    # )
    register_function(
        partial(_project.content_of_method),
        caller=assistant,  # The assistant agent can suggest calls to the calculator.
        executor=user_proxy,  # The user proxy agent can execute the calculator calls.
        name="content_of_method",  # By default, the function name is used as the tool name.
        description="A tool that shows the content of method. "
                    "Source methods and test methods are both supported."
                    "If there is an error here, it may mean that your "
                    "last modification cases a compile error, try to redo your modification.",
    )
    register_function(
        partial(_project.command),
        caller=assistant,  # The assistant agent can suggest calls to the calculator.
        executor=user_proxy,  # The user proxy agent can execute the calculator calls.
        name="command",  # By default, the function name is used as the tool name.
        description="A tool that execute **custom** commands (**Not** a shell)." + project_parser.format_help(),
        # A description of the tool.
    )
    register_function(
        partial(_project.debug_info),
        caller=assistant,  # The assistant agent can suggest calls to the calculator.
        executor=user_proxy,  # The user proxy agent can execute the calculator calls.
        name="debug_info",  # By default, the function name is used as the tool name.
        description="A tool that can show debug information of last test. "
                    "You can choose start line and end line from a test method.",
    )
    autogen.runtime_logging.start(logger_type="file", config={"filename": f"{uuid.uuid4()}.log"})
    chat_result = user_proxy.initiate_chat(
        assistant,
        message="Locate the bug in this project. Now the failed test(s) is "
                + str(project.trigger_test_methods()),
        max_turns=10
    )
    autogen.runtime_logging.stop()
    print(chat_result)


def test_command(_project: Project) -> None:
    _project.command("-h")


def test_run_test(_project: Project) -> None:
    print(_project.run_test())


def test_method(_project: Project):
    print(_project.content_of_method("NumberUtils.java", "NumberUtils", "createNumber"))
    print(_project.content_of_method("test/org/apache/commons/lang3/math/NumberUtilsTest.java",
                                     "NumberUtilsTest", "TestLang747"))


def test_debug_info(_project: Project):
    _project.run_test()
    print(_project.debug_info("org.apache.commons.lang3.math.NumberUtilsTest", "TestLang747"))
    print("-----------------------------")
    print(_project.debug_info(
        "org.apache.commons.lang3.math.NumberUtilsTest",
        "TestLang747",
        256, 256
    ))


def test_all_files(_project: Project):
    print(_project.content_of_file("org/apache/commons/lang3/math/NumberUtils.java"))
    print(_project.all_files())


if __name__ == '__main__':
    import os
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--base-dir", help="base dir of the project", required=True)
    args = parser.parse_args()
    project = Project(args.base_dir)

    # 获取当前脚本所在目录的上级目录的绝对路径
    parent_dir = os.path.dirname(os.path.abspath(__file__))
    grand_parent_dir = os.path.dirname(parent_dir)

    # 将上级目录添加到Python的搜索路径中
    sys.path.insert(0, grand_parent_dir)
    from load_env import load_env

    load_env()

    test_llm(project)
    # test_group_chat(project)
    # test_command(project)
    # test_run_test(project)
    # test_method(project)
    # test_debug_info(project)
    # test_all_files(project)
