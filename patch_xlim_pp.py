with open("src/lib/ui_state_classes.py", "r") as f:
    content = f.read()

old_xlim = """    def x_axis_xlim(self, prow, dft=None) -> tuple:
        \"\"\"Return (xmin, xmax) for the output graph given the current mode.

        In time mode, also caches the auto-scaled unit (divisor and label)
        for use by x_axis_xlabel and x_axis_formatter.  The returned limits
        are always in sweep-space (same coordinates as the line x-data);
        the FuncFormatter converts tick labels to the chosen time unit.
        \"\"\"
        mode = self.x_axis"""

new_xlim = """    def x_axis_xlim(self, prow, dft=None) -> tuple:
        \"\"\"Return (xmin, xmax) for the output graph given the current mode.

        In time mode, also caches the auto-scaled unit (divisor and label)
        for use by x_axis_xlabel and x_axis_formatter.  The returned limits
        are always in sweep-space (same coordinates as the line x-data);
        the FuncFormatter converts tick labels to the chosen time unit.
        \"\"\"
        if self.experiment_type == "PP":
            return (0.5, 1.5)
        
        mode = self.x_axis"""

if old_xlim in content:
    content = content.replace(old_xlim, new_xlim)
    with open("src/lib/ui_state_classes.py", "w") as f:
        f.write(content)
    print("Patched x_axis_xlim in ui_state_classes.py")
else:
    print("Failed to find old_xlim")

