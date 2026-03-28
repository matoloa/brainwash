with open("src/lib/ui.py", "r") as f:
    content = f.read()

old_exp_type = """        if exp_type in ["io", "PP"] or old_type in ["io", "PP"]:
            self.exorcise()
            self.triggerRefresh()
        else:
            self.update_show()
            self.zoomAuto()
            self.graphRefresh()"""

new_exp_type = """        if exp_type in ["io", "PP"] or old_type in ["io", "PP"]:
            self.exorcise()
            self.triggerRefresh()
            self.zoomAuto()
            self.graphRefresh()
        else:
            self.update_show()
            self.zoomAuto()
            self.graphRefresh()"""

if old_exp_type in content:
    content = content.replace(old_exp_type, new_exp_type)
    with open("src/lib/ui.py", "w") as f:
        f.write(content)
    print("Patched experiment_type_changed to call zoomAuto")
else:
    print("Failed to patch experiment_type_changed")
