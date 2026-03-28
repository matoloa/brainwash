import re

with open("src/lib/ui_plot.py", "r") as f:
    content = f.read()

# Add skip_output variable in addRow
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
        skip_output = getattr(self.uistate, "experiment_type", "time") == "PP" and n_stims != 2"""

content = content.replace(old_add_row, new_add_row)

# Let's replace plot_line and plot_hline calls for ax1/ax2 with conditional
def replace_plot_line(match):
    indent = match.group(1)
    func_call = match.group(2)
    ax_arg = match.group(3)
    if ax_arg in ['"ax1"', '"ax2"']:
        # We need to wrap this in an if block. Since python relies on indentation, we replace it with an if statement
        lines = func_call.split('\n')
        wrapped = f"{indent}if not skip_output:\n"
        for line in lines:
            if line.strip():
                wrapped += f"{indent}    {line.strip()}\n"
        return wrapped.rstrip() + "\n"
    return match.group(0)

# But there are multi-line plot_line calls.
# Let's look at how they are formatted.
