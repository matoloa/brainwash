with open("src/lib/ui_plot.py", "r") as f:
    content = f.read()

old_add_row = """    def addRow(self, p_row, dft, dfmean, dfoutput):
        rec_ID = p_row["ID"]
        rec_name = p_row["recording_name"]
        rec_filter = p_row["filter"]  # the filter currently used for this recording
        n_stims = len(dft)"""

new_add_row = """    def addRow(self, p_row, dft, dfmean, dfoutput):
        rec_ID = p_row["ID"]
        rec_name = p_row["recording_name"]
        rec_filter = p_row["filter"]  # the filter currently used for this recording
        n_stims = len(dft)
        is_pp = getattr(self.uistate, "experiment_type", "time") == "PP"
        skip_output = is_pp and n_stims != 2"""

if old_add_row in content:
    content = content.replace(old_add_row, new_add_row)
    with open("src/lib/ui_plot.py", "w") as f:
        f.write(content)
    print("Success: Added is_pp and skip_output to addRow")
else:
    print("Failed to find old_add_row")

