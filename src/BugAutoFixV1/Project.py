import os
import re
import subprocess
import sys
import uuid
from typing import *

import dotenv
from dotenv import load_dotenv, find_dotenv
from pydantic import BaseModel, Field
import argparse
import javalang

#加载环境变量
_ = load_dotenv(find_dotenv())

#设置忽略路径
ignore_paths = ["/.git", "/.classes.tmp", "/target", "/.idea"]

#设置命令行解释器,添加各个子命令
project_parser = argparse.ArgumentParser(description="Command in project", exit_on_error=False)
subparsers = project_parser.add_subparsers(dest="subcommand")  # save subcommands in "args.subcommand"

#子命令解释器,用于展示项目中所有文件\文件计数以及运行测试
all_files_parser = subparsers.add_parser("all_files", help="Show all files in project")
count_files_parser = subparsers.add_parser("count_files", help="Count all files in project")
run_test_parser = subparsers.add_parser("run_test", help="Run test in project, return value is test result.")
# undo_all_parser = subparsers.add_parser("undo_all", help="Undo all changes.")

#缺陷相关配置键
D4J_RELEVANT_KEY = "d4j.classes.relevant"
D4J_SRC_PATH_KEY = "d4j.dir.src.classes"
D4J_TEST_PATH_KEY = "d4j.dir.src.tests"
D4J_TRIGGER_KEY = "d4j.tests.trigger"

#从环境变量中获取D4J的路径
D4J_EXEC = os.environ.get("DEFECTS4J_EXEC")
if not D4J_EXEC:
    raise Exception("D4J_EXEC env variable is not set")

#定义日志和失败测试文件名
D4J_FAILING_TEST = "failing_tests"
DEBUG_LOG_NAME = "bugDetect.log"
ORI_DEBUG_LOG_NAME = "bugDetectOri.log"

