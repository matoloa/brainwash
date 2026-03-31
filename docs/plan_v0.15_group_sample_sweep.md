# Plan v0.15: Group, Sample, and Sweep Selection

## Mission Statement

The primary goal of version 0.15 is to introduce functionality that allows users to select, highlight, and categorize specific sweeps and recordings for enhanced statistical analysis and data presentation.

Specifically, this update focuses on two main features:

1. **Sweep Highlighting for Statistical Grouping:**
   Allow the user to highlight important sweeps (for example, two bins of 10 sweeps—one immediately before and one after a stimulus train). While this patch focuses on the selection mechanism, these grouped selections will be utilized in later patches to perform statistical tests (e.g., Student's t-tests) to evaluate the differences between the pre- and post-stimulus groups.

2. **Sample Designation for Visual Overlay:**
   Enable users to set specific recordings as "samples." Designating a recording as a sample will allow its trace to be visually overlaid onto presented graphs in exported images, providing clear, representative examples alongside aggregated data.
