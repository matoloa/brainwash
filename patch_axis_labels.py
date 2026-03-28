with open("src/lib/ui_plot.py", "r") as f:
    content = f.read()

old_labels = """        if getattr(uistate, "experiment_type", "time") == "io":
            io_out = getattr(uistate, "io_output", "EPSPamp")
            ax2.set_ylabel("")
            if "slope" in io_out.lower():
                ax1.set_ylabel("EPSP Slope %" if uistate.checkBox["norm_EPSP"] else "EPSP Slope (mV/ms)")
            else:
                ax1.set_ylabel("EPSP Amplitude %" if uistate.checkBox["norm_EPSP"] else "EPSP Amplitude (mV)")

            ax1.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
            ax1.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
            ax2.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
            ax2.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
        else:
            if uistate.checkBox["norm_EPSP"]:
                ax1.set_ylabel("Amplitude %")
                ax2.set_ylabel("Slope %")
            else:
                ax1.set_ylabel("Amplitude (mV)")
                ax2.set_ylabel("Slope (mV/ms)")"""

new_labels = """        exp_type = getattr(uistate, "experiment_type", "time")
        if exp_type == "io":
            io_out = getattr(uistate, "io_output", "EPSPamp")
            ax2.set_ylabel("")
            if "slope" in io_out.lower():
                ax1.set_ylabel("EPSP Slope %" if uistate.checkBox["norm_EPSP"] else "EPSP Slope (mV/ms)")
            else:
                ax1.set_ylabel("EPSP Amplitude %" if uistate.checkBox["norm_EPSP"] else "EPSP Amplitude (mV)")

            ax1.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
            ax1.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
            ax2.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
            ax2.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
        elif exp_type == "PP":
            ax1.set_ylabel("PPR (%)")
            ax2.set_ylabel("PPR (%)")
            
            ax1.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
            ax2.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
            ax1.xaxis.set_major_formatter(uistate.x_axis_formatter())
        else:
            if uistate.checkBox["norm_EPSP"]:
                ax1.set_ylabel("Amplitude %")
                ax2.set_ylabel("Slope %")
            else:
                ax1.set_ylabel("Amplitude (mV)")
                ax2.set_ylabel("Slope (mV/ms)")"""

if old_labels in content:
    content = content.replace(old_labels, new_labels)
    with open("src/lib/ui_plot.py", "w") as f:
        f.write(content)
    print("Success: Updated Axis Labels")
else:
    print("Failed to find old labels block")
