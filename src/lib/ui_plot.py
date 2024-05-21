import seaborn as sns
import numpy as np
from matplotlib import style
from matplotlib.lines import Line2D
from matplotlib.colors import LinearSegmentedColormap

import time # counting time for functions

class UIplot():
    def __init__(self, uistate):
        self.uistate = uistate
        print(f"UIplot instantiated: {self.uistate.anyView()}")


    def xDeselect(self, ax, reset=False):
        # clear previous axvlines and axvspans
        ax1, ax2 = self.uistate.ax1, self.uistate.ax2
        if ax == ax1 or ax == ax2:
            axlines = ax1.get_lines() + ax2.get_lines()
            axpatches = ax1.patches + ax2.patches
            if reset:
                self.uistate.x_select['output_start'] = None
                self.uistate.x_select['output_end'] = None
        else: # axm
            axlines = ax.get_lines()
            axpatches = ax.patches
            if reset:
                self.uistate.x_select['mean_start'] = None
                self.uistate.x_select['mean_end'] = None

        for line in axlines:
            if line.get_label().startswith('xSelect'):
                line.remove()
        for patch in axpatches:
            if patch.get_label().startswith('xSelect'):
                patch.remove()
        ax.figure.canvas.draw()


    def xSelect(self, canvas):
        # draws a selected range of x values on <canvas>
        if canvas == self.uistate.axm.figure.canvas:
            ax = self.uistate.axm
            self.xDeselect(ax)
            if self.uistate.x_select['mean_end'] is None:
                print(f"Selected x: {self.uistate.x_select['mean_start']}")
                ax.axvline(x=self.uistate.x_select['mean_start'], color='blue', label='xSelect_x')
            else:
                start, end = self.uistate.x_select['mean_start'], self.uistate.x_select['mean_end']
                print(f"Selected x_range: {start} - {end}")
                ax.axvline(x=start, color='blue', label='xSelect_start')
                ax.axvline(x=end, color='blue', label='xSelect_end')
                ax.axvspan(start, end, color='blue', alpha=0.1, label='xSelect_span')
        else: # canvasOutput
            if self.uistate.checkBox['EPSP_slope']:
                ax = self.uistate.ax2
            else:
                ax = self.uistate.ax1
            self.xDeselect(ax) # will clear both ax1 and ax2, if fed either one
            if self.uistate.x_select['output_end'] is None:
                print(f"Selected x: {self.uistate.x_select['output_start']}")
                ax.axvline(x=self.uistate.x_select['output_start'], color='blue', label='xSelect_x')
            else:
                start, end = self.uistate.x_select['output_start'], self.uistate.x_select['output_end']
                print(f"Selected x_range: {start} - {end}")
                ax.axvline(x=start, color='blue', label='xSelect_start')
                ax.axvline(x=end, color='blue', label='xSelect_end')
                ax.axvspan(start, end, color='blue', alpha=0.1, label='xSelect_span')
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
            for patch in ax.patches:
                patch.remove()
            legend = ax.get_legend()
            if legend is not None:
                legend.remove()
        print("All lines hidden")


    def unPlot(self, rec_ID):
        dict_rec = self.uistate.dict_rec_labels
        dict_show = self.uistate.dict_rec_show
        keys_to_remove = [key for key, value in dict_rec.items() if rec_ID == value['rec_ID']]
        for key in keys_to_remove:
            dict_rec[key]['line'].remove()
            print(f"unPlot: {key} removed from dict_rec")
            del dict_rec[key]
            if key in dict_show:
                print(f"unPlot: {key} removed from dict_show")
                del dict_show[key]


    def unPlotGroup(self, group_ID):
        dict_group = self.uistate.dict_group_label_ID_line_SEM
        keys_to_remove = [key for key, value in dict_group.items() if group_ID == value[0]]
        for key in keys_to_remove:
            dict_group[key][1].remove()
            dict_group[key][2].remove()
            del dict_group[key]


    def graphRefresh(self):
        # show only selected and imported lines, only appropriate aspects
        print("graphRefresh")
        #t0 = time.time()
        uistate = self.uistate

        # Recordings
        if uistate.df_recs2plot is None or not uistate.anyView():
            self.hideAll()
        else:
            dict_rec = uistate.dict_rec_show
            axis_names = ['axm', 'axe', 'ax1', 'ax2']
            loc_values = ['upper right', 'upper right', 'upper right', 'lower right']
            for axis_name, loc in zip(axis_names, loc_values):
                dict_on_axis = {key: value for key, value in dict_rec.items() if value['axis'] == axis_name}
                axis_legend = {key: value['line'] for key, value in dict_on_axis.items() if not key.endswith(" marker")}
                for key, value in dict_on_axis.items():
                    value['line'].set_visible(True)
                axis = getattr(uistate, axis_name)
                axis.legend(axis_legend.values(), axis_legend.keys(), loc=loc)              
        # Groups
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
        axm, axe, ax1, ax2 = self.uistate.axm, self.uistate.axe, self.uistate.ax1, self.uistate.ax2
        axm.axis('off')
        axm.set_xlim(uistate.zoom['mean_xlim'])

        axe.set_xlabel("Time (s)")
        axe.set_ylabel("Voltage (V)")
        axe.set_xlim(uistate.zoom['event_xlim'])
        axe.set_ylim(uistate.zoom['event_ylim'])

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
        ax1.set_xlim(uistate.zoom['output_xlim'])
        ax2.set_xlim(uistate.zoom['output_xlim'])
        ax1.figure.subplots_adjust(bottom=0.2)
        print(f"ax1-2_xlim: {uistate.zoom['output_xlim']} enforced")
        self.oneAxisLeft()

        # maintain drag selections through reselection
        if uistate.x_select['mean_start'] is not None:
            self.xSelect(canvas = axm.figure.canvas)
        if uistate.x_select['output_start'] is not None:
            if uistate.checkBox['EPSP_slope']:
                self.xSelect(canvas = ax2.figure.canvas)
            else:
                self.xSelect(canvas = ax1.figure.canvas)

        # redraw
        axm.figure.canvas.draw()
        axe.figure.canvas.draw()
        ax1.figure.canvas.draw() # ax2 should be on the same canvas
        #print(f" - - {round((time.time() - t0) * 1000)} ms")


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

    def addRow(self, p_row, dft, dfmean, dfoutput):
        uistate = self.uistate
        axm, axe, ax1, ax2 = uistate.axm, uistate.axe, uistate.ax1, uistate.ax2
        rec_ID = p_row['ID']
        rec_name = p_row['recording_name']
        #print(f"addRow {rec_name}: {rec_ID}")
        rec_filter = p_row['filter'] # the filter currently used for this recording
        n_stims = len(dft)
        # plot relevant filter of dfmean on canvasEvent
        if rec_filter != 'voltage':
            label = f"{rec_name} ({rec_filter})"
        else:
            label = rec_name

        # add to Mean
        mean_label = f"mean {rec_name}"
        line, = axm.plot(dfmean["time"], dfmean[rec_filter], label=mean_label, color="black")
        uistate.dict_rec_labels[mean_label] = {'rec_ID':rec_ID, 'stim': None, 'line':line, 'axis':'axm'}

        colors = [(1, 0.5, 0), "green", "teal"]  # RGB for a redder orange
        cmap = LinearSegmentedColormap.from_list("", colors)
        list_gradient = {i: cmap(i/n_stims) for i in range(n_stims)}

        # process detected stims
        for i_stim, t_row in dft.iterrows():
            color = list_gradient[i_stim]
            stim_num = i_stim + 1 # 1-numbering (visible to user)
            t_stim = t_row['t_stim']
            stim_str = f" - stim {stim_num}"
            out = dfoutput[dfoutput['stim'] == stim_num]# TODO: enable switch to dfdiff?
            y_position = dfmean.loc[dfmean.time == t_stim, rec_filter].values[0] # returns index, y_value
            subplot = f"{mean_label}{stim_str} marker"
            line, = axm.plot(t_stim, y_position, marker='o', markerfacecolor=color, markeredgecolor=color, markersize=10, alpha=1, zorder=0, label=f"{subplot}")
            uistate.dict_rec_labels[subplot] = {'rec_ID':rec_ID, 'stim': stim_num, 'line':line, 'axis':'axm'}
            subplot = f"{mean_label}{stim_str} selection marker"
            line = axm.axvline(x=t_stim, color=color, linewidth=1, alpha=0.8, label=f"{subplot}")
            uistate.dict_rec_labels[subplot] = {'rec_ID':rec_ID, 'stim': stim_num, 'line':line, 'axis':'axm'}
            # convert all variables except t_stim to stim-specific time
            variables = ['t_EPSP_amp', 't_EPSP_slope_start', 't_EPSP_slope_end', 't_volley_amp', 't_volley_slope_start', 't_volley_slope_end']
            for var in variables:
               t_row[var] -= t_stim

            # add to Events
            stim_label = f"{label}{stim_str}"
            window_start = t_stim + uistate.settings['event_start']
            window_end = t_stim + uistate.settings['event_end']
            df_event = dfmean[(dfmean['time'] >= window_start) & (dfmean['time'] <= window_end)].copy()
            df_event['time'] = df_event['time'] - t_stim  # shift event so that t_stim is at time 0
            line, = axe.plot(df_event['time'], df_event[rec_filter], color=color, label=stim_label)
            uistate.dict_rec_labels[stim_label] = {'rec_ID':rec_ID, 'stim': stim_num, 'line':line, 'axis':'axe'}
            
            # plot markers on axe, output lines on ax1 and ax2
            out = dfoutput[dfoutput['stim'] == stim_num] # TODO: enable switch to dfdiff?
            rgb_EPSP_amp = uistate.settings['rgb_EPSP_amp']
            rgb_EPSP_slope = uistate.settings['rgb_EPSP_slope']
            rgb_volley_amp = uistate.settings['rgb_volley_amp']
            rgb_volley_slope = uistate.settings['rgb_volley_slope']
            a_mark, a_line, a_dot = uistate.settings['alpha_mark'], uistate.settings['alpha_line'], uistate.settings['alpha_dot']

            if not np.isnan(t_row['t_EPSP_amp']):
                subplot = f"{label}{stim_str} EPSP amp marker"
                y_position = df_event.loc[df_event.time == t_row['t_EPSP_amp'], rec_filter]
                line, = axe.plot(t_row['t_EPSP_amp'], y_position, marker='o', markerfacecolor='none', markeredgecolor=rgb_EPSP_amp, markersize=10, markeredgewidth=3, alpha=a_dot, zorder=0, label=subplot)
                uistate.dict_rec_labels[subplot] = {'rec_ID':rec_ID, 'stim': stim_num, 'line':line, 'axis':'axe'}
                subplot = f"{label}{stim_str} EPSP amp"
                line, = ax1.plot(out['sweep'], out['EPSP_amp'], color=rgb_EPSP_amp, alpha=a_line, zorder=3, label=subplot)
                uistate.dict_rec_labels[subplot] = {'rec_ID':rec_ID, 'stim': stim_num, 'line':line, 'axis':'ax1'}
                if 'EPSP_amp_norm' in out.columns:
                    subplot = f"{label}{stim_str} EPSP amp norm"
                    line, = ax1.plot(out["sweep"], out['EPSP_amp_norm'], color=rgb_EPSP_amp, zorder=3, alpha=a_line, label=subplot)
                    uistate.dict_rec_labels[subplot] = {'rec_ID':rec_ID, 'stim': stim_num, 'line':line, 'axis':'ax1'}
            if not np.isnan(t_row['t_EPSP_slope_start']):
                x_start = t_row['t_EPSP_slope_start']
                x_end = t_row['t_EPSP_slope_end']
                index = (df_event['time'] - x_start).abs().idxmin()
                y_start = df_event.loc[index, rec_filter] if index in df_event.index else None
                index = (df_event['time'] - x_end).abs().idxmin()
                y_end = df_event.loc[index, rec_filter] if index in df_event.index else None
                subplot = f"{label}{stim_str} EPSP slope marker"
                line, = axe.plot([x_start, x_end], [y_start, y_end], color=rgb_EPSP_slope, linewidth=10, alpha=a_mark, zorder=0, label=subplot)
                uistate.dict_rec_labels[subplot] = {'rec_ID':rec_ID, 'stim': stim_num, 'line':line, 'axis':'axe'}
                subplot = f"{label}{stim_str} EPSP slope"
                line, = ax2.plot(out["sweep"], out['EPSP_slope'], color=rgb_EPSP_slope, zorder=3, alpha=a_line, label=subplot)
                uistate.dict_rec_labels[subplot] = {'rec_ID':rec_ID, 'stim': stim_num, 'line':line, 'axis':'ax2'}
                if 'EPSP_slope_norm' in out.columns:
                    subplot = f"{label}{stim_str} EPSP slope norm"
                    line, = ax2.plot(out["sweep"], out['EPSP_slope_norm'], color=rgb_EPSP_slope, zorder=3, alpha=a_line, label=subplot)
                    uistate.dict_rec_labels[subplot] = {'rec_ID':rec_ID, 'stim': stim_num, 'line':line, 'axis':'ax2'}
            if not np.isnan(t_row['t_volley_amp']):
                y_position = df_event.loc[df_event.time == t_row['t_volley_amp'], rec_filter]
                subplot = f"{label}{stim_str} volley amp marker"
                line, = axe.plot(t_row['t_volley_amp'], y_position, marker='o', markerfacecolor='none', markeredgecolor=rgb_volley_amp, markersize=10, markeredgewidth=3, alpha=a_dot, zorder=0, label=subplot)
                uistate.dict_rec_labels[subplot] = {'rec_ID':rec_ID, 'stim': stim_num, 'line':line, 'axis':'axe'}
                subplot = f"{label}{stim_str} volley amp mean"
                line = ax1.axhline(y=t_row['volley_amp_mean'], color=rgb_volley_amp, linestyle=':', zorder=0, label=subplot)
                uistate.dict_rec_labels[subplot] = {'rec_ID':rec_ID, 'stim': stim_num, 'line':line, 'axis':'ax1'}
            if not np.isnan(t_row['t_volley_slope_start']):
                x_start = t_row['t_volley_slope_start']
                x_end = t_row['t_volley_slope_end']
                index = (df_event['time'] - x_start).abs().idxmin()
                y_start = df_event.loc[index, rec_filter] if index in df_event.index else None
                index = (df_event['time'] - x_end).abs().idxmin()
                y_end = df_event.loc[index, rec_filter] if index in df_event.index else None
                subplot = f"{label}{stim_str} volley slope marker"
                line, = axe.plot([x_start, x_end], [y_start, y_end], color=rgb_volley_slope, linewidth=10, alpha=a_mark, zorder=0, label=subplot)
                uistate.dict_rec_labels[subplot] = {'rec_ID':rec_ID, 'stim': stim_num, 'line':line, 'axis':'axe'}
                subplot = f"{label}{stim_str} volley slope mean"
                line = ax2.axhline(y=t_row['volley_slope_mean'], color=rgb_volley_slope, linestyle='--', zorder=0, label=subplot)
                uistate.dict_rec_labels[subplot] = {'rec_ID':rec_ID, 'stim': stim_num, 'line':line, 'axis':'ax2'}
        # print(f"uistate.dict_rec_labels.keys(): {uistate.dict_rec_labels.keys()}")

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

    def plotUpdate(self, p_row, t_row, aspect, data_x, data_y):
        norm = self.uistate.checkBox['norm_EPSP']
        rec_name = p_row['recording_name']
        stim_offset = t_row['t_stim']
        stim_str = f" - stim {t_row['stim']}"
        plot_to_update = f"{p_row['recording_name']}{stim_str} {aspect} marker"
        #print(f"plotUpdate: {plot_to_update}")

        if aspect in ['EPSP slope', 'volley slope']:
            x_start = t_row[f't_{aspect.replace(" ", "_")}_start']-stim_offset
            x_end = t_row[f't_{aspect.replace(" ", "_")}_end']-stim_offset
            y_start = data_y[np.abs(data_x - x_start).argmin()]
            y_end = data_y[np.abs(data_x - x_end).argmin()]
            self.updateLine(plot_to_update, [x_start, x_end], [y_start, y_end])
            if aspect == 'volley slope':
                label = f"{rec_name}{stim_str} {aspect} mean"
                mean = t_row[f'{aspect.replace(" ", "_")}_mean']
                self.updateOutMean(label, mean)
            else:
                label = f"{rec_name}{stim_str} {aspect}"
                if norm:
                    label += " norm"
                self.updateOutLine(label)
        elif aspect in ['EPSP amp', 'volley amp']:
            t_amp = t_row[f't_{aspect.replace(" ", "_")}'] - stim_offset
            y_position = data_y[np.abs(data_x - t_amp).argmin()]
            self.updateLine(plot_to_update, t_amp, y_position)
            if aspect == 'volley amp':
                label = f"{rec_name}{stim_str} {aspect} mean"
                mean = t_row[f'{aspect.replace(" ", "_")}_mean']
                self.updateOutMean(label, mean)
            else:
                label = f"{rec_name}{stim_str} {aspect}"
                if norm:
                    label += " norm"
                self.updateOutLine(label)


    def updateLine(self, plot_to_update, x_data, y_data):
        axe = self.uistate.axe
        linedict = self.uistate.dict_rec_labels[plot_to_update]
        print(f"updateLine: {plot_to_update}, linedict: {linedict}")
        linedict['line'].set_xdata(x_data)
        linedict['line'].set_ydata(y_data)
        axe.figure.canvas.draw()

    def updateOutLine(self, label):
        mouseover_out = self.uistate.mouseover_out
        linedict = self.uistate.dict_rec_labels[label]
        linedict['line'].set_ydata(mouseover_out[0].get_ydata())

    def updateOutMean(self, label, mean):
        linedict = self.uistate.dict_rec_labels[label]
        linedict['line'].set_ydata(mean)

    def updateEPSPout(self, rec_name, out): # TODO: update this last remaining ax-cycle to use the dict
        # OBSOLETE - called by norm, does not operate on stim-specific data!
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
        uistate = self.uistate
        axe = uistate.axe
        def plotMouseover(action, axe):
            alpha = 0.8
            linewidth = 3 if 'resize' in action else 10
            if 'slope' in action:
                if 'EPSP' in action:
                    x_range = uistate.EPSP_slope_start_xy[0], uistate.EPSP_slope_end_xy[0]
                    y_range = uistate.EPSP_slope_start_xy[1], uistate.EPSP_slope_end_xy[1]
                    color = uistate.settings['rgb_EPSP_slope']
                elif 'volley' in action:
                    x_range = uistate.volley_slope_start_xy[0], uistate.volley_slope_end_xy[0]
                    y_range = uistate.volley_slope_start_xy[1], uistate.volley_slope_end_xy[1]
                    color = uistate.settings['rgb_volley_slope']

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
                    color = uistate.settings['rgb_EPSP_amp']
                elif 'volley' in action:
                    x, y = uistate.volley_amp_xy
                    color = uistate.settings['rgb_volley_amp']

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
            zones = {}
            if uistate.checkBox['EPSP_amp']:
                zones['EPSP amp move'] = uistate.EPSP_amp_move_zone
            if uistate.checkBox['EPSP_slope']:
                zones['EPSP slope resize'] = uistate.EPSP_slope_resize_zone
                zones['EPSP slope move'] = uistate.EPSP_slope_move_zone
            if uistate.checkBox['volley_amp']:
                zones['volley amp move'] = uistate.volley_amp_move_zone
            if uistate.checkBox['volley_slope']:
                zones['volley slope resize'] = uistate.volley_slope_resize_zone
                zones['volley slope move'] = uistate.volley_slope_move_zone
            uistate.mouseover_action = None
            for action, zone in zones.items():
                if zone['x'][0] <= x <= zone['x'][1] and zone['y'][0] <= y <= zone['y'][1]:
                    uistate.mouseover_action = action
                    plotMouseover(action, axe)
                    
                    # Debugging block
                    if False:
                        p_row = uistate.dfp_row_copy
                        rec_name = p_row['recording_name']
                        rec_ID = p_row['ID']
                        t_row = uistate.dft_copy.loc[uistate.stim_select[0]]
                        stim_num = t_row['stim']
                        #new_dict = {key: value for key, value in uistate.dict_rec_labels.items() if value.get('stim') == stim_num and value.get('rec_ID') == rec_ID and value.get('axis') == 'ax2'}
                        #EPSP_slope = new_dict.get(f"{rec_name} - stim {stim_num} EPSP slope")
                        EPSP_slope = uistate.dict_rec_labels.get(f"{rec_name} - stim {stim_num} EPSP slope")
                        line = EPSP_slope.get('line')
                        line.set_linewidth(10)
                        print(f"{EPSP_slope} - {action}")
                        
                    break

            if uistate.mouseover_action is None:
                if uistate.mouseover_blob is not None:
                    uistate.mouseover_blob.set_sizes([0])
                if uistate.mouseover_plot is not None:
                    uistate.mouseover_plot[0].set_linewidth(0)

            axe.figure.canvas.draw()