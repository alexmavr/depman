========
Depman
========

An Adaptive Run-Time Dependability Manager for Many-Core Checkpoint/Restart Implementations



Introduction
============


Depman is a run-time manager that controls the operation of Checkpoint/Restart applications.

It resolves common error profiles, such as unreachable cores or easily detectable data corruption, by utilizing available system-level actions such as platform reinitialization or OS restart.

Depman also attempts to minimize the waste time of the C/R scheme by estimating the mean time to failure of the system and adjusting the checkpoint placements accordingly.

The present implementation is configured for Intel Labs' Single-Chip Cloud Computer (SCC) and the InfOli Simulator, a neuroscientific application.


For a quick overview of the Depman tool, take a look at the 
`Slide Presentation
<https://github.com/afein/depman/blob/master/Presentation.pdf?raw=true>`_


The complete documentation, analysis and experimental results are located in the 
`Complete Diploma Thesis 
<https://github.com/afein/depman/blob/master/Thesis.pdf?raw=true>`_


Copyright Information
====================

Depman was developed as part of my Diploma Thesis at the National Technical University of Athens.

Copyright (C) 2014 Alexandros Mavrogiannis 

All code is Licensed under the GPLv3. 

All rights reserved for the thesis document "Thesis.pdf".
