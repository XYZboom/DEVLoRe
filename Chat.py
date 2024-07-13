import os
from typing import List, Union

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam, ChatCompletionSystemMessageParam, \
    ChatCompletionUserMessageParam

from IllegalStateException import IllegalStateException


def create_message(content: str) -> ChatCompletionUserMessageParam:
    return {"role": "user",
            "content": content}


def create_system_prompt(content: str) -> ChatCompletionSystemMessageParam:
    return {"role": "system",
            "content": content}


class Chat:
    _messages: List[ChatCompletionMessageParam]
    _model: str

    def __init__(self, model: str, system_prompt: str):
        self._client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL")
        )
        self._messages = [create_system_prompt(system_prompt)]
        self._model = model
        self._waiting_choice = False
        self._last_messages = None

    def chat(self, content: str, num_choice=1) -> Union[str, List[str]]:
        if self._waiting_choice:
            raise IllegalStateException("Waiting for your choice")
        self._messages.append(create_message(content))
        return self.__do_chat(num_choice)

    def clear(self):
        self._messages.clear()

    def redo_last(self, num_choice=1) -> Union[str, List[str]]:
        if self._waiting_choice:
            raise IllegalStateException("Waiting for your choice")
        del self._messages[-1]
        return self.__do_chat(num_choice)

    def choose(self, index: int):
        if not self._waiting_choice:
            raise IllegalStateException("Not waiting for your choice")
        self._waiting_choice = False
        self._messages.append(self._last_messages[index])
        self._last_messages = None

    def __do_chat(self, num_choice) -> Union[str, List[str]]:
        __completion = self._client.chat.completions.create(model=self._model, messages=self._messages, n=num_choice)
        if num_choice == 1:
            __message = __completion.choices[0].message
            # noinspection PyTypeChecker
            self._messages.append(__message)
            return __message.content
        else:
            self._waiting_choice = True
            self._last_messages = [c.message for c in __completion.choices]
            return [i.content for i in self._last_messages]


if __name__ == '__main__':
    from dotenv import load_dotenv, find_dotenv

    # dotenv  是python的一个库，用来写配置的，可以百度一下很简单！！
    # 如果不要配置，就直接写key和url，然后把这段代码删除了
    _ = load_dotenv(find_dotenv())  # 读取本地 .env 文件，里面定义了 OPENAI_API_KEY
    print()
    pass
