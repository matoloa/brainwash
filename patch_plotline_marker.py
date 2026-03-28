with open("src/lib/ui_plot.py", "r") as f:
    content = f.read()

old_plotline = """    def plot_line(
        self,
        label,
        axid,
        x,
        y,
        color,
        rec_ID,
        aspect=None,
        stim=None,
        width=1,
        alpha=None,
        variant="raw",
        x_mode=None,
    ):
        is_pp = getattr(self.uistate, "experiment_type", "time") == "PP"
        if is_pp and axid in ("ax1", "ax2") and "PPR" not in label:
            return
        zorder = 0 if width > 1 else 1
        alpha = alpha if alpha is not None else self.uistate.settings["alpha_line"]
        (line,) = self.get_axis(axid).plot(x, y, color=color, label=label, alpha=alpha, linewidth=width, zorder=zorder)"""

new_plotline = """    def plot_line(
        self,
        label,
        axid,
        x,
        y,
        color,
        rec_ID,
        aspect=None,
        stim=None,
        width=1,
        alpha=None,
        variant="raw",
        x_mode=None,
        marker=None,
    ):
        is_pp = getattr(self.uistate, "experiment_type", "time") == "PP"
        if is_pp and axid in ("ax1", "ax2") and "PPR" not in label:
            return
        zorder = 0 if width > 1 else 1
        alpha = alpha if alpha is not None else self.uistate.settings["alpha_line"]
        if marker is None:
            (line,) = self.get_axis(axid).plot(x, y, color=color, label=label, alpha=alpha, linewidth=width, zorder=zorder)
        else:
            (line,) = self.get_axis(axid).plot(x, y, color=color, label=label, alpha=alpha, linewidth=width, zorder=zorder, marker=marker)"""

if old_plotline in content:
    content = content.replace(old_plotline, new_plotline)
    
    # Add marker="o" to PP plot calls
    old_ppr_plot = """                        for variant in ["raw", "norm"]:
                            self.plot_line(
                                f"{label} PPR {aspect} {variant}",
                                axid,
                                common_sweeps,
                                ppr,
                                color,
                                rec_ID,
                                aspect=aspect,
                                stim=None,
                                variant=variant,
                                x_mode="sweep"
                            )"""
    new_ppr_plot = """                        for variant in ["raw", "norm"]:
                            self.plot_line(
                                f"{label} PPR {aspect} {variant}",
                                axid,
                                common_sweeps,
                                ppr,
                                color,
                                rec_ID,
                                aspect=aspect,
                                stim=None,
                                variant=variant,
                                x_mode="sweep",
                                marker="o"
                            )"""
    content = content.replace(old_ppr_plot, new_ppr_plot)
    
    with open("src/lib/ui_plot.py", "w") as f:
        f.write(content)
    print("Success: added marker support to plot_line")
else:
    print("Failed")
