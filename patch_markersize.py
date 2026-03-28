with open("src/lib/ui_plot.py", "r") as f:
    content = f.read()

old_def = """        alpha=None,
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
            (line,) = self.get_axis(axid).plot(x, y, color=color, label=label, alpha=alpha, linewidth=width, zorder=zorder, marker=marker)
        line.set_visible(False)"""

new_def = """        alpha=None,
        variant="raw",
        x_mode=None,
        marker=None,
        markersize=None,
    ):
        is_pp = getattr(self.uistate, "experiment_type", "time") == "PP"
        if is_pp and axid in ("ax1", "ax2") and "PPR" not in label:
            return
        zorder = 0 if width > 1 else 1
        alpha = alpha if alpha is not None else self.uistate.settings["alpha_line"]
        kwargs = {"color": color, "label": label, "alpha": alpha, "linewidth": width, "zorder": zorder}
        if marker is not None:
            kwargs["marker"] = marker
        if markersize is not None:
            kwargs["markersize"] = markersize
        (line,) = self.get_axis(axid).plot(x, y, **kwargs)
        line.set_visible(False)"""

if old_def in content:
    content = content.replace(old_def, new_def)
    with open("src/lib/ui_plot.py", "w") as f:
        f.write(content)
    print("Patched plot_line with markersize kwargs")
else:
    print("Failed to patch plot_line kwargs")
