with open("src/lib/ui_plot.py", "r") as f:
    content = f.read()

content = "import warnings\n" + content

with open("src/lib/ui_plot.py", "w") as f:
    f.write(content)
