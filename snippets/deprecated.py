# Functions that are not in use anymore, but might be useful again in the future
'''


    def sweepOutputs(self):
        # rebuild all outputs for all recordings based on output x = sweep number TODO: add option to show time instead
        self.uiFreeze()
        df_p = self.get_df_project()
        for _, p_row in df_p.iterrows():
            uiplot.unPlot(p_row['ID'])
            df_t = self.get_dft(p_row)
            dict_t = df_t.iloc[0].to_dict()
            dfmean = self.get_dfmean(row=p_row)
            dffilter = self.get_dffilter(p_row)
            dfoutput = analysis.build_dfoutput(df=dffilter, dict_t=dict_t, lineEdit=uistate.lineEdit)
            self.persistOutput(p_row['recording_name'], dfoutput)
            print(f"sweepOutputs: {p_row['recording_name']} {dfoutput.columns}")
            uiplot.addRow(p_row, df_t, dfmean, dfoutput)
        self.update_rec_show(reset=True)
        self.mouseoverUpdate()
        self.uiThaw()
        return dfoutput

    def stimOutputs(self):
        # rebuild all outputs for all recordings based on output x = stim number
        self.uiFreeze()
        df_p = self.get_df_project()
        df_parsed = df_p[df_p['sweeps'] != "..."]
        for _, p_row in df_parsed.iterrows():
            uiplot.unPlot(p_row['ID'])
            dfmean = self.get_dfmean(row=p_row)
            df_t = self.get_dft(row=p_row)
            dfoutput = analysis.build_dfstimoutput(dfmean=dfmean, df_t=df_t, lineEdit=uistate.lineEdit)
            print(f"stimOutputs: {p_row['recording_name']} {dfoutput.columns}")
            self.persistOutput(rec_name=p_row['recording_name'], dfoutput=dfoutput)
            uiplot.addRow(p_row, df_t, dfmean, dfoutput)
        self.update_rec_show(reset=True)
        self.mouseoverUpdate()
        self.uiThaw()
        return dfoutput

    def normOutputs(self): # TODO: also norm diffs (paired stim) when applicable
        df_p = self.get_df_project()
        for index, row in df_p.iterrows():
            dfoutput = self.get_dfoutput(row=row)
            print(f"editNormRange: rebuilding norm columns for {row['recording_name']}")
            self.normOutput(dfoutput)
            self.persistOutput(row['recording_name'], dfoutput)


    def normOutput(self, dfoutput, aspect=None): # TODO: reduntant? merge with normOutputs?
        normFrom = uistate.lineEdit['norm_EPSP_on'][0] # start
        normTo = uistate.lineEdit['norm_EPSP_on'][1] # end
        if aspect is None: # norm all existing columns and save file
            if 'EPSP_amp' in dfoutput.columns:
                selected_values = dfoutput.loc[normFrom:normTo, 'EPSP_amp']
                norm_mean = selected_values.mean() / 100 # divide by 100 to get percentage
                dfoutput['EPSP_amp_norm'] = dfoutput['EPSP_amp'] / norm_mean
            if 'EPSP_slope' in dfoutput.columns:
                selected_values = dfoutput.loc[normFrom:normTo, 'EPSP_slope']
                norm_mean = selected_values.mean() / 100 # divide by 100 to get percentage
                dfoutput['EPSP_slope_norm'] = dfoutput['EPSP_slope'] / norm_mean
            return dfoutput
        else: # norm specific column and DO NOT SAVE file (dragged on-the-fly-graphs are saved only on mouse release)
            selected_values = dfoutput.loc[normFrom:normTo, aspect]
            norm_mean = selected_values.mean() / 100 # divide by 100 to get percentage
            dfoutput[f'{aspect}_norm'] = dfoutput[aspect] / norm_mean
            return dfoutput

    def zoomAuto(self):
    # Obsolete extending axe to include all stims in the selected recordings
        print(f"zoomAuto, uistate.selected: {uistate.rec_select}, uistate.stim_select: {uistate.stim_select}")
        if uistate.rec_select:
        # axm
            df_p = self.get_df_project()
            df_selected = df_p.loc[uistate.rec_select]
            max_sweep_duration = df_selected['sweep_duration'].max()
            uistate.zoom['mean_xlim'] = (0, max_sweep_duration)
        # axe
            list_stims = []
            for index, p_row in df_selected.iterrows():
                dft = self.get_dft(row=p_row)
                if uistate.stim_select is not None and set(uistate.stim_select).issubset(dft.index):
                    t_stim_values = dft.loc[uistate.stim_select, 't_stim'].values.tolist()
                else:
                    t_stim_values = [dft['t_stim'].iloc[0]]  # Make sure t_stim_values is always a list
                list_stims.extend(t_stim_values)  # Use extend instead of append to flatten the list
            if list_stims:
                t_stim_min = min(list_stims) - 0.0005
                t_stim_max = max(list_stims) + 0.010
                if t_stim_min > 0:
                    uistate.zoom['event_xlim'] = (t_stim_min, t_stim_max)
        # ax1 and ax2, simplified (iterative version is pre 2024-05-06)
            uistate.zoom['output_xlim'] = 0, df_selected['sweeps'].max()


    def to_axis(self, axis_type): 
        # returns a list of labels that, per uistate settings, should be plotted on axis_type(str)
        df = self.df_recs2plot
        axis_list = []
        for index, row in df.iterrows():
            rec_filter = row['filter']
            key = f"{row['recording_name']} ({rec_filter})" if rec_filter != 'voltage' else row['recording_name']
            if axis_type == 'axm':
                if rec_filter != 'voltage':
                    key = f"mean {row['recording_name']} ({rec_filter})"
                else:
                    key = f"mean {row['recording_name']}"
                axis_list.append(key)
                for stim in range(1, row['stims'] + 1):
                    axis_list.append(f"{key} - stim {stim} marker")
            elif axis_type == 'axe':
                if self.checkBox['EPSP_amp']:
                    axis_list.append(f"{key} EPSP amp marker")
                if self.checkBox['EPSP_slope']:
                    axis_list.append(f"{key} EPSP slope marker")
                if self.checkBox['volley_amp']:
                    axis_list.append(f"{key} volley amp marker")
                if self.checkBox['volley_slope']:
                    axis_list.append(f"{key} volley slope marker")
                for stim in range(1, int(row['stims']) + 1):
                    stim_label = f"{key} - stim {stim}"
                    axis_list.append(stim_label)
            elif axis_type in ['ax1', 'ax2']:
                norm = " norm" if self.checkBox['norm_EPSP'] else ""
                if self.checkBox['EPSP_amp'] and axis_type == 'ax1':
                    axis_list.append(f"{key} EPSP amp{norm}")
                if self.checkBox['volley_amp'] and axis_type == 'ax1':
                    axis_list.append(f"{key} volley amp mean")
                if self.checkBox['EPSP_slope'] and axis_type == 'ax2':
                    axis_list.append(f"{key} EPSP slope{norm}")
                if self.checkBox['volley_slope'] and axis_type == 'ax2':
                    axis_list.append(f"{key} volley slope mean")
                axis_list.append(key)
        return axis_list
        

    def zoomOnScroll(self, event, parent, canvas, ax1=None, ax2=None):
        x = event.xdata
        y = event.ydata
        y2 = event.ydata
        if x is None or y is None: # if the click was outside the canvas, extrapolate x and y
            x_display, y_display = ax1.transAxes.inverted().transform((event.x, event.y))
            x = x_display * (ax1.get_xlim()[1] - ax1.get_xlim()[0]) + ax1.get_xlim()[0]
            y = y_display * (ax1.get_ylim()[1] - ax1.get_ylim()[0]) + ax1.get_ylim()[0]
            if ax2 is not None:
                y2 = y_display * (ax2.get_ylim()[1] - ax2.get_ylim()[0]) + ax2.get_ylim()[0]
        if event.button == 'up':
            zoom = 1.05
        elif event.button == 'down':
            zoom = 1 / 1.05
        else:
            return
        # Define the boundaries of the invisible rectangles
        left = 0.12 * parent.width()
        right = 0.88 * parent.width()
        bottom = 0.12 * parent.height() # NB: counts from bottom up!
        x_rect = [0, 0, parent.width(), bottom]
        slope_left = uistate.slopeOnly()
        if slope_left:
            ax2_rect = [0, 0, left, parent.height()]
        else:
            ax1_rect = [0, 0, left, parent.height()]
            ax2_rect = [right, 0, parent.width()-right, parent.height()]

        # Check if the event is within each rectangle
        in_x = x_rect[0] <= event.x <= x_rect[0] + x_rect[2] and x_rect[1] <= event.y <= x_rect[1] + x_rect[3]
        if slope_left:
            in_ax1 = False
        else:
            in_ax1 = ax1_rect[0] <= event.x <= ax1_rect[0] + ax1_rect[2] and ax1_rect[1] <= event.y <= ax1_rect[1] + ax1_rect[3]
        if ax2 is not None:
            in_ax2 = ax2_rect[0] <= event.x <= ax2_rect[0] + ax2_rect[2] and ax2_rect[1] <= event.y <= ax2_rect[1] + ax2_rect[3]
        else:
            in_ax2 = False
        
        if in_x:
            ax1.set_xlim(x - (x - ax1.get_xlim()[0]) / zoom, x + (ax1.get_xlim()[1] - x) / zoom)
        if in_ax1:
            ax1.set_ylim(y - (y - ax1.get_ylim()[0]) / zoom, y + (ax1.get_ylim()[1] - y) / zoom)
        if ax2 is not None:
            if in_ax2:
                ax2.set_ylim(y2 - (y2 - ax2.get_ylim()[0]) / zoom, y2 + (ax2.get_ylim()[1] - y2) / zoom)
        # if all in_s are false, zoom all axes
        if not in_x and not in_ax1 and not in_ax2:
            ax1.set_xlim(x - (x - ax1.get_xlim()[0]) / zoom, x + (ax1.get_xlim()[1] - x) / zoom)
            ax1.set_ylim(y - (y - ax1.get_ylim()[0]) / zoom, y + (ax1.get_ylim()[1] - y) / zoom)
            if ax2 is not None:
                ax2.set_ylim(y2 - (y2 - ax2.get_ylim()[0]) / zoom, y2 + (ax2.get_ylim()[1] - y2) / zoom)
        canvas.draw()


def label2idx(canvas, aspect): # Returns the index of the line labeled 'aspect' on 'canvas', or False if there is none.
    dict_labels = {k.get_label(): v for (v, k) in enumerate(canvas.axes.lines)}
    return dict_labels.get(aspect, False)

def unPlot(canvas, *artists): # Remove line if it exists on canvas
    #print(f"unPlot - canvas: {canvas}, artists: {artists}")
    for artist in artists:
        artists_on_canvas = canvas.axes.get_children()
        if artist in artists_on_canvas:
            #print(f"unPlot - removed artist: {artist}")
            artist.remove()

def outputAutoScale(ax, df, aspect): # Sets the y limits of ax to the min and max of df[aspect]
    if aspect == "EPSP_amp":
        ax.set_ylim(df['EPSP_amp'].min() - 0.1, df['EPSP_amp'].max() + 0.1)
    elif aspect == "EPSP_slope":
        ax.set_ylim(df['EPSP_slope'].min() - 0.1, df['EPSP_slope'].max() + 0.1)
    else:
        print(f"autoScale: {aspect} not supported.")


def graphGroups(self): # check if groups need to be updated, call uiplot.addGroup as needed
    self.usage("graphGroups")
    df_p = self.get_df_project()
    list_groups = []
    for i in uistate.selected:
        list_groups.extend(df_p.loc[i, 'group_IDs'].split(","))
    # Filter out ' ' and convert to set to remove duplicates
    list_groups = list(set(group for group in list_groups if group.strip() != ''))
    print(f"list_groups: {list_groups}")
    for group in list_groups:
        print(f"Group {group} is of type {type(group)}")
    # filter out groups that are not shown
    list_groups = [group for group in list_groups if uistate.group_show[group]]
    if list_groups:
        for group in list_groups:
            print(f"Adding group {group}")

def setGraphGroups(self, ax1, ax2, list_color): # TODO: deprecate
    print(f"setGraphGroups: {self.dict_groups['list_ID']}")
    df_p = self.get_df_project()
    for i_color, group in enumerate(self.dict_groups['list_ID']):
        dfgroup = df_p[df_p['groups'].str.split(',').apply(lambda x: group in x)]
        if uistate.group_show[group] == False:
            if verbose:
                print(f"Checkbox for group {group} is not checked")
            continue
        if dfgroup.empty:
            if verbose:
                print(f"No data in group {group}")
            continue

        # abort if any recording in group is a str
        if dfgroup['sweeps'].apply(lambda x: isinstance(x, str)).any():
            if verbose:
                print(f"Analyse all recordings in {group} to show group output.")
            continue
        self.plotGroup(ax1, ax2, group, list_color[i_color])

def plotGroup(self, ax1, ax2, group, groupcolor, alpha=0.3): # TODO: deprecate
    dfgroup_mean = self.get_dfgroupmean(key_group=group)
        # Errorbars, EPSP_amp_SEM and EPSP_slope_SEM are already a column in df
        # print(f'dfgroup_mean.columns: {dfgroup_mean.columns}')
    if dfgroup_mean['EPSP_amp_mean'].notna().any() & uistate.checkBox['EPSP_amp']:
        _ = sns.lineplot(data=dfgroup_mean, y="EPSP_amp_mean", x="sweep", ax=ax1, color=groupcolor, linestyle='--', alpha=alpha)
        ax1.fill_between(dfgroup_mean.sweep, dfgroup_mean.EPSP_amp_mean + dfgroup_mean.EPSP_amp_SEM, dfgroup_mean.EPSP_amp_mean - dfgroup_mean.EPSP_amp_SEM, alpha=0.3, color=groupcolor)
        ax1.axhline(y=0, linestyle='--', color=groupcolor, alpha = 0.4)
    if dfgroup_mean['EPSP_slope_mean'].notna().any() & uistate.checkBox['EPSP_slope']:
        _ = sns.scatterplot(data=dfgroup_mean, y="EPSP_slope_mean", x="sweep", ax=ax2, color=groupcolor, s=5, alpha=alpha)
        ax2.fill_between(dfgroup_mean.sweep, dfgroup_mean.EPSP_slope_mean + dfgroup_mean.EPSP_slope_SEM, dfgroup_mean.EPSP_slope_mean - dfgroup_mean.EPSP_slope_SEM, alpha=0.3, color=groupcolor)
        ax2.axhline(y=0, linestyle=':', color=groupcolor, alpha = 0.4)

    #uisub.setGraphSelected(df_analyzed=df_analyzed, ax1=ax1, ax2=ax2)
    # if just one selected, plot its group's mean
    # if len(df_analyzed) == 1:
    #     list_group = df_analyzed['groups'].iloc[0].split(',')
    #     for group in list_group:
    #         if group != " ":
    #             df_groupmean = self.get_dfgroupmean(key_group=group)
    #             if not df_groupmean.empty and uistate.group_show[group]:
    #                 group_index = self.dict_groups['list_ID'].index(group)
    #                 color = self.dict_groups['list_group_colors'][group_index]
    #                 self.plotGroup(ax1, ax2, group, color, alpha=0.05)
    # else: # if none of the selected are analyzed, plot groups instead
    #    if self.dict_groups['list_ID']:
    #        self.setGraphGroups(ax1, ax2, self.dict_groups['list_group_colors'])




         
@QtCore.pyqtSlot(list)
def slotPrintPaths(self, mypaths):
    if verbose:
        print(f"mystr: {mypaths}")
    strmystr = "\n".join(sorted(["/".join(i.split("/")[-2:]) for i in mypaths]))
    self.textBrowser.setText(strmystr)
    list_display_names = ["/".join(i.split("/")[-2:]) for i in mypaths]
    dftable = pd.DataFrame({"path_source": mypaths, "recording_name": list_display_names})
'''