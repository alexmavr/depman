
# names of the diagnostics
diagnostics = ['infoliOutputDivergence', 'processExit', 'coreReachability']

# Location of infoli files
sim_dump_location = '/shared/alex/brain/'

# Safe location to keep backup files
safe_location = '/home/alex/bak/'

# rccerun path
rccerun_path = '/shared/alex/brain/rccerun'

# Infoli kill script path - RELATIVE TO RCCERUN
killfoli_path = '../killfoli'

# injector input files
infoliInjectorFile = sim_dump_location + 'injectors/infolijector.txt'
coreFailureInjectorFile = sim_dump_location + 'injectors/corefailjector.txt'
coreShutdownInjectorFile = sim_dump_location + 'injectors/coreshutjector.txt'
processExitInjectorFile = sim_dump_location + 'injectors/procexitjector.txt'

# True if running on a development environment rather than the SCC
devel = False

# max number of elements to utilize for the MTTF estimation
moving_avg_N = 50

# if False, only DUE checkpoints will be used.
use_SDC_checkpoints = True
