from Chat import Chat

if __name__ == '__main__':
    from dotenv import load_dotenv, find_dotenv
    _ = load_dotenv(find_dotenv())
    chat = Chat("gpt-3.5-turbo", "Please generate some mutations for the Java program I provided")
    with open("Lang33b_1") as f:
        text = f.read()
    messages = chat.chat(text, 20)
    for index, message in enumerate(messages):
        with open(f"out/Lang33b/log{index}", "w") as f:
            f.write(message)
