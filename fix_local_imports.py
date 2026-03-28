with open("src/lib/ui_plot.py", "r") as f:
    lines = f.readlines()
with open("src/lib/ui_plot.py", "w") as f:
    for i, line in enumerate(lines):
        if "import numpy as np" in line and i > 10:
            continue
        if "import warnings" in line and i > 10:
            continue
        f.write(line)

with open("src/lib/ui.py", "r") as f:
    lines = f.readlines()
with open("src/lib/ui.py", "w") as f:
    for i, line in enumerate(lines):
        if "import numpy as np" in line and i > 10:
            continue
        if "import warnings" in line and i > 10:
            continue
        f.write(line)
