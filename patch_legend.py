with open("src/lib/ui_plot.py", "r") as f:
    content = f.read()

old_leg = """        for axid, loc in zip(axids, legend_loc):
            recs_on_axis = {key: value for key, value in dd_recs.items() if value["axis"] == axid and not key.endswith(" marker")}
            axis_legend = {key: value["line"] for key, value in recs_on_axis.items()}
            if axid in ["ax1", "ax2"]:
                groups_on_axis = {key: value for key, value in dd_groups.items() if value["axis"] == axid}
                axis_legend.update({key: value["line"] for key, value in groups_on_axis.items()})
            axis = getattr(uistate, axid)
            if axis_legend:
                axis.legend(axis_legend.values(), axis_legend.keys(), loc=loc)
            else:
                if axis.get_legend():
                    axis.get_legend().remove()"""

new_leg = """        is_pp = getattr(uistate, "experiment_type", "time") == "PP"
        for axid, loc in zip(axids, legend_loc):
            recs_on_axis = {key: value for key, value in dd_recs.items() if value["axis"] == axid and not key.endswith(" marker")}
            axis_legend = {key: value["line"] for key, value in recs_on_axis.items()}
            if axid in ["ax1", "ax2"]:
                groups_on_axis = {key: value for key, value in dd_groups.items() if value["axis"] == axid}
                axis_legend.update({key: value["line"] for key, value in groups_on_axis.items()})
            axis = getattr(uistate, axid)
            if axis_legend and not is_pp:
                axis.legend(axis_legend.values(), axis_legend.keys(), loc=loc)
            else:
                if axis.get_legend():
                    axis.get_legend().remove()"""

if old_leg in content:
    content = content.replace(old_leg, new_leg)
    with open("src/lib/ui_plot.py", "w") as f:
        f.write(content)
    print("Patched legends in graphRefresh")
else:
    print("Failed")
