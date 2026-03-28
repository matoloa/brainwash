with open("src/lib/ui_plot.py", "r") as f:
    for line in f:
        if "EPSP amp norm" in line and "label" in line:
            print(line.strip())
            for _ in range(12):
                print(next(f).strip())
            break
