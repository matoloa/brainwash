import seaborn as sns
import numpy as np
import pandas as pd
from matplotlib import style
from matplotlib.lines import Line2D
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.ticker import FixedLocator


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
        #axm.axis('off')
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
#        ax1.set_xlim(uistate.zoom['output_xlim'])
#        ax2.set_xlim(uistate.zoom['output_xlim'])
        if uistate.checkBox['output_per_stim']:
            x_axis = 'stim'
            if uistate.rec_select:
                x_max = uistate.df_recs2plot['stims'].max()
                ax1.xaxis.set_major_locator(FixedLocator(range(1, x_max+1)))
                ax2.xaxis.set_major_locator(FixedLocator(range(1, x_max+1)))
        else:
            x_axis = 'sweep'
        ax1.set_xlabel(x_axis)
        ax2.set_xlabel(x_axis)
        print(f"output_xlim: {uistate.zoom['output_xlim']}")
        ax1.figure.subplots_adjust(bottom=0.2)
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

    def get_axis(self, axisname): # returns the axis object by name (using only object references failed in some cases)
        axis_dict = {
            "axm": self.uistate.axm,
            "axe": self.uistate.axe,
            "ax1": self.uistate.ax1,
            "ax2": self.uistate.ax2
        }
        return axis_dict.get(axisname, None)

    def get_dict_gradient(self, n_stims):
        colors = [(1, 0.3, 0), "green", "teal"]  # RGB for a redder orange
        cmap = LinearSegmentedColormap.from_list("", colors)
        return {i: cmap(i/n_stims) for i in range(n_stims)}

    def plot_line(self, label, axid, x, y, color, rec_ID, stim=None, width=1):
        zorder = 0 if width > 1 else 1
        line, = self.get_axis(axid).plot(x, y, color=color, label=label, alpha=self.uistate.settings['alpha_line'], linewidth=width, zorder=zorder)
        self.uistate.dict_rec_labels[label] = {'rec_ID':rec_ID, 'stim': stim, 'line':line, 'axis':axid}

    def plot_marker(self, label, axid, x, y, color, rec_ID, stim=None):
        marker, = self.get_axis(axid).plot(x, y, marker='o', markerfacecolor=color, markeredgecolor=color, markersize=10, alpha=self.uistate.settings['alpha_mark'], zorder=0, label=label)
        self.uistate.dict_rec_labels[label] = {'rec_ID':rec_ID, 'stim': stim, 'line':marker, 'axis':axid}

    def plot_vline(self, label, axid, x, color, rec_ID, stim=None):
        vline = self.get_axis(axid).axvline(x=x, color=color, linewidth=1, alpha=self.uistate.settings['alpha_dot'], label=label)
        self.uistate.dict_rec_labels[label] = {'rec_ID':rec_ID, 'stim': stim, 'line':vline, 'axis':axid}

    def addRow(self, p_row, dft, dfmean, dfoutput): # TODO: unspaghetti this
        rec_ID = p_row['ID']
        rec_name = p_row['recording_name']
        rec_filter = p_row['filter'] # the filter currently used for this recording
        n_stims = len(dft)
        if rec_filter != 'voltage':
            label = f"{rec_name} ({rec_filter})"
        else:
            label = rec_name

        # Add meanline to Mean
        self.plot_line(f"mean {label}", 'axm', dfmean["time"], dfmean[rec_filter], "black", rec_ID=rec_ID)

        x_axis = 'stim' if self.uistate.checkBox['output_per_stim'] else 'sweep'
        dict_gradient = self.get_dict_gradient(n_stims)
        # Process detected stims
        for i_stim, t_row in dft.iterrows():
            color = dict_gradient[i_stim]
            stim_num = i_stim + 1 # 1-numbering (visible to user)
            stim_str = f"- stim {stim_num}"
            t_stim = t_row['t_stim']
            out = dfoutput[dfoutput['stim'] == stim_num]# TODO: enable switch to dfdiff?
            y_position = dfmean.loc[dfmean.time == t_stim, rec_filter].values[0] # returns index, y_value
            # Event window, color, and alpha settings
            settings = self.uistate.settings
            # Convert all variables except t_stim to stim-specific time
            variables = ['t_EPSP_amp', 't_EPSP_slope_start', 't_EPSP_slope_end', 't_volley_amp', 't_volley_slope_start', 't_volley_slope_end']
            for var in variables:
               t_row[var] -= t_stim

            # add markers to Mean
            self.plot_marker(f"mean {label} {stim_str} marker", 'axm', t_stim, y_position, color, rec_ID)
            self.plot_vline(f"mean {label} {stim_str} selection marker", 'axm', t_stim, color, rec_ID, stim=stim_num)
            if x_axis == 'stim': # also add to output
                self.plot_marker(f"ax1 mean {label} {stim_str} marker", 'ax1', stim_num, y_position, color, rec_ID, stim=stim_num)
                self.plot_marker(f"ax2 mean {label} {stim_str} marker", 'ax2', stim_num, y_position, color, rec_ID, stim=stim_num)
                self.plot_vline(f"ax1 mean {label} {stim_str} selection marker", 'ax1', stim_num, color, rec_ID, stim=stim_num)
                self.plot_vline(f"ax2 mean {label} {stim_str} selection marker", 'ax2', stim_num, color, rec_ID, stim=stim_num)

            # add to Events
            window_start = t_stim + settings['event_start']
            window_end = t_stim + settings['event_end']
            df_event = dfmean[(dfmean['time'] >= window_start) & (dfmean['time'] <= window_end)].copy()
            df_event['time'] = df_event['time'] - t_stim  # shift event so that t_stim is at time 0
            self.plot_line(f"{label} {stim_str}", 'axe', df_event['time'], df_event[rec_filter], color, rec_ID, stim=stim_num)
            
            # plot markers on axe, output lines on ax1 and ax2
            out = dfoutput[dfoutput['stim'] == stim_num] # TODO: enable switch to dfdiff?

            if not np.isnan(t_row['t_EPSP_amp']):
                x_position = t_row['t_EPSP_amp']
                y_position = df_event.loc[df_event.time == x_position, rec_filter]
                color = settings['rgb_EPSP_amp']
                # TODO: temporary hotfix - salvage bad y_positions (prevent this from happening!)
                if isinstance(y_position, pd.Series):
                    if not y_position.empty and isinstance(y_position.values[0], float):
                        y_position = y_position.values[0]
                    else:
                        print(f"*** Failed to salvage bad y_position: {y_position} from {label} {stim_str} EPSP amp marker; setting to 0")
                        y_position, color = 0, 'red'
                self.plot_marker(f"{label} {stim_str} EPSP amp marker", 'axe', x_position, y_position, color, rec_ID, stim=stim_num)
                if x_axis == 'sweep':
                    self.plot_line(f"{label} {stim_str} EPSP amp", 'ax1', out[x_axis], out['EPSP_amp'], settings['rgb_EPSP_amp'], rec_ID, stim=stim_num)
                    if 'EPSP_amp_norm' in out.columns:
                        self.plot_line(f"{label} {stim_str} EPSP amp norm", 'ax1', out[x_axis], out['EPSP_amp_norm'], settings['rgb_EPSP_amp'], rec_ID, stim=stim_num)
            
            if not np.isnan(t_row['t_EPSP_slope_start']):
                x_start, x_end = t_row['t_EPSP_slope_start'], t_row['t_EPSP_slope_end']
                index = (df_event['time'] - x_start).abs().idxmin()
                y_start = df_event.loc[index, rec_filter] if index in df_event.index else None
                index = (df_event['time'] - x_end).abs().idxmin()
                y_end = df_event.loc[index, rec_filter] if index in df_event.index else None
                self.plot_line(f"{label} {stim_str} EPSP slope marker", 'axe', [x_start, x_end], [y_start, y_end], settings['rgb_EPSP_slope'], rec_ID, stim=stim_num, width=5)
                if x_axis == 'sweep':
                    self.plot_line(f"{label} {stim_str} EPSP slope", 'ax2', out[x_axis], out['EPSP_slope'], settings['rgb_EPSP_slope'], rec_ID, stim=stim_num)
                    if 'EPSP_slope_norm' in out.columns:
                        self.plot_line(f"{label} {stim_str} EPSP slope norm", 'ax2', out[x_axis], out['EPSP_slope_norm'], settings['rgb_EPSP_slope'], rec_ID, stim=stim_num)

            if not np.isnan(t_row['t_volley_amp']):
                y_position = df_event.loc[df_event.time == t_row['t_volley_amp'], rec_filter]
                # TODO: temporary hotfix - salvage bad y_positions (prevent this from happening!)
                if isinstance(y_position, pd.Series):
                    if not y_position.empty and isinstance(y_position.values[0], float):
                        y_position = y_position.values[0]
                    else:
                        print(f"*** Failed to salvage bad y_position: {y_position} from {label} {stim_str} volley amp marker, setting to 0")
                        y_position, color = 0, 'red'
                self.plot_marker(f"{label} {stim_str} volley amp marker", 'axe', t_row['t_volley_amp'], y_position, settings['rgb_volley_amp'], rec_ID, stim=stim_num)
                if x_axis == 'sweep':
                    self.plot_line(f"{label} {stim_str} volley amp mean", 'ax1', out[x_axis], out['volley_amp'], settings['rgb_volley_amp'], rec_ID, stim=stim_num)
            
            if not np.isnan(t_row['t_volley_slope_start']):
                x_start, x_end = t_row['t_volley_slope_start'], t_row['t_volley_slope_end']
                index = (df_event['time'] - x_start).abs().idxmin()
                y_start = df_event.loc[index, rec_filter] if index in df_event.index else None
                index = (df_event['time'] - x_end).abs().idxmin()
                y_end = df_event.loc[index, rec_filter] if index in df_event.index else None
                self.plot_line(f"{label} {stim_str} volley slope marker", 'axe', [x_start, x_end], [y_start, y_end], settings['rgb_volley_slope'], rec_ID, stim=stim_num, width=5)
                if x_axis == 'sweep':
                    self.plot_line(f"{label} {stim_str} volley slope mean", 'ax2', out[x_axis], out['volley_slope'], settings['rgb_volley_slope'], rec_ID, stim=stim_num)

        # add stim-lines to output
        if x_axis == 'stim':
            out = dfoutput
            self.plot_line(f"{label} EPSP amp", 'ax1', out[x_axis], out['EPSP_amp'], settings['rgb_EPSP_amp'], rec_ID)
            if 'EPSP_amp_norm' in out.columns:
                self.plot_line(f"{label} EPSP amp norm", 'ax1', out[x_axis], out['EPSP_amp_norm'], settings['rgb_EPSP_amp'], rec_ID)
            self.plot_line(f"{label} EPSP slope", 'ax2', out[x_axis], out['EPSP_slope'], settings['rgb_EPSP_slope'], rec_ID)
            if 'EPSP_slope_norm' in out.columns:
                self.plot_line(f"{label} EPSP slope norm", 'ax2', out[x_axis], out['EPSP_slope_norm'], settings['rgb_EPSP_slope'], rec_ID)
            self.plot_line(f"{label} volley amp", 'ax1', out[x_axis], out['volley_amp'], settings['rgb_volley_amp'], rec_ID)
            self.plot_line(f"{label} volley slope", 'ax2', out[x_axis], out['volley_slope'], settings['rgb_volley_slope'], rec_ID)


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
        stim_offset = t_row['t_stim']
        label_base = f"{p_row['recording_name']} - stim {t_row['stim']} {aspect}"

        if aspect in ['EPSP slope', 'volley slope']:
            x_start = t_row[f't_{aspect.replace(" ", "_")}_start']-stim_offset
            x_end = t_row[f't_{aspect.replace(" ", "_")}_end']-stim_offset
            y_start = data_y[np.abs(data_x - x_start).argmin()]
            y_end = data_y[np.abs(data_x - x_end).argmin()]
            self.updateLine(f"{label_base} marker", [x_start, x_end], [y_start, y_end])
            if self.uistate.checkBox['output_per_stim']:
                label_base = f"{p_row['recording_name']} {aspect}"
            if aspect == 'volley slope':
                mean = t_row[f'{aspect.replace(" ", "_")}_mean']
                self.updateOutMean(f"{label_base} mean", mean)
            else: # EPSP slope
                if norm:
                    label_base += " norm"
                self.updateOutLine(label_base)
        elif aspect in ['EPSP amp', 'volley amp']:
            t_amp = t_row[f't_{aspect.replace(" ", "_")}'] - stim_offset
            y_position = data_y[np.abs(data_x - t_amp).argmin()]
            self.updateLine(f"{label_base} marker", t_amp, y_position)
            if self.uistate.checkBox['output_per_stim']:
                label_base = f"{p_row['recording_name']} {aspect}"
            if aspect == 'volley amp':
                if self.uistate.checkBox['output_per_stim']:
                    self.updateOutLine(f"{label_base}", t_amp, y_position)
                else:
                    mean = t_row[f'{aspect.replace(" ", "_")}_mean']
                    self.updateOutMean(f"{label_base} mean", mean)
            else: # EPSP amp
                if norm:
                    label_base += " norm"
                self.updateOutLine(label_base)


    def updateLine(self, plot_to_update, x_data, y_data):
        axe = self.uistate.axe
        linedict = self.uistate.dict_rec_labels[plot_to_update]
        print(f"updateLine: {plot_to_update}, linedict: {linedict}")
        linedict['line'].set_xdata(x_data)
        linedict['line'].set_ydata(y_data)
        axe.figure.canvas.draw()

    def updateOutLine(self, label):
        print(f"updateOutLine: {label}")
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