#定义Project类
class Project:

    #在 Project 类中，这些 KEY 作为常量，便于在类的其他方法中引用这些字符串，统一且清晰地表述不同字段的含义
    #保存修改结果用的
    SEARCH_KEY = "search"
    REPLACE_KEY = "replace"
    CLASS_KEY = "class"

    #类的入口
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self._files = []
        self.undo_all_files()
        _d4j_file_name = os.path.join(base_dir, "defects4j.build.properties")
        if not os.path.exists(_d4j_file_name):
            raise FileNotFoundError("No defects4j.build.properties file found")
        self._d4j_configs = dotenv.dotenv_values(_d4j_file_name)
        self._relevant_classes = self._d4j_configs.get(D4J_RELEVANT_KEY).split(",")
        self._src_path = self._d4j_configs.get(D4J_SRC_PATH_KEY).removeprefix("./")
        self._test_path = self._d4j_configs.get(D4J_TEST_PATH_KEY).removeprefix("./")
        self._trigger_test_methods = self._d4j_configs.get(D4J_TRIGGER_KEY)
        self._trigger_tests = [self._trigger_test_methods.split("::")[0]
                               for _test_method in self._trigger_test_methods.split(",")]
        #遍历base目录,过滤过滤路径当中的目录
        for path, dirs, files in os.walk(base_dir):
            ignore = False
            # 给ignore_path中的项添加ignore标记
            for ignore_path in ignore_paths:
                if path.removeprefix(base_dir).startswith(ignore_path):
                    ignore = True
                    break
            if ignore:
                continue
            #Java文件处理
            for f in files:
                if f.endswith(".java"):
                    #路径转换:将文件路径转换成项目当中的相对路径
                    #把路径转换成可以引用的java类名格式
                    _f_path = os.path.join(path.replace(base_dir, ''), f)
                    _class_name = _f_path.removesuffix(".java").removesuffix("/").removeprefix("/")
                    _class_name = re.sub(f"^.*?{self._src_path}", "", _class_name)
                    _class_name = re.sub(f"^.*?{self._test_path}", "", _class_name)
                    _class_name = _class_name.removesuffix("/").removeprefix("/").replace("/", ".")
                    #如果提取的类是相关类,那么将_f_path添加到_files中
                    if _class_name in self._relevant_classes or _class_name in self._trigger_tests:
                        self._files.append(_f_path)
        #没找到相关类就会raise exception
        if len(self._files) == 0:
            raise Exception(f"No files found in {base_dir}")
        
    #应用替换操作的核心部分(这里替换的是correct前后的内容吗)
    #此处_replace_list:List用于表示这是一个列表,Dict表示这个列表每个元素都是一个键值对,Literal限制了这个键值对键的取值,str说明了值必须是字符串类型
    #定义了广义替换操作
    def apply_replace_list(self, _replace_list: List[Dict[Literal["replace", "search", "class"], str]]):
        for _replace in _replace_list:
            self.apply_replace(_replace)

    #定义了具体替换操作
    def apply_replace(self, _replace: Dict[str, str]):
        #从字典中获取类名,如果类名中包含test或Test,那么直接返回,不对测试类文件进行替换  
        _class_name = _replace[self.CLASS_KEY]
        if "test" in _class_name or "Test" in _class_name:
            return
        _file = self.find_file(_class_name.replace(".", "/") + ".java")
        if "test" in _file or "Test" in _file:
            return
        #文件内容处理与预处理
        with open(_file, "r") as _f:
            _ori_content = _f.read()
            _ori_lines = _ori_content.splitlines()#移除换行符,返回每一行内容的列表
        _line_number_ori = len(_ori_lines)#定义line_number,值为ori_lines的长度
        _search_line_index = -1
        _search_lines = _replace[self.SEARCH_KEY].splitlines()
        #查找要替换的行 
        #这行代码的作用是遍历 _ori_lines 的指定部分，为后续逐行匹配 _search_lines 提供 line_index 起始位置
        #使得从 line_index 开始可以完整地匹配 _search_lines 的内容
        for line_index, _ in enumerate(_ori_lines[:-len(_search_lines)]):
            #                                     ^^^^^^^^^^^^^^^^^^^^
            # if remain lines count > replace lines count, no more lines could be replaced.
            found = True
            # 从 line_index 开始，对比 _ori_lines 和 _search_lines 的每一行内容
            for _ori_line, _search_line in zip(_ori_lines[line_index:line_index + len(_search_lines)],
                                               _search_lines):
                 # 指定 _ori_line 和 _search_line 为字符串类型
                _ori_line: str
                _search_line: str
                # 如果 _ori_line 或 _search_line 以行号开头，将其去除（仅保留内容部分）
                if _ori_line.split("|")[0].isdigit():
                    _ori_line = _ori_line.split("|")[1]
                if _search_line.split("|")[0].isdigit():
                    _search_line = _search_line.split("|")[1]

                # 去除前后空格，以便后续准确地比较两行内容
                _trimmed_replace_line = _search_line.strip()
                _trimmed_ori_line = _ori_line.strip()

                # 如果内容不匹配，标记 found 为 False，停止进一步检查
                if _trimmed_replace_line != _trimmed_ori_line:
                    found = False
            # 如果所有行都匹配，将 _search_line_index 设置为当前的 line_index 并退出循环
            if found:
                _search_line_index = line_index
                break
        # 如果未找到匹配项，抛出异常，提示未找到匹配行
        if _search_line_index == -1:
            raise Exception("No matching lines found")
        _replace_lines = _replace[self.REPLACE_KEY].splitlines()
        for i, _search_line in enumerate(_replace_lines):
            if _search_line.split("|")[0].isdigit():
                _search_line = _search_line.split("|")[1]
                _replace_lines[i] = _search_line
        _ori_lines[_search_line_index + 1:_search_line_index + len(_search_lines)] = []
        # _ori_lines[_search_line_index] = _replace[self.REPLACE_KEY] + "\n"
        # 将 _replace_lines 插入到 _ori_lines 中，替换原有内容
        _ori_lines[_search_line_index] = "\n".join(_replace_lines) + "\n"
        # 将修改后的内容写回文件，保持换行符格式一致（\r\n 或 \n）
        with open(_file, "w") as _f:
            if "\r" in _ori_content:
                _f.write("\r\n".join(_ori_lines))
            else:
                _f.write("\n".join(_ori_lines))

    #返回self中的一个值,包括触发测试的方法列表
    def trigger_test_methods(self):
        return self._trigger_test_methods

    ## 遍历当前项目中所有文件名，查找与给定文件名匹配的文件
    #找到文件那么就返回绝对路径,找不到的话就抛出FileNotFoundError
    def find_file(self, file: str) -> str:
        for f_name in self._files:
            if f_name.endswith(file) or f_name.replace("/java", "").endswith(file):
                file_path = self.base_dir + f_name if f_name.startswith("/") else os.path.join(self.base_dir, f_name)
                return os.path.abspath(file_path)
        raise FileNotFoundError(f"No such file {file}")

    def content_of_file(self, file_path: Annotated[str, "The path of the file to be opened. e.g. "
                                                        "org/jetbrains/java/PsiClass.java"],
                        contain_line_number: Annotated[bool, "True if the return string contains line number"] = False,
                        ) -> str:
        # 使用 find_file 函数找到指定文件的路径
        file_path = self.find_file(file_path)
        with open(file_path, "r") as f:
            lines = f.readlines()
        if contain_line_number:
            lines = [str(line_num + 1) + "|" + line for line_num, line in enumerate(lines)]
        # 返回拼接后的所有行内容
        return "".join(lines)

    def content_of_method(
            self,
            file_path: Annotated[str, "The path of the file to be opened. e.g. org/jetbrains/java/PsiClass.java"],
            class_name: Annotated[str, "The class name which contains the method you want."],
            method_name: Annotated[str, "The method name."]
    ) -> str:
        # 获取文件内容
        _content = self.content_of_file(file_path)
        
        # 使用 javalang 解析 Java 源代码结构
        _tree = javalang.parse.parse(_content)

        # 获取类名（可能包含包路径），仅提取类的基本名称
        class_name = class_name.split(".")[-1]
        
        # 在解析树中查找指定的类，确保类名与提供的名称匹配
        _classes = [clazz for clazz in _tree.types if clazz.name == class_name]
        if len(_classes) == 0:
            raise Exception(f"No class named {class_name} in {file_path}")
        
        #提取到的类的定义
        _class = _classes[0]
        
        #在类的定义中查找指定的方法名称
        _methods = [method for method in _class.methods if method.name == method_name]
        if len(_methods) == 0:
            raise Exception(f"No method named {method_name} in {file_path}")
        
        #获取方法的定义
        _method = _methods[0]

        #将文件内容按行分隔为列表
        _content_lines = _content.splitlines()

        #计算方法开始和结束的行号(从开始行从方法的位置信息中获取,结束行依据方法体最后一行推断)
        _start_line = _method.position.line - 1
        _end_line = min(_method.body[-1].position.line + 2, len(_content_lines))

        #提取方法体的所有行
        _result_lines = _content_lines[_start_line:_end_line]
        _result = ""
        for index, line in enumerate(_result_lines):
            _result += line + "// line " + str(index + _start_line + 1) + "\n"
        return _result

    #在指定的文件特定行范围内替换内容.文件修改后会重新写入,保存修改
    def modify_file(
            self,
            file_path: Annotated[str, "Path of file to change."],
            start_line: Annotated[int, "Start line number to replace with new code."],
            end_line: Annotated[int, "End line number to replace with new code."],
            new_code: Annotated[str, "New piece of code to replace old code with. Remember about providing indents."],
    ) -> str:
    #检查文件中路径中是否包含"test"关键字,如果是不允许修改测试文件
        if "test" in file_path or "Test" in file_path:
            raise Exception("Test files can not be modified")
        file_path = self.find_file(file_path)
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
        file_path = self.find_file(file_path)
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

    #返回str列表(文件列表)
    def all_files(self) -> List[str]:
        return self._files

    #
    def run_test(self, delete_last_log=True, single_test: str = None, relevant=True):
        # noinspection PyBroadException
        try:
            os.remove(os.path.join(self.base_dir, D4J_FAILING_TEST))
        except Exception as _:
            pass
        if delete_last_log:
            # noinspection PyBroadException
            try:
                os.remove(os.path.join(self.base_dir, DEBUG_LOG_NAME))
            except Exception as _:
                pass
            # noinspection PyBroadException
            try:
                os.remove(os.path.join(self.base_dir, ORI_DEBUG_LOG_NAME))
            except Exception as _:
                pass
        if single_test:
            result = subprocess.run(f"{D4J_EXEC} test -t {single_test}", shell=True,
                                    stderr=subprocess.PIPE, stdout=subprocess.PIPE, cwd=self.base_dir)
        elif relevant:
            result = subprocess.run(f"{D4J_EXEC} test -r", shell=True,
                                    stderr=subprocess.PIPE, stdout=subprocess.PIPE, cwd=self.base_dir)
        else:
            result = subprocess.run(f"{D4J_EXEC} test", shell=True,
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

    def raw_debug_info(self):
        _base_debug_file = os.path.join(self.base_dir, DEBUG_LOG_NAME)
        with open(_base_debug_file, "r") as f:
            _result = f.read()
        if os.path.getsize(_base_debug_file) < 5 * 1024:
            _last_debug_file = os.path.join(self.base_dir, DEBUG_LOG_NAME + ".1")
            if os.path.exists(_last_debug_file):
                with open(_last_debug_file, "r") as f:
                    _result += f.read()
        if len(_result) == 0:
            print("try use ori")
            _base_debug_file = os.path.join(self.base_dir, ORI_DEBUG_LOG_NAME)
            with open(_base_debug_file, "r") as f:
                _result = f.read()
            if os.path.getsize(_base_debug_file) < 5 * 1024:
                _last_debug_file = os.path.join(self.base_dir, ORI_DEBUG_LOG_NAME + ".1")
                if os.path.exists(_last_debug_file):
                    with open(_last_debug_file, "r") as f:
                        _result += f.read()
        return _result

    def debug_info(
            self, test_class_name: Annotated[str, "The test class name. "
                                                  "e.g. org.apache.commons.lang3.math.NumberUtilsTest"] = None,
            method_name: Annotated[str, "The test method name. e.g. testMethod"] = None,
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
            if test_class_name is None or method_name is None:
                lines.append(line)
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
        name="Bug_fixer",
        system_message="You are a bug fixer. Your goal is to pass all the test in the project."
                       "Ask your assistants to explore the project first.",
        llm_config=llm_config
    )
    testcase_explainer = ConversableAgent(
        name="Testcase_explainer",
        system_message="You are a testcase explainer. Your goal is to explain testcases in the project and help"
                       "bug fixer to pass all the test in the project. "
                       "Ask your assistants to explore the project first.",
        llm_config=llm_config
    )
    programming_assistant = ConversableAgent(
        name="Programming_assistant",
        system_message="You are a programming assistant. Your goal is to help bug fixer edit the files in the project.",
        llm_config=llm_config
    )
    command_executor = ConversableAgent(
        name="Command_executor",
        llm_config=False,
        # is_termination_msg=lambda msg: msg.startswith("TERMINATE"),
        human_input_mode="NEVER",
    )
    group_chat = GroupChat(
        agents=[bug_fixer, testcase_explainer, programming_assistant, command_executor],
        messages=[],
        max_round=30,
        send_introductions=True
    )
    group_chat_manager = GroupChatManager(
        groupchat=group_chat,
        llm_config=llm_config,
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
    programming_assistant.register_for_llm(name="content_of_method",
                                           description=content_of_method_description)(content_of_method_f)
    # bug_fixer.register_for_llm(name="content_of_method",
    #                            description=content_of_method_description)(content_of_method_f)
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
        caller=programming_assistant,  # The assistant agent can suggest calls to the calculator.
        executor=command_executor,  # The user proxy agent can execute the calculator calls.
        name="debug_info",  # By default, the function name is used as the tool name.
        description="A tool that can show debug information of last test. "
                    "You can choose start line and end line from a test method.",
    )

    chat_result = command_executor.initiate_chat(
        group_chat_manager,
        message="Fix the bug(s) in this project. Your goal is to pass all the tests in the project."
                "Now the failed test(s) is "
                + str(project.trigger_test_methods())
    )
    print(chat_result)


def test_llm(_project: Project) -> None:
    from autogen import ConversableAgent

    llm_config = {"config_list": [{"model": "gpt-3.5-turbo", "api_key": os.environ["OPENAI_API_KEY"],
                                   "price": [0.00365, 0.0146]}],
                  "cache_seed": None}

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
        llm_config=llm_config,
    )

    # The user proxy agent is used for interacting with the assistant agent
    # and executes tool calls.
    user_proxy = ConversableAgent(
        name="User",
        system_message="You are a user of a bug locator",
        llm_config=llm_config,
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

    # user_proxy.register_reply(
    #     [autogen.Agent, None],
    #     reply_func=auto_reply_function,
    #     config={"callback": None},
    #     position=-1,
    # )

    # Register the calculator function to the two agents.
    register_function(
        partial(_project.content_of_file),
        caller=assistant,  # The assistant agent can suggest calls to the calculator.
        executor=user_proxy,  # The user proxy agent can execute the calculator calls.
        name="content_of_file",  # By default, the function name is used as the tool name.
        description="A tool that show the content of specified file.",  # A description of the tool.
    )
    register_function(
        partial(_project.modify_file),
        caller=assistant,  # The assistant agent can suggest calls to the calculator.
        executor=user_proxy,  # The user proxy agent can execute the calculator calls.
        name="modify_source_file",  # By default, the function name is used as the tool name.
        description="A tool that can modify lines in specified **SOURCE** file. "
                    "This tool is **NOT allowed to modify the test files**",  # A description of the tool.
    )
    register_function(
        partial(_project.replace_file),
        caller=assistant,  # The assistant agent can suggest calls to the calculator.
        executor=user_proxy,  # The user proxy agent can execute the calculator calls.
        name="replace_source_file",  # By default, the function name is used as the tool name.
        description="A tool that can replace the content of **SOURCE** file. "
                    "This tool is **NOT allowed to modify the test files**",  # A description of the tool.
    )
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
    # print(chat_result)


def test_llm2(_project: Project):
    import Chat
    chat = Chat.Chat("gpt-3.5-turbo-1106", "You are a software development engineer.")
    localize_message_template = """Review the following files, test case(s), and exception that occurs when doing the test, 
and provide a set of locations that need to be edited to fix the issue. The locations can be specified as class 
names, method names, or exact line numbers that require modification.
### Files ###
{files_contents}
### Failed Test Case(s) and exception ###
{testcase_contents}
Please provide the class name, method name, or the exact line numbers that need to be edited.
### Examples:
```
path/to/ClassA.java
line: 10
class: ClassA
line: 51

path/to/ClassB.java
method: ClassB.method0
line: 12

path/to/ClassC.java
method: ClassC.method1
line: 24
line: 241
```

Return just the location(s)
"""
    file_content_template = """### {file_name}
```java
{file_content}
```
"""
    files_contents = [
        file_content_template.format(
            file_name=_file_name, file_content=_project.content_of_file(_file_name, True)
        ) for _file_name in _project.all_files()
    ]
    localize_message = localize_message_template.format(
        files_contents="\n".join(files_contents),
        testcase_contents=_project.failed_test()
    )
    print(localize_message)


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

    # test_llm(project)
    test_llm2(project)
    # test_group_chat(project)
    # test_command(project)
    # test_run_test(project)
    # test_method(project)
    # test_debug_info(project)
    # test_all_files(project)
