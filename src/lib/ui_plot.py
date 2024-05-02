import seaborn as sns
import numpy as np
from matplotlib import style
from matplotlib.lines import Line2D


class UIplot():
    def __init__(self, uistate):
        self.uistate = uistate
        print(f"UIplot instantiated: {self.uistate.anyView()}")


    def xDeselect(self, ax):
        # clear previous axvlines and axvspans
        ax1, ax2 = self.uistate.ax1, self.uistate.ax2
        if ax == ax1 or ax == ax2:
            axlines = ax1.get_lines() + ax2.get_lines()
            axpatches = ax1.patches + ax2.patches
        else:
            axlines = ax.get_lines()
            axpatches = ax.patches

        for line in axlines:
            if line.get_label() == 'xSelect':
                line.remove()
        for patch in axpatches:
            if patch.get_label() == 'xSelect':
                patch.remove()
        ax.figure.canvas.draw()


    def xSelect(self, canvas, slopeAx=None):
        # draws a selected range of x values on <canvas>
        if slopeAx is not None:
            if slopeAx:
                ax = self.uistate.ax2
            else:
                ax = self.uistate.ax1
        else:
            ax = canvas.axes
        self.xDeselect(ax)

        # draw new axvlines and axvspans
        start, end = self.uistate.x_on_click, self.uistate.x_drag
        if end is None:
            print(f"Selected x: {start}")
            ax.axvline(x=start, color='blue', label='xSelect')
        else:
            print(f"Selected x_range: {start} - {end}")
            if start is None:
                return
            elif start > end:
                start, end = end, start
            ax.axvline(x=start, color='blue', label='xSelect')
            ax.axvline(x=end, color='blue', label='xSelect')
            ax.axvspan(start, end, color='blue', alpha=0.1, label='xSelect')
        canvas.draw()


    def styleUpdate(self):
        axm, axe, ax1, ax2 = self.uistate.axm, self.uistate.axe, self.uistate.ax1, self.uistate.ax2
        if self.uistate.darkmode:
            style.use('dark_background')
            for ax in [axm, axe, ax1, ax2]:
                ax.figure.patch.set_facecolor('#333333')
                ax.set_facecolor('#333333')
                ax.xaxis.label.set_color('white')
                ax.yaxis.label.set_color('white')
                ax.tick_params(colors='white')
            #print("Dark mode activated")
        else:
            style.use('default')
            for ax in [axm, axe, ax1, ax2]:
                ax.figure.patch.set_facecolor('white')
                ax.set_facecolor('white')
                ax.xaxis.label.set_color('black')
                ax.yaxis.label.set_color('black')
                ax.tick_params(colors='black')
            #print("Default mode activated")


    def hideAll(self):
        axm, axe, ax1, ax2 = self.uistate.axm, self.uistate.axe, self.uistate.ax1, self.uistate.ax2
        for ax in [axm, axe, ax1, ax2]:
            for line in ax.get_lines():
                line.set_visible(False)
            legend = ax.get_legend()
            if legend is not None:
                legend.remove()
        print("All lines hidden")


    def unPlot(self, rec_ID):
        dict_rec = self.uistate.dict_rec_label_ID_line
        keys_to_remove = [key for key, value in dict_rec.items() if rec_ID == value[0]]
        for key in keys_to_remove:
            dict_rec[key][1].remove()
            del dict_rec[key]


    def unPlotGroup(self, group_ID):
        dict_group = self.uistate.dict_group_label_ID_line_SEM
        keys_to_remove = [key for key, value in dict_group.items() if group_ID == value[0]]
        for key in keys_to_remove:
            dict_group[key][1].remove()
            dict_group[key][2].remove()
            del dict_group[key]


    def graphRefresh(self):
        # toggle show/hide of lines on axe, ax1 and ax2: show only selected and imported lines, only appropriate aspects
        axm, axe, ax1, ax2 = self.uistate.axm, self.uistate.axe, self.uistate.ax1, self.uistate.ax2
        print("graphRefresh")
        uistate = self.uistate
        if uistate.df_recs2plot is None or not uistate.anyView():
            self.hideAll()
        else:
            # set visibility of recording lines and build legend
            axm_legend = self.set_visible_get_legend(axis=axm, show=uistate.to_axm(uistate.df_recs2plot))
            axm.legend(axm_legend.values(), axm_legend.keys(), loc='upper right')
            axe_legend = self.set_visible_get_legend(axis=axe, show=uistate.to_axe(uistate.df_recs2plot))
            axe.legend(axe_legend.values(), axe_legend.keys(), loc='upper right')
            ax1_legend = self.set_visible_get_legend(axis=ax1, show=uistate.to_ax1(uistate.df_recs2plot))
            ax1.legend(ax1_legend.values(), ax1_legend.keys(), loc='upper right')
            ax2_legend = self.set_visible_get_legend(axis=ax2, show=uistate.to_ax2(uistate.df_recs2plot))
            ax2.legend(ax2_legend.values(), ax2_legend.keys(), loc='lower right')

        for label, ID_line_fill in uistate.dict_group_label_ID_line_SEM.items():
            group_ID = ID_line_fill[0]
            str_show = uistate.df_groups.loc[uistate.df_groups['group_ID'] == group_ID, 'show'].values[0]
            if uistate.df_recs2plot is not None and not getattr(uistate.df_recs2plot, 'empty', True):
                if 'group_IDs' in uistate.df_recs2plot.columns and any(uistate.df_recs2plot['group_IDs'].str.contains(group_ID)):
                    ID_line_fill[1].set_visible(bool(str_show == 'True'))
                    ID_line_fill[2].set_visible(bool(str_show == 'True'))
                else: # always hidden, as none of its recordings are selected
                    ID_line_fill[1].set_visible(False)
                    ID_line_fill[2].set_visible(False)
            else: # show all checked groups, as no recordings are selected
                ID_line_fill[1].set_visible(bool(str_show == 'True'))
                ID_line_fill[2].set_visible(bool(str_show == 'True'))

        # arrange axes and labels
        axm.axis('off')

        axe.set_xlabel("Time (s)")
        axe.set_ylabel("Voltage (V)")
        axe.set_xlim(uistate.zoom['mean_xlim'])
        axe.set_ylim(uistate.zoom['mean_ylim'])

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
        self.oneAxisLeft()

        # redraw
        axm.figure.canvas.draw()
        axe.figure.canvas.draw()
        ax1.figure.canvas.draw() # ax2 should be on the same canvas


    def set_visible_get_legend(self, axis, show): # toggles visibility per selection, sets Legend of axis and returns dict_legends{label: line object}
        dict_lines = {item.get_label(): item for item in axis.get_children() if isinstance(item, Line2D)}
        #print(f"dict_lines: {dict_lines.keys()}")
        dict_legend = {}
        for label, line in dict_lines.items():
            visible = label in show if show else False
            line.set_visible(visible)
            if visible and not label.endswith(" marker"):
                dict_legend[label] = line
        return dict_legend


    def oneAxisLeft(self):
        ax1, ax2 = self.uistate.ax1, self.uistate.ax2
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

    def addRow(self, p_row, t_row, dfmean, dfoutput):
        axm, axe, ax1, ax2 = self.uistate.axm, self.uistate.axe, self.uistate.ax1, self.uistate.ax2
        rec_ID = p_row['ID']
        rec_name = p_row['recording_name']
        print(f"Graphing {rec_name}...")
        rec_filter = p_row['filter'] # the filter currently used for this recording
        t_EPSP_amp = t_row['t_EPSP_amp']
        t_EPSP_slope_start = t_row['t_EPSP_slope_start']
        t_EPSP_slope_end = t_row['t_EPSP_slope_end']
        t_volley_amp = t_row['t_volley_amp']
        volley_amp_mean = t_row['volley_amp_mean']
        t_volley_slope_start = t_row['t_volley_slope_start']
        t_volley_slope_end = t_row['t_volley_slope_end']
        volley_slope_mean = t_row['volley_slope_mean']
        # plot relevant filter of dfmean on canvasEvent
        if rec_filter != 'voltage':
            label = f"{rec_name} ({rec_filter})"
        else:
            label = rec_name

        # add to Mean
        mean_label = f"mean_{rec_name}"
        line, = axm.plot(dfmean["time"], dfmean[rec_filter], color="black", label=mean_label)
        self.uistate.dict_rec_label_ID_line[mean_label] = rec_ID, line

        # add to Events
        line, = axe.plot(dfmean["time"], dfmean[rec_filter], color="black", label=label)
        self.uistate.dict_rec_label_ID_line[label] = rec_ID, line
   
        # plot them all, don't bother with show/hide
        out = dfoutput # TODO: enable switch to dfdiff?

        if not np.isnan(t_EPSP_amp):
            y_position = dfmean.loc[dfmean.time == t_EPSP_amp, rec_filter]
            marker, = axe.plot(t_EPSP_amp, y_position, marker='o', markerfacecolor='green', markeredgecolor='green', markersize=10, alpha=0.3, label=f"{label} EPSP amp marker")
            subplot = f"{label} EPSP amp"
            line, = ax1.plot(out["sweep"], out['EPSP_amp'], color="green", linestyle='--', alpha=0.5, label=subplot)
            self.uistate.dict_rec_label_ID_line[subplot] = rec_ID, line
            if 'EPSP_amp_norm' in out.columns:
                subplot = f"{label} EPSP amp norm"
                line, = ax1.plot(out["sweep"], out['EPSP_amp_norm'], color="green", linestyle='--', alpha=0.5, label=subplot)
                self.uistate.dict_rec_label_ID_line[subplot] = rec_ID, line
        if not np.isnan(t_EPSP_slope_start):
            x_start = t_EPSP_slope_start
            x_end = t_EPSP_slope_end
            y_start = dfmean[rec_filter].iloc[(dfmean['time'] - x_start).abs().idxmin()]
            y_end = dfmean[rec_filter].iloc[(dfmean['time'] - x_end).abs().idxmin()]
            subplot = f"{label} EPSP slope marker"
            line, = axe.plot([x_start, x_end], [y_start, y_end], color='green', linewidth=10, alpha=0.3, label=subplot)
            self.uistate.dict_rec_label_ID_line[subplot] = rec_ID, line
            subplot = f"{label} EPSP slope"
            line, = ax2.plot(out["sweep"], out['EPSP_slope'], color="green", alpha = 0.3, label=subplot)
            self.uistate.dict_rec_label_ID_line[subplot] = rec_ID, line
            if 'EPSP_slope_norm' in out.columns:
                subplot = f"{label} EPSP slope norm"
                line, = ax2.plot(out["sweep"], out['EPSP_slope_norm'], color="green", alpha = 0.3, label=subplot)
                self.uistate.dict_rec_label_ID_line[subplot] = rec_ID, line
        if not np.isnan(t_volley_amp):
            y_position = dfmean.loc[dfmean.time == t_volley_amp, rec_filter]
            subplot = f"{label} volley amp marker"
            marker, = axe.plot(t_volley_amp, y_position, marker='o', markerfacecolor='blue', markeredgecolor='blue', markersize=10, alpha = 0.3, label=subplot)
            self.uistate.dict_rec_label_ID_line[subplot] = rec_ID, marker
            subplot = f"{label} volley amp mean"
            line = ax1.axhline(y=volley_amp_mean, color='blue', alpha = 0.3, linestyle='--', label=subplot)
            self.uistate.dict_rec_label_ID_line[subplot] = rec_ID, line
        if not np.isnan(t_volley_slope_start):
            x_start = t_volley_slope_start
            x_end = t_volley_slope_end
            y_start = dfmean[rec_filter].iloc[(dfmean['time'] - x_start).abs().idxmin()]
            y_end = dfmean[rec_filter].iloc[(dfmean['time'] - x_end).abs().idxmin()]
            subplot = f"{label} volley slope marker"
            line, = axe.plot([x_start, x_end], [y_start, y_end], color='blue', linewidth=10, alpha=0.3, label=subplot)
            self.uistate.dict_rec_label_ID_line[subplot] = rec_ID, line
            subplot = f"{label} volley slope mean"
            line = ax2.axhline(y=volley_slope_mean, color='blue', alpha = 0.3, label=subplot)
            self.uistate.dict_rec_label_ID_line[subplot] = rec_ID, line

    def addGroup(self, df_group_row, df_groupmean):
        ax1, ax2 = self.uistate.ax1, self.uistate.ax2
        group_ID = df_group_row['group_ID']
        group_name = df_group_row['group_name']
        color = df_group_row['color']
        label = f"{group_name} EPSP slope"
        if df_groupmean['EPSP_amp_mean'].notna().any() & self.uistate.checkBox['EPSP_amp']:
            label = f"{group_name} EPSP amp"
            line, = ax1.plot(df_groupmean.sweep, df_groupmean.EPSP_amp_mean, color=color, alpha=0.5, linestyle='--', label=label)
            fill = ax1.fill_between(df_groupmean.sweep, df_groupmean.EPSP_amp_mean + df_groupmean.EPSP_amp_SEM, df_groupmean.EPSP_amp_mean - df_groupmean.EPSP_amp_SEM, alpha=0.3, color=color)
            self.uistate.dict_group_label_ID_line_SEM[label] = [group_ID, line, fill]
        if df_groupmean['EPSP_slope_mean'].notna().any() & self.uistate.checkBox['EPSP_slope']:
            label = f"{group_name} EPSP slope"
            line, = ax2.plot(df_groupmean.sweep, df_groupmean.EPSP_slope_mean, color=color, alpha=0.5, linestyle='--', label=label)
            fill = ax2.fill_between(df_groupmean.sweep, df_groupmean.EPSP_slope_mean + df_groupmean.EPSP_slope_SEM, df_groupmean.EPSP_slope_mean - df_groupmean.EPSP_slope_SEM, alpha=0.3, color=color)
            self.uistate.dict_group_label_ID_line_SEM[label] = [group_ID, line, fill]

    def plotUpdate(self, dfp_row, dft_row, aspect, dfmean):
        print(f"dfp_row: {dfp_row}, dft_row: {dft_row}")
        norm = self.uistate.checkBox['norm_EPSP']
        rec_filter = dfp_row['filter']  # the filter currently used for this recording
        plot_to_update = f"{dfp_row['recording_name']} {aspect} marker"

        if aspect in ['EPSP slope', 'volley slope']:
            x_start = dft_row[f't_{aspect.replace(" ", "_")}_start']
            x_end = dft_row[f't_{aspect.replace(" ", "_")}_end']
            y_start = dfmean[rec_filter].iloc[(dfmean['time'] - x_start).abs().idxmin()]
            y_end = dfmean[rec_filter].iloc[(dfmean['time'] - x_end).abs().idxmin()]
            self.updateLine(plot_to_update, [x_start, x_end], [y_start, y_end])
            if aspect == 'volley slope':
                self.updateOutMean(aspect, dft_row)
            else:
                if norm:
                    self.updateOutLine(dfp_row, f"{aspect} norm")
                else:
                    self.updateOutLine(dfp_row, f"{aspect}")
        elif aspect in ['EPSP amp', 'volley amp']:
            t_amp = dft_row[f't_{aspect.replace(" ", "_")}']
            y_position = dfmean.loc[dfmean.time == t_amp, rec_filter].item()
            self.updateLine(plot_to_update, t_amp, y_position)
            if aspect == 'volley amp':
                self.updateOutMean(aspect, dft_row)
            else:
                if norm:
                    self.updateOutLine(dfp_row, f"{aspect} norm")
                else:
                    self.updateOutLine(dfp_row, f"{aspect}")


    def updateLine(self, plot_to_update, x_data, y_data):
        axe = self.uistate.axe
        line = self.uistate.dict_rec_label_ID_line[plot_to_update]
        line[1].set_xdata(x_data)
        line[1].set_ydata(y_data)
        axe.figure.canvas.draw()

    def updateOutLine(self, row, aspect):
        mouseover_out = self.uistate.mouseover_out
        line = self.uistate.dict_rec_label_ID_line[f"{row['recording_name']} {aspect}"]
        line[1].set_ydata(mouseover_out[0].get_ydata())

    def updateOutMean(self, aspect, row):
        rec_name = row['recording_name']
        mean = row[f'{aspect.replace(" ", "_")}_mean']
        line = self.uistate.dict_rec_label_ID_line[f"{rec_name} {aspect} mean"]
        line[1].set_ydata(mean)

    def updateEPSPout(self, rec_name, out): # TODO: update this last remaining ax-cycle to use the dict
        ax1, ax2 = self.uistate.ax1, self.uistate.ax2
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

    def graphMouseover(self, event): # determine which maingraph event is being mouseovered
        axe = self.uistate.axe
        uistate = self.uistate
        def plotMouseover(action, axe):
            alpha = 0.8
            linewidth = 3 if 'resize' in action else 10
            if 'slope' in action:
                if 'EPSP' in action:
                    x_range = uistate.EPSP_slope_start_xy[0], uistate.EPSP_slope_end_xy[0]
                    y_range = uistate.EPSP_slope_start_xy[1], uistate.EPSP_slope_end_xy[1]
                    color = 'green'
                elif 'volley' in action:
                    x_range = uistate.volley_slope_start_xy[0], uistate.volley_slope_end_xy[0]
                    y_range = uistate.volley_slope_start_xy[1], uistate.volley_slope_end_xy[1]
                    color = 'blue'

                if uistate.mouseover_blob is None:
                    uistate.mouseover_blob = axe.scatter(x_range[1], y_range[1], color=color, s=100, alpha=alpha)
                else:
                    uistate.mouseover_blob.set_offsets([x_range[1], y_range[1]])
                    uistate.mouseover_blob.set_sizes([100])
                    uistate.mouseover_blob.set_color(color)

                if uistate.mouseover_plot is None:
                    uistate.mouseover_plot = axe.plot(x_range, y_range, color=color, linewidth=linewidth, alpha=alpha, label="mouseover")
                else:
                    uistate.mouseover_plot[0].set_data(x_range, y_range)
                    uistate.mouseover_plot[0].set_linewidth(linewidth)
                    uistate.mouseover_plot[0].set_alpha(alpha)
                    uistate.mouseover_plot[0].set_color(color)

            elif 'amp' in action:
                if 'EPSP' in action:
                    x, y = uistate.EPSP_amp_xy
                    color = 'green'
                elif 'volley' in action:
                    x, y = uistate.volley_amp_xy
                    color = 'blue'

                if uistate.mouseover_blob is None:
                    uistate.mouseover_blob = axe.scatter(x, y, color=color, s=100, alpha=alpha)
                else:
                    uistate.mouseover_blob.set_offsets([x, y])
                    uistate.mouseover_blob.set_sizes([100])
                    uistate.mouseover_blob.set_color(color)
        x = event.xdata
        y = event.ydata
        if x is None or y is None:
            return
        if event.inaxes == axe:
            zones = {
                'EPSP slope resize': uistate.EPSP_slope_resize_zone,
                'EPSP slope move': uistate.EPSP_slope_move_zone,
                'EPSP amp move': uistate.EPSP_amp_move_zone,
                'volley slope resize': uistate.volley_slope_resize_zone,
                'volley slope move': uistate.volley_slope_move_zone,
                'volley amp move': uistate.volley_amp_move_zone,
            }
            uistate.mouseover_action = None
            for action, zone in zones.items():
                checkbox_key = '_'.join(action.split(' ')[:2])  # Split the action string and use the first two parts as the checkbox key
                if uistate.checkBox.get(checkbox_key, False) and zone['x'][0] <= x <= zone['x'][1] and zone['y'][0] <= y <= zone['y'][1]:
                    uistate.mouseover_action = action
                    plotMouseover(action, axe)
                    break

            if uistate.mouseover_action is None:
                if uistate.mouseover_blob is not None:
                    uistate.mouseover_blob.set_sizes([0])
                if uistate.mouseover_plot is not None:
                    uistate.mouseover_plot[0].set_linewidth(0)

            axe.figure.canvas.draw()