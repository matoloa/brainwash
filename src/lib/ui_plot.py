import seaborn as sns
import numpy as np
from matplotlib.lines import Line2D 

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

    def graphGroups(self, df_groups, dict_group_means, ax1, ax2):
        print(f"Graphing groups {df_groups.group_ID.unique()}:")
        # cycle through the reows of df_groups and print the group_ID, group_name, and color for each one
        for index, row in df_groups.iterrows():
            group_ID = row['group_ID']
            group_name = row['group_name']
            color = row['color']
            print(f"group_ID: {group_ID}, group_name: {group_name}, color: {color}")
            df = dict_group_means[group_ID]
            _ = sns.lineplot(ax=ax2, data=df, y='EPSP_slope_mean', x="sweep", color=color, alpha=0.5, label=f"{group_name} EPSP slope")
            #_ = sns.lineplot(ax=ax1, data=df, y='EPSP_amp_mean', x="sweep", color=color, alpha=0.5, label="EPSP amp")
            #_ = sns.lineplot(ax=ax1, data=df, y='volley_amp_mean', x="sweep", color=color, alpha=0.5, label="volley amp")
            #_ = sns.lineplot(ax=ax2, data=df, y='volley_slope_mean', x="sweep", color=color, alpha=0.5, label="volley slope")
            #_ = sns.lineplot(ax=ax2, data=df, y='EPSP_slope_mean', x="sweep", color=color, alpha=0.5, label="EPSP slope")


    def graphUpdate(self, df_selected, axm, ax1, ax2):
        # toggle show/hide of lines on axm, ax1 and ax2: show only selected and imported lines, only appropriate aspects
        print("graphUpdate")
        uistate = self.uistate
        #print("uistate.plotted: ", uistate.plotted)
        df_parsed_selection = df_selected[df_selected['sweeps'] != "..."]
        if df_parsed_selection.empty or not uistate.anyView():
            self.hideAll(axm, ax1, ax2)
        else:
            # axm, set visibility of lines and build legend
            axm_legend = self.graphVisible(axis=axm, show=uistate.to_axm(df_parsed_selection))
            axm.legend(axm_legend.values(), axm_legend.keys(), loc='upper right')
            ax1_legend = self.graphVisible(axis=ax1, show=uistate.to_ax1(df_parsed_selection))
            ax1.legend(ax1_legend.values(), ax1_legend.keys(), loc='upper right')
            ax2_legend = self.graphVisible(axis=ax2, show=uistate.to_ax2(df_parsed_selection))
            ax2.legend(ax2_legend.values(), ax2_legend.keys(), loc='lower right')

        # arrange axes and labels
        axm.set_xlabel("Time (s)")
        axm.set_ylabel("Voltage (V)")
        # x and y limits
        axm.set_xlim(uistate.zoom['mean_xlim'])
        axm.set_ylim(uistate.zoom['mean_ylim'])

        if uistate.checkBox['norm_EPSP']:
            ax1.set_ylabel("Amplitude %")
            ax2.set_ylabel("Slope %")
            ax1.set_ylim(0, 550)
            ax2.set_ylim(0, 550)
        else:
            ax1.set_ylabel("Amplitude (mV)")
            ax2.set_ylabel("Slope (mV/ms)")
            ax1.set_ylim(uistate.zoom['output_ax1_ylim'])
            ax2.set_ylim(uistate.zoom['output_ax2_ylim'])
        self.oneAxisLeft(ax1, ax2)
        # redraw
        axm.figure.canvas.draw()
        ax1.figure.canvas.draw() # ax2 should be on the same canvas


        # # Below is the instruction to plot groups. TODO: Move to a separate functions
        # if len(uistate.group_show) < 1:
        #     return
        
        # if df_parsed_selection.empty: # If df is empty, get all group_IDs from uisub.df_groups
        #     group_IDs_to_plot = uisub.df_groups['group_ID'].tolist()
        #     df_groups = uisub.df_groups
        # else: # If df is not empty, get group_IDs from df (selected and parsed rows)
        #     group_IDs_to_plot = df_parsed_selection['group_IDs'].str.split(',').sum()
        #     df_groups = uisub.df_groups[uisub.df_groups['group_ID'].isin(group_IDs_to_plot)]
        # print(f"group_IDs_to_plot: {group_IDs_to_plot}")
        # for str_ID in group_IDs_to_plot:
        #     uisub.get_dfgroupmean(str_ID)
        # self.graphGroups(df_groups, uisub.dict_group_means, ax1, ax2)

    def graphVisible(self, axis, show): # toggles visibility per selection and sets Legend of axis
        dict_lines = {item.get_label(): item for item in axis.get_children() if isinstance(item, Line2D)}
        #print(f"dict_lines: {dict_lines.keys()}")
        dict_legend = {}
        for label, line in dict_lines.items():
            visible = label in show if show else False
            line.set_visible(visible)
            if visible and not label.endswith(" marker"):
                dict_legend[label] = line
        return dict_legend


    def oneAxisLeft(self, ax1, ax2):
        uistate = self.uistate
        # sets ax1 and ax2 visibility and position
        ax1.set_visible(uistate.ampView())
        ax2.set_visible(uistate.slopeView())
        # print(f"oneAxisLeft - uistate.ampView: {uistate.ampView()}, uistate.slopeView: {uistate.slopeView()}, uistate.slopeOnly: {uistate.slopeOnly()}")
        if uistate.slopeOnly():
            ax2.yaxis.set_label_position("left")
            ax2.yaxis.set_ticks_position("left")
        else:
            ax2.yaxis.set_label_position("right")
            ax2.yaxis.set_ticks_position("right")

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

