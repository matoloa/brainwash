import seaborn as sns
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt # for the scatterplot
from matplotlib import style
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.ticker import FixedLocator

from matplotlib.lines import Line2D # for custom legend; TODO: still used?

import time # counting time for functions




class UIplot():
    def __init__(self, uistate):
        self.uistate = uistate
        print(f"UIplot instantiated: {self.uistate.anyView()}")


    def heatmap(self, df):
        ax1 = self.uistate.ax1
        ax2 = self.uistate.ax2

        if not hasattr(self.uistate, "dict_heatmap"):
            self.uistate.dict_heatmap = {}

        sweeps = df["sweep"].values
        pcols = [c for c in df.columns if c.startswith("p_")]

        for col in pcols:
            ps = df[col].values
            sig = ps < 0.05
            xs = sweeps[sig]

            if "amp" in col:
                ax = ax1
            elif "slope" in col:
                ax = ax2
            else:
                continue

            for x in xs:
                sc = ax.scatter([x], [0], marker="o", color="red")
                self.uistate.dict_heatmap.setdefault(col, {})[x] = sc

        ax1.figure.canvas.draw()
        ax2.figure.canvas.draw()


    def heatunmap(self):
        d = getattr(self.uistate, "dict_heatmap", None)
        if d is None:
            return
        ax = self.uistate.ax1
        #print(f"heatunmap: {d}")
        for col in list(d.keys()):
            for x, sc in list(d[col].items()):
                try:
                    sc.remove()
                except:
                    pass
            d[col].clear()

        d.clear()
        ax.figure.canvas.draw()


    def create_barplot(self, dict_group_color_ratio_SEM, str_aspect, output_path):
        plt.figure(figsize=(6, 6))
        group_names = []
        ratios = []
        SEMs = []
        colors = []
        
        # Extract information from the dictionary
        for group, (color, ratio, group_SEM) in dict_group_color_ratio_SEM.items():
            group_names.append(group)
            ratios.append(ratio)
            SEMs.append(group_SEM)
            colors.append(color)
        
        # Increase the font size for all text in the plot
        plt.rcParams.update({'font.size': 14})  # Adjust the size as needed
        
        # Create the bar plot with narrower bars
        bars = plt.bar(group_names, ratios, color=colors, width=0.4)  # Adjust the width for narrower bars
        
        # Add error bars (SEM) to each bar
        x_positions = np.arange(len(group_names))  # Get the x positions of the bars
        plt.errorbar(x_positions, ratios, yerr=SEMs, fmt='none', capsize=5, color='black')
        
        # Add a dashed line at 1
        plt.axhline(y=100, color='black', linestyle='--')
        
        # Set labels and title with increased font size
        #plt.xlabel('Group', fontsize=16)
        plt.ylabel(f"{str_aspect}, % of stim 1", fontsize=16)
        plt.title('Paired Pulse Ratio (50ms)', fontsize=18)
        
        # Increase tick labels size
        plt.xticks(fontsize=14)
        plt.yticks(fontsize=14)
        
        plt.savefig(output_path)
        plt.close()
        print(f'Saved barplot to {output_path}')


    def create_scatterplot(self, dict_rec_legend_color_df, x_aspect, y_aspect, dd_r_lines, output_path):
        print(f"Creating scatter plot for {len(dict_rec_legend_color_df)} records")
        plt.figure(figsize=(8, 6))
        
        # Iterate over each record in dict_rec_legend_color_df
        for label, (legend, color, df) in dict_rec_legend_color_df.items():
            plt.scatter(df[x_aspect], df[y_aspect], label=legend, color=color)
            if label in dd_r_lines:
                x, y = dd_r_lines[label]['x'], dd_r_lines[label]['y']
                plt.plot(x, y, linestyle='--', linewidth=2, color=color)  # Use the same color for regression line
        
        plt.title(f"Scatter plot of {x_aspect} vs {y_aspect} with Regression Lines")
        plt.xlabel(x_aspect)
        plt.ylabel(y_aspect)
        
        # Remove duplicate legends
        handles, labels = plt.gca().get_legend_handles_labels()
        by_label = dict(zip(labels, handles))
        plt.legend(by_label.values(), by_label.keys())
        
        plt.grid(True)
        plt.savefig(output_path)
        plt.close()
        print(f'Saved scatter plot to {output_path}')


    def xDeselect(self, ax, reset=False):
        # clear previous axvlines and axvspans
        ax1, ax2 = self.uistate.ax1, self.uistate.ax2
        if ax == ax1 or ax == ax2:
            axlines = ax1.get_lines() + ax2.get_lines()
            axpatches = ax1.patches + ax2.patches
            if reset:
                self.uistate.x_select['output'] = set()
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
        if reset:
            self.clear_axe_mean()
        ax.figure.canvas.draw()


    def xSelect(self, canvas):
        # draws a selected range of x values on <canvas>
        if canvas == self.uistate.axm.figure.canvas:
            ax = self.uistate.axm
            self.xDeselect(ax)
            if self.uistate.x_select['mean_end'] is None:
                #print(f"Selected x: {self.uistate.x_select['mean_start']}")
                ax.axvline(x=self.uistate.x_select['mean_start'], color='blue', label='xSelect_x')
            else:
                start, end = self.uistate.x_select['mean_start'], self.uistate.x_select['mean_end']
                #print(f"Selected x_range: {start} - {end}")
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
                # If only the start is selected, draw a line at the start
                #print(f"Selected x: {self.uistate.x_select['output_start']}")
                ax.axvline(x=self.uistate.x_select['output_start'], color='blue', label='xSelect_x')
            else:
                # If both start and end are selected, draw the range
                start, end = self.uistate.x_select['output_start'], self.uistate.x_select['output_end']
                #print(f"Selected x_range: {start} - {end}")
                ax.axvline(x=start, color='blue', label='xSelect_start')
                ax.axvline(x=end, color='blue', label='xSelect_end')
                ax.axvspan(start, end, color='blue', alpha=0.1, label='xSelect_span')
            # draw the mean of selected sweeps on axm
        canvas.draw()

    def clear_axe_mean(self):
        # if uistate.dict_rec_labels exists and contains keys that start with "axe mean selected sweeps", remove their lines and del the items
        if self.uistate.dict_rec_labels:
            for key in [k for k in self.uistate.dict_rec_labels if k.startswith('axe mean selected sweeps')]:
                self.uistate.dict_rec_labels[key]['line'].remove()
                del self.uistate.dict_rec_labels[key]
        else:
            print(" - - - - No dict_rec_labels to clear mean sweeps from")


    def update_axe_mean(self):
        '''
        updates the mean of selected sweeps drawn on axe, called by ui.py after:
        * releasing drag on output, selecting sweeps
        * clicking odd/even buttons
        * TODO: writing sweep range in text boxes
        '''
        self.clear_axe_mean()
        # if exactly one RECORDING is selected, plot the mean of selected SWEEPS one axe, if any
        if self.uistate.x_select['output'] and len(self.uistate.list_idx_select_recs) == 1:
            #print(f" - selected sweep(s): {self.uistate.x_select['output']}")
            # build mean of selected sweeps
            idx_rec = self.uistate.list_idx_select_recs[0]
            rec_ID = self.uistate.df_recs2plot.loc[idx_rec, 'ID']
            selected = self.uistate.x_select['output']
            df = self.uistate.df_rec_select_data
            col = self.uistate.settings.get('filter') or 'voltage'
            df_sweeps = df[df['sweep'].isin(selected)]
            df_mean = (df_sweeps.groupby('time', as_index=False)[col].mean())
            # calculate offset for t_stim
            df_t = self.uistate.df_rec_select_time
            n_stims = len(df_t)
            dict_gradient = self.get_dict_gradient(n_stims)
            alpha = self.uistate.settings['alpha_line']/2 # make mean-of-selected-lines more transparent
            for i_stim, t_row in df_t.iterrows():
                color = dict_gradient[i_stim]
                stim_num = i_stim + 1 # 1-numbering (visible to user)
                stim_str = f"- stim {stim_num}"
                t_stim = t_row['t_stim']
                # add to Events
                window_start = t_stim + self.uistate.settings['event_start']
                window_end = t_stim + self.uistate.settings['event_end']
                df_event = df_mean[(df_mean['time'] >= window_start) & (df_mean['time'] <= window_end)].copy()
                df_event['time'] = df_event['time'] - t_stim  # shift event so that t_stim is at time 0
                self.plot_line(f"axe mean selected sweeps {stim_str}", 'axe', df_event['time'], df_event[col], color, rec_ID, stim=stim_num, alpha=alpha)
                self.uistate.dict_rec_labels[f"axe mean selected sweeps {stim_str}"]['line'].set_visible(True)
        self.uistate.axe.figure.canvas.draw()


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
            if ax is not None:
                lines = ax.get_lines()
                if len(lines) > 0:
                    for line in lines:
                        line.set_visible(False)
                patches = ax.patches
                if len(patches) > 0:
                    for patch in patches:
                        patch.remove()
                legend = ax.get_legend()
                if legend is not None:
                    legend.remove()
        print("All lines hidden")


    def unPlot(self, rec_ID=None):
        dict_rec = self.uistate.dict_rec_labels
        dict_show = self.uistate.dict_rec_show
        if rec_ID is None:
            keys_to_remove = list(dict_rec.keys())
        else:
            keys_to_remove = [key for key, value in dict_rec.items() if rec_ID == value['rec_ID']]
        for key in keys_to_remove:
            dict_rec[key]['line'].remove()
            del dict_rec[key]
            if key in dict_show:
                del dict_show[key]


    def exterminate(self):
        # cycles through every line, on every graph, and kills it.
        uis = self.uistate
        axes = [uis.axm, uis.axe, uis.ax1, uis.ax2,]
        for axis in axes:
            if axis is None:
                continue
            for line in list(axis.lines):
                line.remove()
            for coll in list(axis.collections):
                coll.remove()
            axis.figure.canvas.draw()
        # clean up references
        uis.dict_rec_labels = {}
        uis.dict_rec_show = {}
        uis.dict_group_labels = {}
        uis.dict_group_show = {}
        uis.mouseover_plot = None
        uis.mouseover_blob = None
        uis.mouseover_out = None
        uis.mouseover_action = None
        uis.ghost_sweep = None
        uis.ghost_label = None


    def unPlotGroup(self, group_ID=None):
        dict_group = self.uistate.dict_group_labels
        if group_ID is None:
            keys_to_remove = list(dict_group.keys())  # Remove all if group_ID is None
        else:
            keys_to_remove = [key for key, value in dict_group.items() if group_ID == value['group_ID']]
        for key in keys_to_remove:
            dict_group[key]['fill'].remove()
            dict_group[key]['line'].remove()
            del dict_group[key]


    def graphRefresh(self, dd_groups):
        # show only selected and imported lines, only appropriate aspects
        print("graphRefresh")
        uistate = self.uistate
        if uistate.axm is None:
            print("No axes to refresh")
            return
        t0 = time.time()

        # Set recordings and group legends
        dd_recs = uistate.dict_rec_show
        dd_groups = uistate.dict_group_show
        axids = ['axm', 'axe', 'ax1', 'ax2']
        legend_loc = ['upper right', 'upper right', 'upper right', 'lower right']
        for axid, loc in zip(axids, legend_loc):
            recs_on_axis = {key: value for key, value in dd_recs.items() if value['axis'] == axid and not key.endswith(" marker")}
            axis_legend = {key: value['line'] for key, value in recs_on_axis.items()}
            if axid in ['ax1', 'ax2']:
                groups_on_axis = {key: value for key, value in dd_groups.items() if value['axis'] == axid}
                axis_legend.update({key: value['line'] for key, value in groups_on_axis.items()})
            axis = getattr(uistate, axid)
            axis.legend(axis_legend.values(), axis_legend.keys(), loc=loc)              

        # arrange axes and labels
        axm, axe, ax1, ax2 = self.uistate.axm, self.uistate.axe, self.uistate.ax1, self.uistate.ax2

        axm.axis('off')
        #axm.set_xlim(uistate.zoom['mean_xlim'])
        #axm.set_ylim(uistate.zoom['mean_ylim'])
        #axm.set_xlabel("Time (s)")
        #axe.set_ylabel("Voltage (V)")

        axe.set_xlabel("Time (s)")
        axe.set_ylabel("Voltage (V)")
        axe.set_xlim(uistate.zoom['event_xlim'])
        axe.set_ylim(uistate.zoom['event_ylim'])

        # Convert y-axis from V → mV
        axe.set_ylabel("Voltage (mV)")
        axe.set_yticks(axe.get_yticks())  # keeps same positions
        axe.set_yticklabels([f"{y*1e3:.1f}" for y in axe.get_yticks()])

        # Convert x-axis from s → ms
        axe.set_xlabel("Time (ms)")
        axe.set_xticks(axe.get_xticks())
        axe.set_xticklabels([f"{x*1e3:.1f}" for x in axe.get_xticks()])


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
        if uistate.checkBox['output_per_stim']:
            x_axis = 'stim'
            if uistate.rec_select:
                x_max = int(uistate.df_recs2plot['stims'].max())
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

        # 0-hline for Events
        if not 'Events y zero marker' in self.uistate.dict_rec_labels:
            hline0 = self.uistate.axe.axhline(0, linestyle='dotted', alpha=0.3)
            self.uistate.dict_rec_labels['Events y zero marker'] = {'rec_ID':None, 'stim': None, 'line':hline0, 'axis':'axe'}
        uistate.dict_rec_labels['Events y zero marker']['line'].set_visible(True)

        # 100-hline for relative Output
        if uistate.checkBox['norm_EPSP']:
            if not 'Output y 100% marker' in self.uistate.dict_rec_labels:
                hline100ax1 = self.uistate.ax1.axhline(100, linestyle='dotted', alpha=0.3, color = uistate.settings['rgb_EPSP_amp'])
                hline100ax2 = self.uistate.ax2.axhline(100, linestyle='dotted', alpha=0.3, color = uistate.settings['rgb_EPSP_slope'])
                self.uistate.dict_rec_labels['output amp 100% marker'] = {'rec_ID':None, 'stim': None, 'line':hline100ax1, 'axis':'ax1'}
                self.uistate.dict_rec_labels['output slope 100% marker'] = {'rec_ID':None, 'stim': None, 'line':hline100ax2, 'axis':'ax2'}
            uistate.dict_rec_labels['output amp 100% marker']['line'].set_visible(uistate.ampView())
            uistate.dict_rec_labels['output slope 100% marker']['line'].set_visible(uistate.slopeView())

        # update mean of selected sweeps on axe
        self.update_axe_mean()

        # redraw
        axm.figure.canvas.draw()
        axe.figure.canvas.draw()
        ax1.figure.canvas.draw() # ax2 should be on the same canvas
        print(f" - - {round((time.time() - t0) * 1000)} ms")


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
        colors = [(1, 0.3, 0), "green", (0, 0.3, 1)]  # RGB for a redder orange and a tealer blue
        cmap = LinearSegmentedColormap.from_list("", colors)
        return {i: cmap(i/n_stims) for i in range(n_stims)}

    def plot_line(self, label, axid, x, y, color, rec_ID, aspect=None, stim=None, width=1, alpha=None):
        zorder = 0 if width > 1 else 1
        alpha = alpha if alpha is not None else self.uistate.settings['alpha_line']
        line, = self.get_axis(axid).plot(x, y, color=color, label=label, alpha=alpha, linewidth=width, zorder=zorder)
        line.set_visible(False)
        self.uistate.dict_rec_labels[label] = {'rec_ID':rec_ID, 'aspect':aspect, 'stim': stim, 'line':line, 'axis':axid}

    def plot_marker(self, label, axid, x, y, color, rec_ID, aspect=None, stim=None):
        marker, = self.get_axis(axid).plot(x, y, marker='o', markerfacecolor=color, markeredgecolor=color, markersize=10, alpha=0.4, zorder=0, label=label)
        marker.set_visible(False)
        self.uistate.dict_rec_labels[label] = {'rec_ID':rec_ID, 'aspect':aspect, 'stim': stim, 'line':marker, 'axis':axid}

    def plot_cross(self, label, axid, x, amp_x, amp_y, color, rec_ID, aspect=None, stim=None):
        xline, = self.get_axis(axid).plot(amp_x, [amp_y[1], amp_y[1]], color=color, label=f"{label} x", alpha=self.uistate.settings['alpha_line'], zorder=0)
        yline, = self.get_axis(axid).plot([x,x], amp_y, color=color, label=f"{label} y", alpha=self.uistate.settings['alpha_line'], zorder=0)
        xline.set_visible(False)
        yline.set_visible(False)
        self.uistate.dict_rec_labels[f"{label} x marker"] = {'rec_ID':rec_ID, 'aspect':aspect, 'stim': stim, 'line':xline, 'axis':axid}
        self.uistate.dict_rec_labels[f"{label} y marker"] = {'rec_ID':rec_ID, 'aspect':aspect, 'stim': stim, 'line':yline, 'axis':axid}

    def plot_vline(self, label, axid, x, color, rec_ID, aspect=None, stim=None, linewidth=8):
        vline = self.get_axis(axid).axvline(x=x, color=color, alpha=self.uistate.settings['alpha_mark'], label=label, linewidth=linewidth, zorder=0)
        vline.set_visible(False)
        self.uistate.dict_rec_labels[label] = {'rec_ID':rec_ID, 'aspect':aspect, 'stim': stim, 'line':vline, 'axis':axid}

    def plot_hline(self, label, axid, y, color, rec_ID, aspect=None, stim=None, linewidth=1):
        hline = self.get_axis(axid).axhline(y=y, color=color, alpha=self.uistate.settings['alpha_mark'], label=label, linewidth=linewidth, zorder=0)
        hline.set_visible(False)
        self.uistate.dict_rec_labels[label] = {'rec_ID':rec_ID, 'aspect':aspect, 'stim': stim, 'line':hline, 'axis':axid}

    def plot_group_lines(self, axid, group_ID, dict_group, df_groupmean):
        group_name = dict_group['group_name']
        color = dict_group['color']
        axis = self.get_axis(axid)
        if axid == 'ax1':
            aspect = 'EPSP_amp'
            str_aspect = 'EPSP amp'
        else:
            aspect = 'EPSP_slope'
            str_aspect = 'EPSP slope'
        if self.uistate.checkBox['output_per_stim']:
            x = df_groupmean.stim
        else:
            x = df_groupmean.sweep
        label_mean = f"{group_name} {str_aspect} mean"
        label_norm = f"{group_name} {str_aspect} norm"
        y_mean = df_groupmean[f"{aspect}_mean"].fillna(0)
        y_mean_SEM = df_groupmean[f"{aspect}_SEM"].fillna(0)
        y_norm = df_groupmean[f"{aspect}_norm_mean"].fillna(0)
        y_norm_SEM = df_groupmean[f"{aspect}_norm_SEM"].fillna(0)

        print(f"y_mean: {y_mean}")
        print(f"y_mean_SEM: {y_mean_SEM}")
        print(f"y_mean - y_mean_SEM: {y_mean - y_mean_SEM}")
        print(f"y_mean + y_mean_SEM: {y_mean + y_mean_SEM}")

        meanline, = axis.plot(x, y_mean, color=color, label=label_mean, alpha=self.uistate.settings['alpha_line'], zorder=0)
        normline, = axis.plot(x, y_norm, color=color, label=label_norm, alpha=self.uistate.settings['alpha_line'], zorder=0)
        meanfill  = axis.fill_between(x, y_mean - y_mean_SEM, y_mean + y_mean_SEM, alpha=0.3, color=color)
        normfill  = axis.fill_between(x, y_norm - y_norm_SEM, y_norm + y_norm_SEM, alpha=0.3, color=color)
        meanline.set_visible(False)
        normline.set_visible(False)
        meanfill.set_visible(False)
        normfill.set_visible(False)
        self.uistate.dict_group_labels[label_mean] = {'group_ID':group_ID, 'stim':None, 'aspect':aspect, 'axis':axid, 'line':meanline, 'fill':meanfill}
        self.uistate.dict_group_labels[label_norm] = {'group_ID':group_ID, 'stim':None, 'aspect':aspect, 'axis':axid, 'line':normline, 'fill':normfill}


    def addRow(self, p_row, dft, dfmean, dfoutput):
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

        settings = self.uistate.settings # Event window, color, and alpha settings
        variables = ['t_EPSP_amp', 't_EPSP_slope_start', 't_EPSP_slope_end', 't_volley_amp', 't_volley_slope_start', 't_volley_slope_end']

        # Process detected stims
        for i_stim, t_row in dft.iterrows():
            color = dict_gradient[i_stim]
            stim_num = i_stim + 1 # 1-numbering (visible to user)
            stim_str = f"- stim {stim_num}"
            t_stim = t_row['t_stim']
            amp_zero = t_row['amp_zero']
            out = dfoutput[dfoutput['stim'] == stim_num]# TODO: enable switch to dfdiff?
            y_position = dfmean.loc[dfmean.time == t_stim, rec_filter].values[0] # returns index, y_value
            for var in variables: # Convert all variables except t_stim to stim-specific time
               t_row[var] -= t_stim

            # add markers to Mean
            self.plot_marker(f"mean {label} {stim_str} marker", 'axm', t_stim, 0, color, rec_ID)
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
                self.plot_marker(f"{label} {stim_str} EPSP amp marker", 'axe', x_position, y_position, settings['rgb_EPSP_amp'], rec_ID, aspect='EPSP_amp', stim=stim_num)
                amp_x = x_position - t_row['t_EPSP_amp_halfwidth'], x_position + t_row['t_EPSP_amp_halfwidth']
                amp_y = amp_zero, amp_zero - (out['EPSP_amp'].mean() / 1000) # mV to V
                self.plot_cross(f"{label} {stim_str} EPSP amp", 'axe', x_position, amp_x, amp_y, settings['rgb_EPSP_amp'], rec_ID, aspect='EPSP_amp', stim=stim_num)
                if x_axis == 'sweep':
                    self.plot_line(f"{label} {stim_str} EPSP amp", 'ax1', out[x_axis], out['EPSP_amp'], settings['rgb_EPSP_amp'], rec_ID, aspect='EPSP_amp', stim=stim_num)
                    self.plot_line(f"{label} {stim_str} EPSP amp norm", 'ax1', out[x_axis], out['EPSP_amp_norm'], settings['rgb_EPSP_amp'], rec_ID, aspect='EPSP_amp', stim=stim_num)
                self.plot_line(f"{label} {stim_str} amp_zero marker", 'axe', [-0.002, -0.001], [amp_zero, amp_zero], settings['rgb_EPSP_amp'], rec_ID, aspect='EPSP_amp', stim=stim_num) # TODO: hardcoded x

            x_start, x_end = t_row['t_EPSP_slope_start'], t_row['t_EPSP_slope_end']
            if not (np.isnan(x_start) or np.isnan(x_end)):
                index = (df_event['time'] - x_start).abs().idxmin()
                y_start = df_event.loc[index, rec_filter] if index in df_event.index else None
                index = (df_event['time'] - x_end).abs().idxmin()
                y_end = df_event.loc[index, rec_filter] if index in df_event.index else None
                self.plot_line(f"{label} {stim_str} EPSP slope marker", 'axe', [x_start, x_end], [y_start, y_end], settings['rgb_EPSP_slope'], rec_ID, aspect='EPSP_slope', stim=stim_num, width=5)
                if x_axis == 'sweep':
                    self.plot_line(f"{label} {stim_str} EPSP slope", 'ax2', out[x_axis], out['EPSP_slope'], settings['rgb_EPSP_slope'], rec_ID, aspect='EPSP_slope', stim=stim_num)
                    self.plot_line(f"{label} {stim_str} EPSP slope norm", 'ax2', out[x_axis], out['EPSP_slope_norm'], settings['rgb_EPSP_slope'], rec_ID, aspect='EPSP_slope', stim=stim_num)

            if not np.isnan(t_row['t_volley_amp']):
                x_position = t_row['t_volley_amp']
                y_position = df_event.loc[df_event.time == t_row['t_volley_amp'], rec_filter]
                color = settings['rgb_volley_amp']
                self.plot_marker(f"{label} {stim_str} volley amp marker", 'axe', t_row['t_volley_amp'], y_position, settings['rgb_volley_amp'], rec_ID, aspect='volley_amp', stim=stim_num)
                volley_amp_mean = t_row.get('volley_amp_mean')
                if volley_amp_mean is None:
                    volley_amp_mean = out['volley_amp'].mean()
                amp_x = x_position - t_row['t_volley_amp_halfwidth'], x_position + t_row['t_volley_amp_halfwidth']
                amp_y = amp_zero, amp_zero - volley_amp_mean / 1000 # mV to V
                self.plot_cross(f"{label} {stim_str} volley amp", 'axe', x_position, amp_x, amp_y, color, rec_ID, aspect='volley_amp', stim=stim_num)
                volley_amp_mean = t_row.get('volley_amp_mean')
                if volley_amp_mean is None:
                    volley_amp_mean = out['volley_amp'].mean()
                self.plot_hline(f"{label} {stim_str} volley amp mean", 'ax1', volley_amp_mean, settings['rgb_volley_amp'], rec_ID, aspect='volley_amp_mean', stim=stim_num)
                self.plot_line(f"{label} {stim_str} volley amp", 'ax1', out[x_axis], out['volley_amp'], settings['rgb_volley_amp'], rec_ID, aspect='volley_amp', stim=stim_num)

            x_start, x_end = t_row['t_volley_slope_start'], t_row['t_volley_slope_end']
            if not (np.isnan(x_start) or np.isnan(x_end)):
                index = (df_event['time'] - x_start).abs().idxmin()
                y_start = df_event.loc[index, rec_filter] if index in df_event.index else None
                index = (df_event['time'] - x_end).abs().idxmin()
                y_end = df_event.loc[index, rec_filter] if index in df_event.index else None
                self.plot_line(f"{label} {stim_str} volley slope marker", 'axe', [x_start, x_end], [y_start, y_end], settings['rgb_volley_slope'], rec_ID, aspect='volley_slope', stim=stim_num, width=5)
                volley_slope_mean = t_row.get('volley_slope_mean')
                if volley_slope_mean is None:
                    volley_slope_mean = out['volley_slope'].mean()
                self.plot_hline(f"{label} {stim_str} volley slope mean", 'ax2', volley_slope_mean, settings['rgb_volley_slope'], rec_ID, aspect='volley_slope_mean', stim=stim_num)
                self.plot_line(f"{label} {stim_str} volley slope", 'ax2', out[x_axis], out['volley_slope'], settings['rgb_volley_slope'], rec_ID, aspect='volley_slope', stim=stim_num)

        if x_axis == 'stim': # add stim-lines to output
            out = dfoutput
            self.plot_line(f"{label} EPSP amp", 'ax1', out[x_axis], out['EPSP_amp'], settings['rgb_EPSP_amp'], rec_ID, aspect='EPSP_amp')
            self.plot_line(f"{label} EPSP amp norm", 'ax1', out[x_axis], out['EPSP_amp_norm'], settings['rgb_EPSP_amp'], rec_ID, aspect='EPSP_amp')
            self.plot_line(f"{label} EPSP slope", 'ax2', out[x_axis], out['EPSP_slope'], settings['rgb_EPSP_slope'], rec_ID, aspect='EPSP_slope')
            self.plot_line(f"{label} EPSP slope norm", 'ax2', out[x_axis], out['EPSP_slope_norm'], settings['rgb_EPSP_slope'], rec_ID, aspect='EPSP_slope')
            self.plot_line(f"{label} volley amp", 'ax1', out[x_axis], out['volley_amp'], settings['rgb_volley_amp'], rec_ID, aspect='volley_amp')
            self.plot_line(f"{label} volley slope", 'ax2', out[x_axis], out['volley_slope'], settings['rgb_volley_slope'], rec_ID, aspect='volley_slope')


    def addGroup(self, group_ID, dict_group, df_groupmean):
        # plot group meanlines and SEMs
        if df_groupmean['EPSP_amp_mean'].notna().any():
            self.plot_group_lines('ax1', group_ID, dict_group, df_groupmean)
        if df_groupmean['EPSP_slope_mean'].notna().any():
            self.plot_group_lines('ax2', group_ID, dict_group, df_groupmean)


    def update(self, prow, trow, aspect, data_x, data_y, amp=None):
        """
        Updates the existing plotted artists stored in `self.uistate.dict_rec_labels`.
        Parameters
        - prow (pandas.Series): df_project row for selected recording.
        - trow (pandas.Series): dft (timepoint) row for selected stim.
        - aspect (str): One of 'EPSP slope', 'volley slope', 'EPSP amp', 'volley amp'.
            Controls which markers/lines are updated.
        - data_x (np.ndarray-like): x-values (time or shifted time) corresponding to
            the event window or mean trace used to sample y-values for marker placement.
        - data_y (np.ndarray-like): y-values aligned with `data_x` (voltage trace).
        - amp (float, optional): amplitude value used for drawing amplitude markers
        """

        # Validate input formats
        if not isinstance(prow, pd.Series):
            raise TypeError(f"prow must be pandas.Series, got {type(prow).__name__}")
        if not isinstance(trow, (pd.Series, dict)):
            raise TypeError(f"trow must be pandas.Series or dict, got {type(trow).__name__}")
        if isinstance(trow, dict) and not trow:
            raise ValueError("trow dict is empty")
       
        valid_aspects = ['EPSP slope', 'volley slope', 'EPSP amp', 'volley amp']
        if aspect not in valid_aspects:
            raise ValueError(f"aspect must be one of {valid_aspects}, got '{aspect}'")
        if not isinstance(data_x, np.ndarray):
            try:
                data_x = np.asarray(data_x)
            except (TypeError, ValueError):
                raise TypeError(f"data_x must be array-like, got {type(data_x).__name__}")
        if not isinstance(data_y, np.ndarray):
            try:
                data_y = np.asarray(data_y)
            except (TypeError, ValueError):
                raise TypeError(f"data_y must be array-like, got {type(data_y).__name__}")
        
        if len(data_x) != len(data_y):
            raise ValueError(f"data_x and data_y must have same length, got {len(data_x)} and {len(data_y)}")

        if amp is not None and not isinstance(amp, (int, float, np.number)):
            raise TypeError(f"amp must be numeric or None, got {type(amp).__name__}")
        
        # Validate required keys in trow
        required_keys = ['t_stim', 'stim', 'amp_zero']
        for key in required_keys:
            if key not in trow:
                raise KeyError(f"trow missing required key: '{key}'")

        # TODO: unspaghetti this mess
        norm = self.uistate.checkBox['norm_EPSP']
        stim_offset = trow['t_stim']
        label_core = f"{prow['recording_name']} - stim {trow['stim']} {aspect}"

        if aspect in ['EPSP slope', 'volley slope']:
            x_start = trow[f't_{aspect.replace(" ", "_")}_start']-stim_offset
            x_end = trow[f't_{aspect.replace(" ", "_")}_end']-stim_offset
            y_start = data_y[np.abs(data_x - x_start).argmin()]
            y_end = data_y[np.abs(data_x - x_end).argmin()]
            self.updateLine(f"{label_core} marker", [x_start, x_end], [y_start, y_end])
            if self.uistate.checkBox['output_per_stim']:
                label_core = f"{prow['recording_name']} {aspect}"
            if aspect == 'volley slope':
                if self.uistate.checkBox['output_per_stim']:
                    self.updateOutLine(label_core)
                else:
                    volley_slope_mean = trow.get('volley_slope_mean')
                    print(f" - - - volley_slope_mean: {volley_slope_mean}")
                    #if volley_slope_mean is None:
                    #    volley_slope_mean = self.uistate.mouseover_out[0].get_ydata().mean()
                    self.updateOutMean(f"{label_core} mean", volley_slope_mean)
            else: # EPSP slope
                if norm:
                    label_core += " norm"
                self.updateOutLine(label_core)
        elif aspect in ['EPSP amp', 'volley amp']:
            key = aspect.replace(" ", "_")
            t_amp = trow[f't_{key}'] - stim_offset
            y_position = data_y[np.abs(data_x - t_amp).argmin()]
            amp_x = t_amp - trow[f't_{key}_halfwidth'], t_amp + trow[f't_{key}_halfwidth']
            self.updateAmpMarker(label_core, t_amp, y_position, amp_x, trow['amp_zero'], amp=amp)
            if self.uistate.checkBox['output_per_stim']:
                label_core = f"{prow['recording_name']} {aspect}"
            if aspect == 'volley amp':
                if self.uistate.checkBox['output_per_stim']:
                    self.updateOutLine(label_core)
                else:
                    volley_amp_mean = trow.get('volley_amp_mean')
                    print(f" - - - volley_amp_mean: {volley_amp_mean}")
                    #if volley_amp_mean is None:
                    #    volley_amp_mean = self.uistate.mouseover_out[0].get_ydata().mean()
                    self.updateOutLine(label_core)
                    self.updateOutMean(f"{label_core} mean", volley_amp_mean)
            else: # EPSP amp
                if norm:
                    label_core += " norm"
                self.updateOutLine(label_core)

    def updateAmpMarker(self, labelbase, x, y, amp_x, amp_zero, amp=None):
        axe = self.uistate.axe
        print(f"updateAmpMarker called with labelbase: {labelbase}, x: {x}, y: {y}, amp_x: {amp_x}, amp_zero: {amp_zero}, amp: {amp}")
        x = np.atleast_1d(x)
        y = np.atleast_1d(y)
        print(f"updateAmpMarker: {labelbase}, x: {x}, y: {y}, amp_x: {amp_x}, amp_zero: {amp_zero}, amp: {amp}")
        self.uistate.dict_rec_labels[f"{labelbase} marker"]['line'].set_data(x, y)
        if amp is not None:
            amp_y = amp_zero, (0 - amp) + amp_zero
            self.uistate.dict_rec_labels[f"{labelbase} x marker"]['line'].set_data(amp_x, [amp_y[1],amp_y[1]])
            self.uistate.dict_rec_labels[f"{labelbase} y marker"]['line'].set_data([x,x], amp_y)
        axe.figure.canvas.draw()

    def updateLine(self, plot_to_update, x_data, y_data):
        axe = self.uistate.axe
        dict_line = self.uistate.dict_rec_labels[plot_to_update]
        dict_line['line'].set_data(x_data, y_data)
        axe.figure.canvas.draw()

    def updateOutLine(self, label):
        print(f"updateOutLine: {label}")
        mouseover_out = self.uistate.mouseover_out
        linedict = self.uistate.dict_rec_labels[label]
        linedict['line'].set_xdata(mouseover_out[0].get_xdata())
        linedict['line'].set_ydata(mouseover_out[0].get_ydata())

    def updateOutMean(self, label, mean):
        print(f"updateOutMean: {label}, {mean}")
        mouseover_out = self.uistate.mouseover_out
        linedict = self.uistate.dict_rec_labels[label]
        linedict['line'].set_xdata(mouseover_out[0].get_xdata())
        linedict['line'].set_ydata([mean] * len(linedict['line'].get_xdata()))
        # linedict['line'].set_ydata(mean)



#####################################################################
#     #DEPRECATED FUNCTIONS - TO BE REMOVED IN FUTURE RELEASES      #
#####################################################################

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