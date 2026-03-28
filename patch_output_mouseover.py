import re

with open("src/lib/ui.py", "r") as f:
    content = f.read()

old_func = """    def outputMouseover(self, event):  # determine which event is being mouseovered
        is_io = getattr(uistate, "experiment_type", "time") == "io"
        if is_io:"""

new_func = """    def outputMouseover(self, event):  # determine which event is being mouseovered
        if getattr(uistate, "experiment_type", "time") == "PP":
            return
        is_io = getattr(uistate, "experiment_type", "time") == "io"
        if is_io:"""

if old_func in content:
    content = content.replace(old_func, new_func)
    with open("src/lib/ui.py", "w") as f:
        f.write(content)
    print("Success")
else:
    print("Failed")
