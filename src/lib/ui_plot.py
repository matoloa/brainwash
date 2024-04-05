import seaborn as sns
import numpy as np

class UIplot():
    def __init__(self, uistate):
        self.uistate = uistate
        print(f"UIplot instantiated {self.uistate.anyView()}")

    def hideAll(self, axm, ax1, ax2):
        for ax in [axm, ax1, ax2]:
            for line in ax.get_lines():
                line.set_visible(False)
            legend = ax.get_legend()
            if legend is not None:
                legend.remove()
        print("All lines hidden")

    def purge(self, rec, axm, ax1, ax2):
        print(f"Purging {rec}...")
        # remove the line named rec from axm
        for line in axm.get_lines():
            if line.get_label() == rec:
                line.remove()
                # remove subplots via uistate.plotted
                subplots = self.uistate.plotted[rec] # list of subplots of rec
                all_plots = axm.get_lines() + ax1.get_lines() + ax2.get_lines() # list of all lines
                for line in all_plots:
                    if line.get_label() in subplots:
                        line.remove()
                del self.uistate.plotted[rec]
    
    def graph(self, dict_row, dfmean, dfoutput, axm, ax1, ax2):
        print(f"Graphing {dict_row['recording_name']}...")
        rec_name = dict_row['recording_name']
        rec_filter = dict_row['filter'] # the filter currently used for this recording
        t_EPSP_amp = dict_row['t_EPSP_amp']
        t_EPSP_slope_start = dict_row['t_EPSP_slope_start']
        t_EPSP_slope_end = dict_row['t_EPSP_slope_end']
        t_volley_amp = dict_row['t_volley_amp']
        volley_amp_mean = dict_row['volley_amp_mean']
        t_volley_slope_start = dict_row['t_volley_slope_start']
        t_volley_slope_end = dict_row['t_volley_slope_end']
        volley_slope_mean = dict_row['volley_slope_mean']
        # plot relevant filter of dfmean on main_canvas_mean
        if rec_filter != 'voltage':
            label = f"{rec_name} ({rec_filter})"
        else:
            label = rec_name

        # persist a custom-named lineplot and list in uisate.plotted
        _ = sns.lineplot(ax=axm, label=label, data=dfmean, y=rec_filter, x="time", color="black")
        self.uistate.plotted[label] = []
        plotted = self.uistate.plotted[label]
   
        # plot them all, don't bother with show/hide
        out = dfoutput # TODO: enable switch to dfdiff?

        if not np.isnan(t_EPSP_amp):
            y_position = dfmean.loc[dfmean.time == t_EPSP_amp, rec_filter]
            axm.plot(t_EPSP_amp, y_position, marker='o', markerfacecolor='green', markeredgecolor='green', markersize=10, alpha=0.3, label=f"{label} EPSP amp marker")
            subplot = f"{label} EPSP amp"
            plotted.append(subplot)
            _ = sns.lineplot(ax=ax1, data=out, y='EPSP_amp', x="sweep", color="green", linestyle='--', alpha=0.5, label=subplot)
            if 'EPSP_amp_norm' in out.columns:
                subplot = f"{label} EPSP amp norm"
                print(f"EPSP_amp_norm in {rec_name} out")
                plotted.append(subplot)
                _ = sns.lineplot(ax=ax1, data=out, y='EPSP_amp_norm', x="sweep", color="green", linestyle='--', alpha=0.5, label=subplot)
            else:
                print(f"EPSP_amp_norm not in {rec_name} out")
        if not np.isnan(t_EPSP_slope_start):
            x_start = t_EPSP_slope_start
            x_end = t_EPSP_slope_end
            y_start = dfmean[rec_filter].iloc[(dfmean['time'] - x_start).abs().idxmin()]
            y_end = dfmean[rec_filter].iloc[(dfmean['time'] - x_end).abs().idxmin()]
            subplot = f"{label} EPSP slope marker"
            plotted.append(subplot)
            axm.plot([x_start, x_end], [y_start, y_end], color='green', linewidth=10, alpha=0.3, label=subplot)
            subplot = f"{label} EPSP slope"
            plotted.append(subplot)
            _ = sns.lineplot(ax=ax2, data=out, y='EPSP_slope', x="sweep", color="green", alpha = 0.3, label=subplot)
            #if out has the column 'EPSP_slope_norm', plot it
            if 'EPSP_slope_norm' in out.columns:
                subplot = f"{label} EPSP slope norm"
                print(f"EPSP_slope_norm in {rec_name} out")
                plotted.append(subplot)
                _ = sns.lineplot(ax=ax2, data=out, y='EPSP_slope_norm', x="sweep", color="green", alpha = 0.3, label=subplot)
            else:
                print(f"EPSP_slope_norm not in {rec_name} out")
        if not np.isnan(t_volley_amp):
            y_position = dfmean.loc[dfmean.time == t_volley_amp, rec_filter]
            subplot = f"{label} volley amp marker"
            plotted.append(subplot)
            axm.plot(t_volley_amp, y_position, marker='o', markerfacecolor='blue', markeredgecolor='blue', markersize=10, alpha = 0.3, label=subplot)
            subplot = f"{label} volley amp mean"
            plotted.append(subplot)
            ax1.axhline(y=volley_amp_mean, color='blue', alpha = 0.3, linestyle='--', label=subplot)
        if not np.isnan(t_volley_slope_start):
            x_start = t_volley_slope_start
            x_end = t_volley_slope_end
            y_start = dfmean[rec_filter].iloc[(dfmean['time'] - x_start).abs().idxmin()]
            y_end = dfmean[rec_filter].iloc[(dfmean['time'] - x_end).abs().idxmin()]
            subplot = f"{label} volley slope marker"
            plotted.append(subplot)
            axm.plot([x_start, x_end], [y_start, y_end], color='blue', linewidth=10, alpha=0.3, label=subplot)
            subplot = f"{label} volley slope mean"
            plotted.append(subplot)
            ax2.axhline(y=volley_slope_mean, color='blue', alpha = 0.3, label=subplot)

    def plotUpdate(self, row, aspect, dfmean, mouseover_out, axm, ax_out, norm=False):
        rec_filter = row['filter']  # the filter currently used for this recording
        plot_to_update = f"{row['recording_name']} {aspect} marker"

        if aspect in ['EPSP slope', 'volley slope']:
            x_start = row[f't_{aspect.replace(" ", "_")}_start']
            x_end = row[f't_{aspect.replace(" ", "_")}_end']
            y_start = dfmean[rec_filter].iloc[(dfmean['time'] - x_start).abs().idxmin()]
            y_end = dfmean[rec_filter].iloc[(dfmean['time'] - x_end).abs().idxmin()]
            self.updateLine(axm, plot_to_update, [x_start, x_end], [y_start, y_end])
            if aspect == 'volley slope':
                self.updateOutMean(ax_out, aspect, row)

        elif aspect in ['EPSP amp', 'volley amp']:
            t_amp = row[f't_{aspect.replace(" ", "_")}']
            y_position = dfmean.loc[dfmean.time == t_amp, rec_filter].item()
            self.updateLine(axm, plot_to_update, t_amp, y_position)
            if aspect == 'volley amp':
                self.updateOutMean(ax_out, aspect, row)

        if norm:
            self.updateOutLine(ax_out, row, f"{aspect} norm", mouseover_out)
        else:
            self.updateOutLine(ax_out, row, aspect, mouseover_out)


    def updateLine(self, axm, plot_to_update, x_data, y_data):
        for line in axm.get_lines():
            if line.get_label() == plot_to_update:
                line.set_xdata(x_data)
                line.set_ydata(y_data)
                axm.figure.canvas.draw()
                break

    def updateOutLine(self, ax_out, row, aspect, mouseover_out):
        print(f"Updating {row['recording_name']} {aspect}")
        for line in ax_out.get_lines():
            if line.get_label() == f"{row['recording_name']} {aspect}":
                line.set_ydata(mouseover_out[0].get_ydata())
                ax_out.figure.canvas.draw()
                break

    def updateOutMean(self, ax_out, aspect, row):
        rec_name = row['recording_name']
        mean = row[f'{aspect.replace(" ", "_")}_mean']
        for line in ax_out.get_lines():
            if line.get_label() == f"{rec_name} {aspect} mean":
                line.set_ydata(mean)
                ax_out.figure.canvas.draw()
                break

    def updateEPSPout(self, rec_name, out, ax1, ax2):
        for line in ax1.get_lines():
            if line.get_label() == f"{rec_name} EPSP amp":
                line.set_ydata(out['EPSP_amp'])
            if line.get_label() == f"{rec_name} EPSP amp norm":
                line.set_ydata(out['EPSP_amp_norm'])
                ax1.figure.canvas.draw()
        for line in ax2.get_lines():
            if line.get_label() == f"{rec_name} EPSP slope":
                line.set_ydata(out['EPSP_slope'])
            if line.get_label() == f"{rec_name} EPSP slope norm":
                line.set_ydata(out['EPSP_slope_norm'])
                ax2.figure.canvas.draw()

