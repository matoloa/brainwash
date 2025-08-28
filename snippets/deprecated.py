# Functions that are not in use anymore, but might be useful again in the future


# build_dfmean checking for duplicates (deprecated; now prevented at read)
    dfmean = dfdata.copy()
    dfmean.drop(columns=['datetime', 'sweep_raw', 'sweep'], inplace=True)
    dfmean.rename(columns={'voltage_raw': 'voltage'}, inplace=True)
    # Aggregate rows with identical 'time' values by computing the mean
    dfmean = dfmean.groupby('time').mean().reset_index()

    # leftovers:
    # Ensure aggregation over 'sweep' and 'time' removes all duplicates
    dfdata = dfdata.groupby(['sweep', 'time'], as_index=False)['voltage_raw'].mean()
    print("aggregation finished.")

    # Check for duplicates after aggregation (for debugging purposes)
    if dfdata.duplicated(['sweep', 'time']).any():
        print("Warning: Still duplicates present after aggregation.")

'''

    Legacy method
    returns a list of tuples: [(dict_meta, df_raw), ...]
    There was considerable postprocessing in the original code - channels and stims
        df_ch_st = df_ch.loc[df_ch.sweep_raw % nstims == i].copy()
        df_ch_st['sweep'] = (df_ch_st.sweep_raw / nstims).apply(lambda x: int(np.floor(x)))
    # 3) Assumptions: 2 stims, for now
    list_stims = ["a", "b"]
    nstims = len(list_stims)
    nchannels = df.channel.nunique()
    sweep_duration = df.time.nunique()
    df.sort_values(by=['datetime', 'channel'], inplace=True, ignore_index=True)
    df['sweep_raw'] = df.index // (sweep_duration * nchannels)
    # 4) split by channel and stim
    list_tuple_data = []
    for channel in df.channel.unique():
        print(f" - channel: {channel} (nchannels: {nchannels}), nstims: {nstims}, sweep_duration: {sweep_duration}")
        if keep_non_stim_data:
            df_ch = df # TODO NOT TESTED!
        else:
            df_ch = df[df.channel==channel]
        for i, stim in enumerate(list_stims):
            full_recording_name = f"{recording_name}_Ch{channel}_{stim}"
            df_ch_st = df_ch.loc[df_ch.sweep_raw % nstims == i].copy()
            df_ch_st['sweep'] = (df_ch_st.sweep_raw / nstims).apply(lambda x: int(np.floor(x)))
        df_raw = df
        dict_meta = {
            "recording_name": full_recording_name,
            "channels": channels,
            "nsweeps": sweeps,
            "sweep_duration": len(abf.getAllXs()) / abf.sampleRate,
            "sampling_rate": abf.sampleRate,
            "resets": [],
        }
        # 4a) add tuple to list
        list_tuple_data.append((dict_meta, df_raw))
    return list_tuple_data'''



