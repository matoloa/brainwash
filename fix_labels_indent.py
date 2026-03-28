with open("src/lib/ui_plot.py", "r") as f:
    content = f.read()

bad_else = """        else:
            if uistate.checkBox["norm_EPSP"]:
                ax1.set_ylabel("Amplitude %")
                ax2.set_ylabel("Slope %")
            else:
                ax1.set_ylabel("Amplitude (mV)")
                ax2.set_ylabel("Slope (mV/ms)")

            ax1.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
            ax2.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
            ax1.xaxis.set_major_formatter(uistate.x_axis_formatter())"""

# Wait, if bad_else exists, it means the formatter lines were inside the else block natively! Let's check.
