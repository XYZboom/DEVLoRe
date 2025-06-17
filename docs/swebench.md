# How to use on swebench
- [x] **Step 1. Clone project**

```bash
git clone https://github.com/XYZboom/DEVLoRe.git
```

- [x] **Step 2. Install python requirements**

```bash
pip install -r requirements.txt
```

- [x] **Step 3. Prepare [SWEbench](https://github.com/SWE-bench/SWE-bench) environment**

Just follow the readme in SWEbench ([https://github.com/SWE-bench/SWE-bench](https://github.com/SWE-bench/SWE-bench))

Note that we currently support several bugs in SWEbench-Lite only.

- [x] **Step 4. Setup environment variables**

Create a ".env" file at the root of this project.
Set environment variables like this:

```text
OPENAI_API_KEY=your_openai_api_key
OUTPUT_PATH=where_to_output
MODULE_NAME=your LLM name, gpt-4o-mini better
```

- [x] **Step 5. Run scripts**

Run scripts under `src/swebench_utils_docker`
