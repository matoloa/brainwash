with open("src/lib/ui.py", "r") as f:
    content = f.read()

# Patch 1: graphPreloadThread
old_thread = """                print("graphPreloadThread.run: calling get_dfoutput")
                if self.uistate.checkBox["paired_stims"]:
                    dfoutput = self.uisub.get_dfdiff(row=p_row)
                else:
                    dfoutput = self.uisub.get_dfoutput(row=p_row)"""

new_thread = """                print("graphPreloadThread.run: calling get_dfoutput")
                is_pp = getattr(self.uistate, "experiment_type", "time") == "PP"
                if self.uistate.checkBox["paired_stims"] and not is_pp:
                    dfoutput = self.uisub.get_dfdiff(row=p_row)
                else:
                    dfoutput = self.uisub.get_dfoutput(row=p_row)"""

if old_thread in content:
    content = content.replace(old_thread, new_thread)
    print("Patched graphPreloadThread")

# Patch 2: graphUpdate
old_graph_update = """        def processRow(row):
            dfmean = self.get_dfmean(row=row)
            dft = self.get_dft(row=row)
            print(f"graphUpdate dft: {dft}")
            dfoutput = self.get_dfdiff(row=row) if uistate.checkBox["paired_stims"] else self.get_dfoutput(row=row)
            if dfoutput is not None:"""

new_graph_update = """        def processRow(row):
            dfmean = self.get_dfmean(row=row)
            dft = self.get_dft(row=row)
            print(f"graphUpdate dft: {dft}")
            is_pp = getattr(uistate, "experiment_type", "time") == "PP"
            dfoutput = self.get_dfdiff(row=row) if (uistate.checkBox["paired_stims"] and not is_pp) else self.get_dfoutput(row=row)
            if dfoutput is not None:"""

if old_graph_update in content:
    content = content.replace(old_graph_update, new_graph_update)
    print("Patched graphUpdate")

with open("src/lib/ui.py", "w") as f:
    f.write(content)
