with open("src/lib/ui.py", "r") as f:
    for line in f:
        if "def refreshData(" in line:
            for _ in range(30):
                print(line, end="")
                line = next(f)
            break
