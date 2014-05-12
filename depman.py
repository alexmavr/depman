# Dependability manager for the SCC

import sys
import os
import logging
import json
from signal import signal, SIGKILL, SIGINT
from time import sleep, time
from subprocess import Popen, call, check_output, PIPE, STDOUT
from Queue import Queue
from collections import deque
from threading import Lock, Thread

from scc_diagnostics import processExit, coreReachability
from infoli_diagnostics import infoliOutputDivergence
from scc_countermeasures import countermeasure_enum
from injectors import injectorManager

from config import *

class depman(object):
    completed = False   # True if the simulation is completed
    stopped = False     # The simulation run status

    def __init__(self):
        ''' Depman initialization '''
        # parse arguments
        if len(sys.argv) < 8:
            sys.exit("Please provide enough arguments (nue, hostfile, restart executable, executable, parameters)");

        offset = 1  # argument offset

        self.fault_injection = False
        if sys.argv[1] == '-i':
            ''' Fault Injection mode '''
            self.fault_injection = True
            offset = 2

        if sys.argv[offset] == '-nue':
            self.num_cores = int(sys.argv[offset+1])
        else:
            print "ERROR: -nue argument not specified"
            sys.exit(1)

        if sys.argv[offset+2] == '-f':
            self.hostfile = sys.argv[offset+3]
        else:
            print "ERROR: -f argument not specified"
            sys.exit(1)

        if not self.scc_env_check():
            print "ERROR: SCCKit not found in PATH"
            sys.exit(1)

        # set executables
        self.restart_exec = sys.argv[offset+4]
        self.exec_list = sys.argv[(offset+5):]

        # parse initial list of cores from the hosts file
        self.hostfd = open(os.path.join(os.getcwd(), self.hostfile), 'r')
        core_list = filter(None, self.hostfd.read().splitlines())
        self.initial_cores = map(lambda s:'rck'+s.strip(), core_list)
        self.hostfd.close()
        self.cores = self.initial_cores[:]

        self.cells = int(sys.argv[offset+6]) * int(sys.argv[offset+7])
        self.update_cellcount()

        if len(self.cores) < self.num_cores:
            print "ERROR: less cores in host file than requested"
            sys.exit(1)
        elif len(self.cores) > self.num_cores:
            print "WARNING: hostfile contains more cores than requested, some may not be used"
            self.cores = self.cores[self.num_cores:]

        # configure logging
        logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', \
                            datefmt='%d/%m/%Y %I:%M:%S %p', \
                            filename='infoli.log', filemode='w', \
                            level=logging.DEBUG)

        # set simulation directory as attribute
        self.sim_dir = sim_dump_location

        self.prev_globalmax = 0     # (infoli-specific) previous maximum recoverable simulation step
        self.min_step = 0
        self.checkpoints = []     # locations of checkpoints

        # create the safe location if it doesnt exist
        if not os.path.exists(safe_location):
            try:
                os.makedirs(safe_location)
            except OSError:
                logging.error("Error during safe location creation")
                exit(1)
            else:
                logging.info("Safe location directory successfully created")

        # The depman lock is held by the master thread while a simulation is running
        self.lock = Lock()

        # start simulation and create the diagnostics
        self.rccerun(self.exec_list)

        sleep(4) #wait for the task to be initially spawned at the SCC TODO: no error detection at this time
        self.diagnostics = []
        if 'processExit' in diagnostics:
            self.diagnostics.append(processExit(self))
        if 'infoliOutputDivergence' in diagnostics:
            self.diagnostics.append(infoliOutputDivergence(self))
        if 'coreReachability' in diagnostics:
            self.diagnostics.append(coreReachability(self, 3))
        if 'infoliOutputDivergence' not in diagnostics and use_SDC_checkpoint:
            print "use_SDC_checkpoint is True but no SDC detection diagnostic is used."
            loggin.warning("use_SDC_checkpoint is True but no SDC detection diagnostic is used.")
            use_SDC_checkpoint = False

        # Initialize the countermeasure procedure
        self.current_counter_proc = []

        # Initialize MTTF and MTTR estimation
        self.timestamp = 0  # initialized for when no diagnostics ever fail
        self.mttf_values = deque([], moving_avg_N)
        self.mttr_values = []
        self.failure_timestamp = time()

        # Start the fault injection manager if requested
        if self.fault_injection:
            self.injector = injectorManager(self.diagnostics)
            logging.info("Fault Injection module initialized")

        # Set the killfoli sigint handler
        signal(SIGINT, self.sigint_handler)

    def halt_injectors(self):
        self.injector.halt = True

    def update_cellcount(self):
        self.cellcount = self.cells / len(self.cores)

    def scc_env_check(self):
        ''' Check if sccReset can be located in depman's environment '''
        if devel:
            out = call(['which', 'echo'])
        else:
            out = call(['which', 'sccReset'])
        if out == 1:
            return False
        print "SCCKit located"
        return True

    def sigint_handler(self, signal, frame):
        ''' Handle Ctrl-C by killing the simulation on a non-daemon thread '''
        self.t = Thread(target=self.stop)
        self.t.daemon = False
        self.t.start()
        print "Depman terminated by SIGINT"
        logging.info("Depman terminating by SIGINT")
        sys.exit(0)

    def reinitialize_diagnostics(self):
        ''' forces a reinitialization of the diagnostics for the new simulation '''
        map(lambda d:d.reinit(), self.diagnostics)

    def unset_failed_diagnostics(self):
        ''' unsets the failed flag from all diagnostics '''
        for i in self.diagnostics:
            i.failed = False

    def wait_diagnostics(self):
        ''' Waits for the diagnostics to complete their current operations '''
        map(lambda d:d.wait(), self.diagnostics)

    def create_hostfile(self, cores):
        ''' Creates a new hostfile for the core numbers specified '''
        cores = map(lambda x:x[3:], cores)  #strip the rck prefix
        self.hostfd = open(os.path.join(os.getcwd(), self.hostfile), 'w+')
        for core in cores:
            self.hostfd.write(str(core).zfill(2) + '\n')
        self.hostfd.close()

    def new_DUE_checkpoint(self):
        ''' returns True if a new valid DUE checkpoint was found '''
        # TODO: move it somewhere more infoli-specific?
        import struct
        steps = []

        if devel:
            cellstate_size = 172
        else:
            cellstate_size = 168

        for i in range(len(self.cores)):
            steps.append([])
            with open(sim_dump_location + 'ckptFile%d.bin' % i, 'rb') as f:
                chunk = f.read(12)
                if (len(chunk) < 12):
                    logging.error("Checkpoint file %d is too short", i)
                    return False
                header = struct.unpack('iii', chunk)
                if header[0] * header[1] != len(self.cores) * self.cellcount:
                    logging.error("Checkpoint file %d contains invalid grid dimensions", i)
                    return False
                steps[i].append(header[2])
                chunk = f.read(cellstate_size * self.cellcount)
                if (len(chunk) < cellstate_size * self.cellcount):
                    logging.error("Checkpoint file %d is too short", i)
                    return False
                chunk = f.read(4)
                if (len(chunk) < 4):
                    logging.error("Checkpoint file %d is too short", i)
                    return False

                steps[i].append(struct.unpack('i', chunk)[0])

        # Determine the max common simulation step, TODO:infoli-specific
        globalmax = max(steps[0][0], steps[0][1])
        for core in steps[1:]:
            localmax = max(core[0], core[1])
            if localmax < globalmax:
                globalmax = localmax

        print "Maximum recoverable simulation step: " + str(globalmax)

        if globalmax <= self.prev_globalmax:
            return False
        self.prev_globalmax = globalmax

        # Check if a core's checkpoint file lacks the determined step (result of checkpoint corruption)
        for i, core in enumerate(steps):
            if core[0] != globalmax and core[1] != globalmax:
                logging.warning("Checkpoint File %d does not contain simulation step %d", i, globalmax)
                return False

        call( ['mkdir', safe_location + str(globalmax)])
        for i in range(len(self.cores)):
            call( ['cp', '-f', '--remove-destination', sim_dump_location + 'ckptFile%d.bin' %i, safe_location + str(globalmax)])
            call( ['cp', '-f', '--remove-destination', sim_dump_location + 'InferiorOlive_Output%d.txt' %i, safe_location + str(globalmax)]) # Porting Option 1 format

        self.checkpoints.append(globalmax)
        print self.checkpoints

        logging.info("A new DUE checkpoint has been stored for simstep %d", globalmax)
        return True

    def change_cores(self, cores):
        ''' Change the current set of cores'''
        self.hostfd.close()
        self.create_hostfile(cores)
        self.cores = cores
        self.update_cellcount()
        self.num_cores = len(cores)
        logging.info("cores changed to %d", len(cores))

    def rccerun(self, exec_list):
        ''' Spawns an RCCE process '''

        print [rccerun_path] + ['-nue'] + [str(len(self.cores))] + \
                        ['-f'] + [self.hostfile] + exec_list
        self.simulation = Popen( \
                        [rccerun_path] + ['-nue'] + [str(len(self.cores))] + \
                        ['-f'] + [self.hostfile] + exec_list,
                        stderr=STDOUT, stdout=PIPE)
        logging.info("Simulation initialized for %d cores", len(self.cores))

    def determine_countermeasures(self):
        ''' Returns the failed diagnostics' countermeasure procedure with the 
            most expensive TTR
        '''
        #  get the countermeasure procedure for each failed diagnostic
        procedures = [i.countermeasure_procedure() for i in self.diagnostics if i.failed]

        # determine the most expensive countermeasure procedure to follow
        max_cost = 0
        max_proc = procedures[0]
        for individual in procedures:
            cost = countermeasure_enum[individual[0][0].__name__]
            if cost > max_cost:
                max_cost = cost
                max_proc = individual
        return max_proc

    def event_loop(self):
        ''' Depman's main event loop.
            Waits for the simulation to exit, processes failed diagnostics and
            performs the determined countermeasures, if any
        '''
        with self.lock:
            logging.info("waiting for simulation") #verbose
            ret = self.simulation.wait() 
            logging.info("Simulation returned exit code: %d", ret) #verbose
            self.wait_diagnostics()

        # Execution is completed when the simulation is stopped with no failed diagnostics
        failed = self.failed_diagnostics()
        while len(failed) == 0 and any(map(lambda x: not x.completed, self.diagnostics)):
            # wait for incomplete diagnostics
            failed = self.failed_diagnostics()
            sleep(1)

        if len(failed) == 0:
                logging.info("No diagnostics failed, exiting")
                self.completed = True
                return

        # Calculate the TTF if the simulation stopped manually and add it to the previous observed values
        if self.timestamp > 0:
            mttf = self.timestamp - self.failure_timestamp
            self.mttf_values.append(mttf)
            mttf_estimate = sum(self.mttf_values) / float(len(self.mttf_values))
            print "MTTF estimate: " + str(mttf_estimate)
            logging.info("MTTF estimate: " + str(mttf_estimate))

        
        # TODO: adjust checkpoint interval for optimality here
        # TODO: perform distinct SDC and DUE checks

        # Check if a new countermeasure procedure needs to be calculated
        advance = self.new_DUE_checkpoint()
        procedure_failed = len(self.current_counter_proc) == 0
        if (not advance) and len(self.mttr_values) == 0:
            logging.error("No valid checkpoint was created. Simulation cannot be restarted")
            print "No valid checkpoint was found. Simulation cannot be restarted"
            sys.exit(1)
        if (not advance) and procedure_failed and len(self.mttr_values) > 0:
            logging.error("Countermeasure procedure was fully performed and no new checkpoints were created")
            map(lambda x:x.degrade(), failed) # Degrade the simulation state 
        if advance or procedure_failed:
            self.current_counter_proc = self.determine_countermeasures()
            logging.info("New countermeasure procedure determined")

        # Perform the next sequence from the list of countermeasures
        while len(self.current_counter_proc) > 0:
            countermeasures = self.current_counter_proc.pop(0)
            cfailed = False
            for step in countermeasures:
                if not step.perform():
                    cfailed = True
                    break
            if not cfailed:
                break

        self.unset_failed_diagnostics()
        self.stopped = False
        self.reinitialize_diagnostics()

        # Calculate the TTR
        mttr = time() - self.timestamp
        self.mttr_values.append(mttr)
        print "MTTR estimate: " + str(sum(self.mttr_values) / float(len(self.mttr_values))) # DEBUG
        print "Repair Completed" #DEBUG

        # Restart the TTF timer 
        self.failure_timestamp = time()

        # Reinitialize injectors
        if self.fault_injection:
            self.injector.reinit_injectors()

    def stop(self):
        ''' Halt the simulation using a kill script and 
            a SIGKILL on the RCCE process
        '''
        self.timestamp = time()
        self.stopped = True
        if self.fault_injection:
            self.halt_injectors()
        call( [rccerun_path] + ['-nue'] + [str(self.num_cores)] + \
                ['-f'] + [self.hostfile] + [killfoli_path])
        try:
            os.kill(self.simulation.pid, SIGKILL)
            logging.info("Signaled SIGKILL to the simulation") #verbose
        except OSError:
            pass #process already killed through killfoli
        logging.warning("Simulation stopped")

    def failed_diagnostics(self):
        ''' Return a list of the diagnostics that have failed '''
        return [x for x in self.diagnostics if x.failed == True]


def main():
    dm = depman()
    while not dm.completed:
        dm.event_loop()
    print "execution completed"

if __name__=="__main__":
    main()
