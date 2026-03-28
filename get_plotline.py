with open("src/lib/ui_plot.py", "r") as f:
    for i, line in enumerate(f):
        if "def plot_line(" in line:
            break
    for _ in range(40):
        print(next(f), end="")
