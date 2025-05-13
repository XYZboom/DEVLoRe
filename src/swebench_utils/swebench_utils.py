if __name__ == '__main__':
    from datasets import load_dataset

    # Login using e.g. `huggingface-cli login` to access this dataset
    ds = load_dataset("SWE-bench/SWE-bench_Lite")

    ds
