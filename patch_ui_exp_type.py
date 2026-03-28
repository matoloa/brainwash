with open("src/lib/ui.py", "r") as f:
    content = f.read()

old_exp = """        if exp_type == "io" or old_type == "io":
            self.exorcise()
            self.triggerRefresh()"""

new_exp = """        if exp_type in ["io", "PP"] or old_type in ["io", "PP"]:
            self.exorcise()
            self.triggerRefresh()"""

if old_exp in content:
    content = content.replace(old_exp, new_exp)
    with open("src/lib/ui.py", "w") as f:
        f.write(content)
    print("Success: experiment_type_changed")
else:
    print("Failed")
