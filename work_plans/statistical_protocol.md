Statistical protocol
Experimental unit
Subject (animal) is the only independent experimental unit.
Subject defines the biological sample size (n).
Slice and Recording are nested repeated measurements and must never increase n.
Data hierarchy
Subject
└── Slice
└── Recording (Unique ID)
└── Repeated measurements

General analysis rules
Treat repeated measurements (time, stimulus strength, pulse) as within-recording factors.
Treat recordings as nested within slices, and slices as nested within subjects.
Use mixed-effects models whenever possible:
Fixed effects: Group and experimental factor(s).
Random effects: Subject, Slice within Subject, Recording within Slice.
If mixed models are unavailable:
Compute one summary value per recording.
Average recordings within each subject.
Perform statistical comparisons using subject means.
Never compare groups using recordings or slices as independent observations.
Reporting
Always report:
Number of subjects per group (n).
Number of slices.
Number of recordings.

Example:

Group A: n = 4 subjects, 8 slices, 88 recordings
Group B: n = 4 subjects, 8 slices, 88 recordings
Inferential statistics must use n = number of subjects, unless a hierarchical mixed model explicitly accounts for the nested structure.
Expected analyses
Time course

Mixed model:

Response ~ Group × Time + random effects
Report:
Group effect
Time effect
Group × Time interaction
Post hoc tests if interaction is significant
Input–Output (I/O)

Mixed model:

Response ~ Group × StimulusStrength + random effects
Report:
Group effect
Stimulus strength effect
Group × Stimulus strength interaction
Optionally report derived metrics (maximum response, slope, AUC, fitted parameters).
Paired Pulse (PP)

Mixed model:

PPR ~ Group × PulseCondition + random effects
Report:
Group effect
Pulse condition effect
Group × Pulse condition interaction
Definition of n
n = number of unique subjects (animals).
Slice and Recording improve measurement precision but do not increase sample size.
