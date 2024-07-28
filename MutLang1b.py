from Chat import Chat

if __name__ == '__main__':
    from dotenv import load_dotenv, find_dotenv
    _ = load_dotenv(find_dotenv())
    chat = Chat("gpt-4o-2024-05-13", "You are a software development engineer.")
    with open("Lang1b_debug") as f:
        text = f.read()
    messages = chat.chat(text, 5)
    for index, message in enumerate(messages):
        with open(f"out/Lang1b/log{index}", "w") as f:
            f.write(message)