def parseProjFiles(dict_folders, df=None, recording_name=None, source_path=None, single_stim=False):
    """
    DEPRECATED: Still operational, called from ui.py
    * receives a df of project data file paths built in ui
        files that are already parsed are to be overwritten (ui.py passes filitered list of unparsed files)
    * creates a datafile by unique source file/channel/stim combination
    * Stim defaults to a and b
    * saves two files:
        dict_folders['data']<recording_name>_Ch<Ch>_<Stim>.csv
        dict_folders['cache']<recording_name>_Ch<Ch>_<Stim>_dfmean.csv
    
    returns a list of <recording_name>_Ch<Ch>_<Stim> for updating df_project recording names
    calls build_dfmean() to create an average, prim and bis file, per channel-stim combo
    """
    def parser(dict_folders, recording_name, source_path):
        df = None
        dict_data = {}
        if verbose:
            print(f" - parser, source_path: {source_path}")
        if Path(source_path).is_dir():
            # check contents of folder: .ibw or .abf
            list_files = [i for i in os.listdir(source_path) if -1 < i.find(".ibw") or -1 < i.find(".abf")]
            filetype = None
            if -1 < list_files[0].find(".abf"):
                filetype = "abf"
            elif -1 < list_files[0].find(".ibw"):
                filetype = "ibw"
            if filetype is None:
                raise ValueError(f" - - no supported files found in {source_path}")

            if filetype == "abf":
                df = parse_abfFolder(folderpath=Path(source_path))
            elif filetype == "ibw":
                df = parse_ibwFolder(folder=Path(source_path))#, dev=True)
        else:
            # set filetype to last 3 letters of filename
            filetype = source_path[-3:]
            if filetype == "csv":
                df = pd.read_csv(source_path)
                file_base = os.path.splitext(os.path.basename(source_path))[0].replace('.', '_')
                persistdf(file_base=file_base, dict_folders=dict_folders, dfdata=df)
                dict_sub = {
                    'nsweeps': df['sweep'].nunique(),
                    # channel is what comes after the last Ch in the filename, and ends before the first _
                    'channel': source_path.split("Ch")[-1].split("_")[0],
                    # stim is the last letter in the filename, before the .csv
                    'stim': source_path.split("_")[-1].split(".")[0],
                    # sweep_duration is the difference between the highest and the lowest time in the file
                    'sweep_duration': df['time'].max() - df['time'].min(),
                    # reset is the first sweep number after every sweep_raw reset: finds recording breaks for display purposes
                    'resets': df[(df['sweep_raw'] == df['sweep_raw'].min()) & (df['time'] == 0)]['sweep'].tolist()[1:]
                    }
                # TODO: Add checks for csv files; must be brainwash formatted!
                dict_data[file_base] = dict_sub
                return dict_data
            elif filetype == "abf":
                df = parse_abf(filepath=Path(source_path))
            elif filetype == "ibw":
                df = parse_ibw(filepath=Path(source_path))
        if df is None:
            raise ValueError(f" - - no supported files found in {source_path}")
        df = df.sort_values(by='datetime').reset_index(drop=True)
        # sort df2parse in channels and stims (a and b)
        if single_stim:
            if verbose:
                print(" - - user set single_stim=True")
                list_stims=["a"]
        else: #default to 2 stims 
            if verbose:
                print(" - - default: two stims per channel")
                list_stims=["a", "b"]
        nstims = len(list_stims)
        nchannels = df.channel.nunique()
        sweep_duration = df.time.nunique()

        print(f" - - nchannels: {nchannels}, nstims: {nstims}, sweep_duration: {sweep_duration}")

        # TODO: Why is this copied?
        dfcopy = df.copy()
        dfcopy = dfcopy.sort_values(by=['datetime', 'channel']).reset_index(drop=True)
        dfcopy['sweep_raw'] = dfcopy.index.to_numpy() // (sweep_duration * nchannels)
        print (f" - - dfcopy: {dfcopy}")
        for channel in dfcopy.channel.unique():
            df_ch = dfcopy[dfcopy.channel==channel]
            for i, stim in enumerate(list_stims):
                file_base = f"{recording_name}_Ch{channel}_{stim}"
                print(f"file_base: {file_base}")
                if filetype == "abf": # split df by % nstims
                    df_ch_st = df_ch.loc[df_ch.sweep_raw % nstims == i].copy()
                    df_ch_st['sweep'] = (df_ch_st.sweep_raw / nstims).apply(lambda x: int(np.floor(x)))
                elif filetype == "ibw":
                    if False: # split df; time < 0.5 is stim a, time >= 0.5 is stim b
                        # TODO: This is a stupid approach; don't split the data before the stims are placed!
                        if stim == "a":
                            df_ch_st = dfcopy.loc[dfcopy.time < 0.25].copy()
                        if stim == "b":
                            df_ch_st = dfcopy.loc[dfcopy.time >= 0.5].copy()  
                    else:
                        df_ch_st = dfcopy.copy()
                    df_ch_st['sweep'] = df_ch_st.sweep_raw
                df_ch_st.drop(columns=['channel'], inplace=True)
                print(f"nunique: {df_ch_st['sweep'].nunique()}")
                dfmean, i_stim = build_dfmean(df_ch_st)
                dffilter = zeroSweeps(dfdata=df_ch_st, i_stim=i_stim)
                persistdf(file_base=file_base, dict_folders=dict_folders, dfdata=df_ch_st, dfmean=dfmean, dffilter=dffilter)
                # Build dict: keys are datafile names, values are a dict of nsweeps, channels, stim, and reset (the first sweep number after every sweep_raw reset: finds recording breaks for display purposes)
                dict_sub = {
                    'nsweeps': df_ch_st['sweep'].nunique(),
                    'channel': channel,
                    'stim': stim,
                    'sweep_duration': df_ch_st['time'].max() - df_ch_st['time'].min(),
                    'resets': df_ch_st[(df_ch_st['sweep_raw'] == df_ch_st['sweep_raw'].min()) & (df_ch_st['time'] == 0)]['sweep'].tolist()[1:]
                }
                dict_data[f"{recording_name}_Ch{channel}_{stim}"] = dict_sub
        return dict_data

    if verbose:
        print(f"proj folder: {dict_folders['project']}")
        if source_path is not None:
            print(f"recording_name: {recording_name}")
            print(f"source_path: {source_path}")
        if df is not None:
            print(f"recording_name: {df['recording_name']}")
            print(f"path: {df['path']}")

    if recording_name is not None:
        list_data = parser(dict_folders=dict_folders, recording_name=recording_name, source_path=source_path)
        return list_data

    if df is not None:
        df_unique_names = df.drop_duplicates(subset='recording_name')
        for i, row in df_unique_names.iterrows():
            recording_name = row['recording_name']
            source_path = row['path']
            list_data = parser(dict_folders=dict_folders, recording_name=recording_name, source_path=source_path)
        return list_data

