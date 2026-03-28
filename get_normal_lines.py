with open("src/lib/ui_plot.py", "r") as f:
    for line in f:
        if "EPSP amp norm" in line and "plot_line" in line:
            for _ in range(15):
                print(line, end="")
                line = next(f)
            break
