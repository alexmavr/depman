========
Depman
========

An Adaptive Run-Time Dependability Manager for Many-Core Checkpoint/Restart Implementations



Overview
============


Depman is a run-time manager that controls the operation of Checkpoint/Restart applications.

It resolves common error profiles such as unreachable cores or silent data corruptions by utilizing available system-level actions.

Depman utilizes two novel approaches the field of systems dependability:

-When the target platform is underutilized, the remaining tasks are assigned on the chip through a novel thermal-aware algorithm, aiming to minimize the creation of thermal hotspots.
-The waste time of the C/R scheme is minimized through an adaptive closed-loop optimization scheme.
After each failure, the mean time to failure of the system is estimated and checkpoint placements are adjusted accordingly.


The present implementation is configured for the Single-Chip Cloud Computer (SCC) by Intel Labs and the InfOli Simulator, a biologically acurate neuron simulator developed by the Erasmus MC in Rotterdam.


For a quick overview of the Depman tool, take a look at the 
`Slide Presentation
<https://github.com/afein/depman/blob/master/Presentation.pdf?raw=true>`_.


The complete documentation, analysis and experimental results are located in the 
`Diploma Thesis 
<https://github.com/afein/depman/blob/master/Thesis.pdf?raw=true>`_/

A conference paper based on the thesis work is currently under peer review, outlining the closed-loop checkpoint interval optimization scheme and the thermal-aware task reallocation algorithm. 

Copyright Information
====================

Depman was developed as part of my Diploma Thesis at the National Technical University of Athens.

Copyright (C) 2014 Alexandros Mavrogiannis 

All code is Licensed under the GPLv3. 

All rights reserved for the thesis document, "Thesis.pdf", and the presentation slides, "Presentation.pdf".