# ui corresponding part:
        dict_data = parse.parseProjFiles(dict_folders=self.dict_folders, recording_name=recording_name, source_path=source_path, single_stim=uistate.checkBox['force1stim'])
        for new_name, dict_sub in dict_data.items():
            nsweeps = dict_sub.get('nsweeps', None) 
            if nsweeps is not None:
                # Check for duplicates
                if new_name in recording_names:
                    recording_names[new_name] += 1
                    new_name = f"{new_name}({recording_names[new_name]})"
                else:
                    recording_names[new_name] = 1
                df_proj_new_row = self.create_new_row(df_proj_row, new_name, dict_sub)
                self.rows.append(df_proj_new_row)

##################################################################
#    Temporary functions for David's project - TODO: Purge       #
##################################################################
            # TODO: Temporary for David's master; deprecate
        self.actionCopyMeans = QtWidgets.QAction("Copy means", self)
        self.actionCopyMeans.triggered.connect(self.export_means)
        self.actionCopyMeans.setShortcut("Ctrl+M")
        self.menuEdit.addAction(self.actionCopyMeans)

    def trigger_export_selection(self):
        self.usage("trigger_export_selection")
        self.export_selection()

    def trigger_export_groups(self):
        self.usage("trigger_export_groups")
        self.export_groups()


    def export_means(self):
        print("export_means")
        means_list = []
        df_p = self.get_df_project()
        for _, p_row in df_p.iterrows():
            df = self.get_dfoutput(p_row)
            rec_name = p_row['recording_name']
            rec_ID = p_row['ID']
            group_ID = self.get_groupsOfRec(rec_ID)
            group_name = self.dd_groups[group_ID[0]]['group_name']
        
            # Define sweep ranges for averaging
            sweep_ranges = {
                '0': (0, 9),
                '110': (110, 119),
                '120': (120, 129),
                '590': (590, 599),
            }
            
            # Initialize dictionary to store means
            means_dict = {}
            
            # Calculate mean for each sweep range for EPSP_amp, EPSP_slope, volley_amp, and volley_slope
            for prefix, (start, end) in sweep_ranges.items():
                filtered_df = df[df['sweep'].between(start, end)]
                means_dict[f'EPSP_amp_mean_{prefix}'] = filtered_df['EPSP_amp'].mean()
                means_dict[f'EPSP_slope_mean_{prefix}'] = filtered_df['EPSP_slope'].mean()
                means_dict[f'volley_amp_mean_{prefix}'] = filtered_df['volley_amp'].mean()
                means_dict[f'volley_slope_mean_{prefix}'] = filtered_df['volley_slope'].mean()  # Assuming 'volley_slope' is a column in your DataFrame
            # Combine with other data
            row_dict = {
                'rec_name': rec_name,
                'group_name': group_name,
                **means_dict  # Merge the means_dict into row_dict
            }
        
            means_list.append(row_dict)
    
        df_means_by_group = pd.DataFrame(means_list)
        # Sort by 'group_name' in reverse alphabetical order
        df_means_by_group = df_means_by_group.sort_values(by='group_name', ascending=False)
        df_means_by_group.to_clipboard(index=False)
        

    def export_selection(self): # WARNING! Experimental feature for very specific use-cases. TODO: generalize!
        if uistate.checkBox['bin']:
            print("export_selection of binned data, treated as IO - WARNING! Experimental feature for very specific use-cases.")
            aspect_pairs = []
            if uistate.checkBox['EPSP_amp']:
                aspect_pairs.append(("volley_amp", "EPSP_amp"))
            if uistate.checkBox['EPSP_slope']:
                aspect_pairs.append(("volley_slope", "EPSP_slope"))
            print(aspect_pairs)
            if not aspect_pairs:
                print("No aspects selected for export.")
                return
            df_selected = self.get_df_project()
            if uistate.rec_select:  # if something is selected, export only that
                df_selected = df_selected.iloc[uistate.rec_select]

            for x_aspect, y_aspect in aspect_pairs:
                output_path = Path(f"{self.projects_folder}/{self.projectname}_{x_aspect.split('_')[-1]}.png")
                print(f"Exporting {x_aspect} vs {y_aspect} to {output_path}")
                dict_rec_legend_color_df = {}
                dd_r_lines = {}
                for i, p_row in df_selected.iterrows():
                    rec = p_row['recording_name']
                    df = self.get_dfoutput(p_row)
                    color = uistate.colors[i % len(uistate.colors)]
                    dict_rec_legend_color_df[rec] = rec, color, df
                    dd_r_lines[rec] = analysis.regression_line(df[x_aspect], df[y_aspect])

                print(f"Calling create_scatterplot for {len(dict_rec_legend_color_df)} dataframes with aspects {x_aspect} and {y_aspect}")
                uiplot.create_scatterplot(dict_rec_legend_color_df, x_aspect, y_aspect, dd_r_lines, output_path)
        else: # For now, just export the output window as it is TODO: actually export selection!
            print("export_selection of non-binned data, snapshot of output window - WARNING! Experimental feature for very specific use-cases.")
            figure = self.canvasOutput.figure
            # Construct the full path with the specified folder and project name
            filename = os.path.join(self.projects_folder, f"{self.projectname}.png")
            # Save the figure
            figure.savefig(filename, dpi=300)  # Adjust dpi for desired resolution
            print(f"Canvas output saved to {filename}")


    def export_groups(self): # WARNING! Experimental feature for very specific use-cases. TODO: generalize!
        if uistate.checkBox['output_per_stim']: # TODO: now interpreted as PP export
            print("export_groups: PP barplot export - WARNING! Experimental feature for very specific use-cases!")
            dict_group_color_ratio_SEM = {}
            for group_ID, dict_group in self.dd_groups.items():
                if dict_group['show']:
                    df_group = self.get_dfgroupmean(group_ID)
                    if uistate.checkBox['EPSP_amp']:
                        group_ratio = df_group.loc[df_group['stim'] == 2, 'EPSP_amp_norm_mean'].values[0]
                        group_SEM = df_group.loc[df_group['stim'] == 2, 'EPSP_amp_norm_SEM'].values[0]
                        output_path = Path(f"{self.projects_folder}/{self.projectname}_amp.png")
                        str_aspect = "EPSP amplitude"
                    else:
                        group_ratio = df_group.loc[df_group['stim'] == 2, 'EPSP_slope_norm_mean'].values[0]
                        group_SEM = df_group.loc[df_group['stim'] == 2, 'EPSP_slope_norm_SEM'].values[0]
                        output_path = Path(f"{self.projects_folder}/{self.projectname}_slope.png")
                        str_aspect = "EPSP slope"
                    dict_group_color_ratio_SEM[dict_group['group_name']] = [dict_group['color'], group_ratio, group_SEM]
            print(f"Calling create_barplot for {len(dict_group_color_ratio_SEM)} groups")
            uiplot.create_barplot(dict_group_color_ratio_SEM, str_aspect, output_path)
        else:
            print("export_groups: scatterplot export - WARNING! Experimental feature for very specific use-cases!")
            aspect_pairs = []
            if uistate.checkBox['EPSP_amp']:
                aspect_pairs.append(("volley_amp", "EPSP_amp"))
            if uistate.checkBox['EPSP_slope']:
                aspect_pairs.append(("volley_slope", "EPSP_slope"))
            print(aspect_pairs)
            if not aspect_pairs:
                print("No aspects selected for export.")
                return
            df_selected = self.get_df_project()
            if uistate.rec_select:  # if something is selected, export only that
                df_selected = df_selected.iloc[uistate.rec_select]

            for x_aspect, y_aspect in aspect_pairs:
                output_path = Path(f"{self.projects_folder}/{self.projectname}_grouped_{x_aspect.split('_')[-1]}.png")
                print(f"Exporting group {x_aspect} vs {y_aspect} to {output_path}")
                dict_rec_legend_color_df = {} # legend (group)name; color, df
                dd_r_lines = {}
                dd_r_report = {}
                for _, p_row in df_selected.iterrows():
                    rec = p_row['recording_name']
                    rec_in_groups = self.get_groupsOfRec(p_row['ID'])
                    if rec_in_groups:
                        dict_prime_group = self.dd_groups[rec_in_groups[0]]
                        prime_group_name = dict_prime_group['group_name']
                        legend = f"{prime_group_name}"# {rec}"
                        color = dict_prime_group['color']
                    else:
                        legend = rec
                        color = 'black'
                    df = self.get_dfoutput(p_row)
                    dict_rec_legend_color_df[rec] = [legend, color, df]
                    dd_r_lines[rec] = analysis.regression_line(df[x_aspect], df[y_aspect])
                    # Assuming dd_r_lines[rec] is a dictionary
                    dd_r_report[rec] = dd_r_lines[rec]
                    dd_r_report[rec]['group'] = prime_group_name
                #TODO Temporary; make a df of dd_r_lines and save it to clipboard
                df_r_report = pd.DataFrame(dd_r_report)
                df_r_report.to_clipboard()

                print(f"Calling create_scatterplot for {len(dict_rec_legend_color_df)} dataframes with aspects {x_aspect} and {y_aspect}")
                uiplot.create_scatterplot(dict_rec_legend_color_df, x_aspect, y_aspect, dd_r_lines, output_path)

                

                # addRow DEBUG Block, draw event x/y lines and means
                self.plot_line(f"{label} {stim_str} amp_zero", 'axe', [-0.002, -0.001], [amp_zero, amp_zero], settings['rgb_EPSP_amp'], rec_ID, aspect='EPSP_amp', stim=stim_num)
                x, y = self.uistate.dict_rec_labels[f"{label} {stim_str}"]['line'].get_data()
                # filter x and y by amp_x
                start_time = t_row['t_EPSP_amp'] - t_row['EPSP_amp_halfwidth']
                end_time = t_row['t_EPSP_amp'] + t_row['EPSP_amp_halfwidth']
                # Find the index of the closest value to start_time and end_time in x
                start_index = (np.abs(x - start_time)).argmin()
                end_index = (np.abs(x - end_time)).argmin()
                x = x[start_index:end_index+1]
                y = y[start_index:end_index+1]
                mean = y.mean()
                # plot the mean line
                out_amp = out['EPSP_amp'].iloc[0] / -1000 # convert from mV to V, undo inversion
                out_amp = out_amp + amp_zero # undo amp-zero compensation
                self.plot_line(f"{label} {stim_str} amp_event: {str(round(mean, 6))}, {str(len(x))}", 'axe', amp_x, [mean, mean], 'green', rec_ID, aspect='EPSP_amp', stim=stim_num)
                self.plot_line(f"{label} {stim_str} amp_output: {str(round(out_amp, 6))}, {str(len(x))}", 'axe', amp_x, [out_amp, out_amp], 'red', rec_ID, aspect='EPSP_amp', stim=stim_num)





    above_threshold_indices = np.where(dfmean['prim'] > threshold)[0]
    # Filter the indices to ensure they are more than min_time_difference apart
    filtered_indices = []
    max_index = above_threshold_indices[0]
    max_value = dfmean['prim'][max_index]
    for i in range(1, len(above_threshold_indices)):
        current_index = above_threshold_indices[i]
        current_value = dfmean['prim'][current_index]
        previous_index = above_threshold_indices[i - 1]
        # If the time difference between the current and previous index is more than min_time_difference
        if dfmean['time'][current_index] - dfmean['time'][previous_index] > min_time_difference:
            # Add the index of the maximum value in the previous cluster to filtered_indices
            filtered_indices.append(max_index)
            # Reset max_index and max_value for the new cluster
            max_index = current_index
            max_value = current_value
        elif current_value > max_value:
            # Update max_index and max_value if the current value is greater than max_value
            max_index = current_index
            max_value = current_value
    # Add the index of the maximum value in the last cluster to filtered_indices
    filtered_indices.append(max_index)
    
    n_stims = len(filtered_indices)  # Count the number of unique stimuli
    print(f"zeroSweeps found {len(above_threshold_indices)} above_threshold_indices in {n_stims} unique stims.")  # Print the number of above-threshold indices and unique stimuli
    i_stim = filtered_indices[0]  # Get the first filtered index


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