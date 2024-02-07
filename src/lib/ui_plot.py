import seaborn as sns
import numpy as np

class UIplot():
    def __init__(self, uistate):
        self.uistate = uistate
        print(f"UIplot instantiated {self.uistate.anyView()}")

    def graph(self, dict_row, dfmean, dfoutput, axm, ax1, ax2):
        uistate = self.uistate
        t_EPSP_amp = dict_row['t_EPSP_amp']
        t_EPSP_slope = dict_row['t_EPSP_slope']
        t_EPSP_slope_size = dict_row['t_EPSP_slope_size']
        t_volley_amp = dict_row['t_volley_amp']
        volley_amp_mean = dict_row['volley_amp_mean']
        t_volley_slope = dict_row['t_volley_slope']
        t_volley_slope_size = dict_row['t_volley_slope_size']
        volley_slope_mean = dict_row['volley_slope_mean']

        # plot relevant filter of dfmean on main_canvas_mean
        label = f"{dict_row['recording_name']}"
        rec_filter = dict_row['filter'] # the filter currently used for this recording
        if rec_filter != 'voltage':
            label = f"{label} ({rec_filter})"
        _ = sns.lineplot(ax=axm, label=label, data=dfmean, y=rec_filter, x="time", color="black")
        out = dfoutput
        show = uistate.checkBox
        aspect = {"EPSP_amp": show['EPSP_amp'], "EPSP_slope": show['EPSP_slope'], "volley_amp": show['volley_amp'], "volley_slope": show['volley_slope']}
        
        for key, value in aspect.items():
            if key.startswith('EPSP') and uistate.checkBox['norm_EPSP']:
                key = f"{key}_norm"
            if value and key in out.columns:
                if key.startswith('EPSP_amp') and not np.isnan(t_EPSP_amp):
                    _ = sns.lineplot(ax=ax1, label=f"{label}_{key}", data=out, y=key, x="sweep", color="green", linestyle='--')
                    print(f"t_EPSP_amp: {t_EPSP_amp} - {np.isnan(t_EPSP_amp)}")
                    y_position = dfmean.loc[dfmean.time == t_EPSP_amp, rec_filter]
                    print(f"y_position: {y_position}")
                    axm.plot(t_EPSP_amp, y_position, marker='v', markerfacecolor='green', markeredgecolor='green', markersize=10, alpha = 0.3)
                if key.startswith('EPSP_slope')  and not np.isnan(t_EPSP_slope):
                    _ = sns.lineplot(ax=ax2, label=f"{label}_{key}", data=out, y=key, x="sweep", color="green", alpha = 0.3)
                    x_start = t_EPSP_slope - t_EPSP_slope_size
                    x_end = t_EPSP_slope + t_EPSP_slope_size
                    y_start = dfmean[rec_filter].iloc[(dfmean['time'] - x_start).abs().idxmin()]
                    y_end = dfmean[rec_filter].iloc[(dfmean['time'] - x_end).abs().idxmin()]
                    axm.plot([x_start, x_end], [y_start, y_end], color='green', linewidth=10, alpha=0.3)
                if key == 'volley_amp' and not np.isnan(t_volley_amp):
                    ax1.axhline(y=volley_amp_mean, color='blue', alpha = 0.3, linestyle='--')
                    #_ = sns.lineplot(ax=ax1, label=f"{label}_{key}", data=out, y=key, x="sweep", color="blue", linestyle='--', alpha = 0.3)
                    y_position = dfmean.loc[dfmean.time == t_volley_amp, rec_filter]
                    axm(t_volley_amp, y_position, marker='v', markerfacecolor='blue', markeredgecolor='blue', markersize=10, alpha = 0.3)
                if key == 'volley_slope' and not np.isnan(t_volley_slope):
                    ax2.axhline(y=volley_slope_mean, color='blue', alpha = 0.3)
                    #_ = sns.lineplot(ax=ax2, label=f"{label}_{key}", data=out, y=key, x="sweep", color="blue", alpha = 0.3)
                    x_start = t_volley_slope - t_volley_slope_size
                    x_end = t_volley_slope + t_volley_slope_size
                    y_start = dfmean[rec_filter].iloc[(dfmean['time'] - x_start).abs().idxmin()]
                    y_end = dfmean[rec_filter].iloc[(dfmean['time'] - x_end).abs().idxmin()]
                    axm.plot([x_start, x_end], [y_start, y_end], color='blue', linewidth=10, alpha=0.3)

