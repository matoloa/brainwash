with open("src/lib/ui_plot.py", "r") as f:
    content = f.read()

old_out_mean = """    def updateOutMean(self, label, mean):
        print(f"updateOutMean: {label}, {mean}")
        mouseover_out = self.uistate.mouseover_out
        if mouseover_out is None:
            print(f"updateOutMean: mouseover_out is None, skipping update for '{label}'")
            return
        linedict = self.uistate.dict_rec_labels[label]"""

new_out_mean = """    def updateOutMean(self, label, mean):
        print(f"updateOutMean: {label}, {mean}")
        mouseover_out = self.uistate.mouseover_out
        if mouseover_out is None:
            print(f"updateOutMean: mouseover_out is None, skipping update for '{label}'")
            return
        if label not in self.uistate.dict_rec_labels:
            return
        linedict = self.uistate.dict_rec_labels[label]"""

if old_out_mean in content:
    content = content.replace(old_out_mean, new_out_mean)
    with open("src/lib/ui_plot.py", "w") as f:
        f.write(content)
    print("Patched updateOutMean")
else:
    print("Failed")
