with open("src/lib/ui_plot.py", "r") as f:
    lines = f.readlines()
for line in lines:
    if "def plot_line(" in line:
        print(line, end="")
    if "def plot_hline(" in line:
        print(line, end="")
    if "def plot_marker(" in line:
        print(line, end="")
