with open("src/lib/ui_plot.py", "r") as f:
    for line in f:
        if "def plot_line(" in line:
            break
    for _ in range(30):
        print(next(f), end="")
