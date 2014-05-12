import logging
from time import sleep
from monitors import lineProcessor, fileReader
from injectors import infoliInjector
from scc_diagnostics import diagnostic 

class infoliOutputDivergence(diagnostic):
    def __init__(self, manager):
        self.manager = manager
        self.injectors = [infoliInjector(self)]
        self.min_step = 0
        diagnostic.__init__(self)
        self._spawn_readers()

    def _spawn_readers(self):
        # populate the readers list with file readers for every infoli output file
        self.readers = []
        for core in map(lambda x : x[3:], self.manager.cores):
            if core[0] == '0':
                core = core[1]
            outfile = self.manager.sim_dir + 'InferiorOlive_Output' + core + '.txt'
            self.readers.append(fileReader(outfile, infoliLineProcessor(core, self, self.min_step)))

    def reinitialize(self):
        self._spawn_readers()
        sleep(2)

    def wait(self):
        self.min_step = min(map(lambda x:x.line_processor.simstep, self.readers))
        if len(self.manager.failed_diagnostics()) != 0:
            self.manager.min_step = self.min_step
            print "SDC detection will continue from step " + str(self.min_step)
            for reader in self.readers:
                reader.wait()
            sleep(2)

    def completed(self):
        # returns true if all threads have completed
        for i in range(self.manager.cores):
            if self.readers[i].line_processor.simstep < 120000:
                return False
        return True

    def countermeasure_procedure(self):
        from scc_countermeasures import restartSimulation, coreReboot, platformReinitialization
        return [[restartSimulation(self.manager)], \
            [coreReboot(self.manager.cores, self.manager.cores), restartSimulation(self.manager)], \
            [platformReinitialization(self.manager.cores), restartSimulation(self.manager)]]


''' Processes the output file of each core through infoli-specific methods'''
class infoliLineProcessor(lineProcessor):
    def __init__(self, core, diagnostic, step):
        self.core = int(core)
        self.simstep = step
        self.diagnostic = diagnostic
        self.done = False

    def expected_length(self):
        return self.diagnostic.manager.cellcount + 3

    def assert_line(self, line):
        linelist = line.split()
        if len(linelist) != self.expected_length():
            raise AssertionError
        try:
            int(linelist[0]) # first element must be an integer
            map(float,linelist[3:]) # voltages must be floats
        except ValueError:
            raise AssertionError

    def break_condition(self, line):
        return line.split()[0] == '#simSteps'

    def process_line(self, line):
        ''' Returns True if no errors were found '''
        linelist = line.split()

        try:
            simstep = int(linelist[0])
        except ValueError, TypeError:
            logging.error("Possible SDC: simstep could not be parsed as int")
            self.diagnostic.fail()
            return

        #if self.core == 0:
            #print simstep
        if simstep <= self.simstep:
            return # skip simsteps of previous chunks
        self.simstep = simstep

        for voltage in linelist[3:]:
            try:
                v = float(voltage)
            except ValueError, TypeError:
                logging.error("Possible SDC: voltage could not be parsed as float")
                self.diagnostic.fail()
                return
            if (v < -100) or (v > 100):
                logging.error("Voltage %s of core exceeded threshold")
                self.diagnostic.fail()
                return


