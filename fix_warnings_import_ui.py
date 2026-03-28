with open("src/lib/ui.py", "r") as f:
    content = f.read()

content = "import warnings\n" + content

with open("src/lib/ui.py", "w") as f:
    f.write(content)
