import os

from openai import OpenAI

from dotenv import load_dotenv, find_dotenv

# dotenv  是python的一个库，用来写配置的，可以百度一下很简单！！
# 如果不要配置，就直接写key和url，然后把这段代码删除了
_ = load_dotenv(find_dotenv())  # 读取本地 .env 文件，里面定义了 OPENAI_API_KEY

if __name__ == '__main__':
    # proxy_url = 'http://127.0.0.1'
    # proxy_port = 26001

    # Set the http_proxy and https_proxy environment variables
    # os.environ['http_proxy'] = f'{proxy_url}:{proxy_port}'
    # os.environ['https_proxy'] = f'{proxy_url}:{proxy_port}'

    # 开启openAI的接口 OPENAI_API_KEY，可以是OpenAI申请的key，也可以是国内的key
    # OPENAI_BASE_URL，可以是OpenAI的URl，例如：https://api.openai.com/v1/chat/completions，这个URL在OpenAI官方的 API reference
    # 里面都有。当然也可以是国内代理的URL，需要自己替换哦。 一定要记得，key与url 需要匹配使用，如果你用的是代理模式，那就一套都是代理的信息，如果是OpenAI API 源模式。那就一套都是OpenAI的信息
    # 宝子们一定要记得改这里。
    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL")
    )
    completion = client.chat.completions.create(
        model="ERNIE-Speed-128K",
        messages=[
            {"role": "system",
             "content": os.getenv("SYS_PROMPT")},
            {"role": "user",
             "content": open("Lang1b_1").read()}
        ]
    )

    print(completion.choices[0].message)
