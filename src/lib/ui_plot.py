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
        print("All lines hidden")

    def graph(self, dict_row, dfmean, dfoutput, axm, ax1, ax2):
        uistate = self.uistate
        rec_name = dict_row['recording_name']
        rec_filter = dict_row['filter'] # the filter currently used for this recording
        t_EPSP_amp = dict_row['t_EPSP_amp']
        t_EPSP_slope = dict_row['t_EPSP_slope']
        t_EPSP_slope_size = dict_row['t_EPSP_slope_size']
        t_volley_amp = dict_row['t_volley_amp']
        volley_amp_mean = dict_row['volley_amp_mean']
        t_volley_slope = dict_row['t_volley_slope']
        t_volley_slope_size = dict_row['t_volley_slope_size']
        volley_slope_mean = dict_row['volley_slope_mean']

        # plot relevant filter of dfmean on main_canvas_mean
        if rec_filter != 'voltage':
            label = f"{rec_name} ({rec_filter})"
        else:
            label = rec_name
        # persist a custom-named lineplot

        _ = sns.lineplot(ax=axm, label=label, data=dfmean, y=rec_filter, x="time", color="black")
   
        # plot them all, don't bother with show/hide
        out = dfoutput

        aspects = ['EPSP_amp', 'EPSP_slope', 'volley_amp', 'volley_slope']

        for aspect in aspects:
            # if norm is checked, use the _norm columns
            if aspect.startswith('EPSP') and uistate.checkBox['norm_EPSP']:
                aspect = f"{aspect}_norm"
            # make an attribute named (label + ' ' + aspect)
            if aspect not in out.columns:
                raise ValueError(f"ERROR (ui_plot.py UIplot graph): no {aspect} in {rec_name}")

            if aspect.startswith('EPSP_amp') and not np.isnan(t_EPSP_amp):
                y_position = dfmean.loc[dfmean.time == t_EPSP_amp, rec_filter]
                # print(f"t_EPSP_amp: {t_EPSP_amp} - {np.isnan(t_EPSP_amp)}")
                # print(f"y_position: {y_position}")
                axm.plot(t_EPSP_amp, y_position, marker='v', markerfacecolor='green', markeredgecolor='green', markersize=10, alpha = 0.3, label=f"{label} EPSP amp marker")
                _ = sns.lineplot(ax=ax1, data=out, y=aspect, x="sweep", color="green", linestyle='--', label=f"{label} EPSP amp")
            if aspect.startswith('EPSP_slope')  and not np.isnan(t_EPSP_slope):
                x_start = t_EPSP_slope - t_EPSP_slope_size
                x_end = t_EPSP_slope + t_EPSP_slope_size
                y_start = dfmean[rec_filter].iloc[(dfmean['time'] - x_start).abs().idxmin()]
                y_end = dfmean[rec_filter].iloc[(dfmean['time'] - x_end).abs().idxmin()]
                axm.plot([x_start, x_end], [y_start, y_end], color='green', linewidth=10, alpha=0.3, label=f"{label} EPSP slope marker")
                _ = sns.lineplot(ax=ax2, data=out, y=aspect, x="sweep", color="green", alpha = 0.3, label=f"{label} EPSP slope")
            if aspect == 'volley_amp' and not np.isnan(t_volley_amp):
                y_position = dfmean.loc[dfmean.time == t_volley_amp, rec_filter]
                axm.plot(t_volley_amp, y_position, marker='v', markerfacecolor='blue', markeredgecolor='blue', markersize=10, alpha = 0.3, label=f"{label} volley amp marker")
                ax1.axhline(y=volley_amp_mean, color='blue', alpha = 0.3, linestyle='--', label=f"{label} volley amp mean")
                #_ = sns.lineplot(ax=ax1, label=f"{label} {aspect}", data=out, y=aspect, x="sweep", color="blue", linestyle='--', alpha = 0.3)
            if aspect == 'volley_slope' and not np.isnan(t_volley_slope):
                x_start = t_volley_slope - t_volley_slope_size
                x_end = t_volley_slope + t_volley_slope_size
                y_start = dfmean[rec_filter].iloc[(dfmean['time'] - x_start).abs().idxmin()]
                y_end = dfmean[rec_filter].iloc[(dfmean['time'] - x_end).abs().idxmin()]
                axm.plot([x_start, x_end], [y_start, y_end], color='blue', linewidth=10, alpha=0.3, label=f"{label} volley slope marker")
                ax2.axhline(y=volley_slope_mean, color='blue', alpha = 0.3, label=f"{label} volley slope mean")
                #_ = sns.lineplot(ax=ax2, label=f"{label} {aspect}", data=out, y=aspect, x="sweep", color="blue", alpha = 0.3)
