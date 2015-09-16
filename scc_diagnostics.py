import logging
import abc
import sys
from threading import Lock
from monitors import monitor, checkpointMonitor, corePinger, fileReader, lineProcessor
from injectors import processExitInjector, coreShutdownInjector, coreFailureInjector, benchmarkInjector
from core_allocator import allocate_tasks


""" Diagnostics Interface """
class diagnostic(object):
    __metaclass__ = abc.ABCMeta
    #diagnostics must have an injectors list if fault injection will be used
    # if a diagnostic does not implement a monitor object, it should have a wait method

    def __init__(self):
        self.failed = False
        self.lock = Lock()

    def fail(self):
        with self.lock:
            if not self.failed:
                logging.error("%s diagnostic failed", self.__class__.__name__)
                self.failed = True
            if not self.manager.stopped:
                self.manager.stop()

    def reinit(self):
        self.failed = False
        self.reinitialize()

    def degrade(self):
        pass

    def completed(self):
        return True

    @abc.abstractmethod
    def reinitialize(self):
        return

    @abc.abstractmethod
    def countermeasure_procedure(self):
        return

class benchmark(diagnostic):
    def __init__(self, manager):
        self.manager = manager
        self.injectors = [benchmarkInjector(self)]
        diagnostic.__init__(self)

    def wait(self):
        pass

    def reinitialize(self):
        pass

    def countermeasure_procedure(self):
        from scc_countermeasures import restartSimulation
        return [[restartSimulation(self.manager)]]

class processExit(checkpointMonitor, diagnostic):
    def __init__(self, manager):
        self.manager = manager
        checkpointMonitor.__init__(self, self.manager)
        diagnostic.__init__(self)
        self.injectors = [processExitInjector(self)]

    def process_line(self, line):
            """ Checks for SCC FAILURE messages in the app's stdout.
                Returns true if the stdout line does not cause the diagnostic to fail
            """
            checkpointMonitor.process_line(line)
            if line.find("FAILURE") != 1:
                core = line[23:29]  # core number
                if line[-12:-1] == "Interrupted": # ignore "Interrupted" messages
                    return True
                try:
                    error = int(line[-4:-1])
                except ValueError:
                    """ Ignore non-SCC messsages"""
                    return True

                if error != 255:
                    # ignore error code 255, as it occurs during manual killing of the process
                    logging.error('Core %s: Process failed with error value %d', core, error)
                    self.fail()
                    return False
            return True

    def reinitialize(self):
        self.switch_process(self.manager.simulation)

    def countermeasure_procedure(self):
        from scc_countermeasures import restartSimulation, coreReboot, platformReinitialization
        return [[restartSimulation(self.manager)],
                [coreReboot(self.manager.initial_cores, self.manager.initial_cores), \
                    restartSimulation(self.manager)],\
                [platformReinitialization(self.manager.initial_cores), \
                    restartSimulation(self.manager)]]


class coreReachability(corePinger, diagnostic):
    def __init__(self, manager, num_threads):
        self.manager = manager
        corePinger.__init__(self, num_threads, self.manager.cores)
        diagnostic.__init__(self)
        self.injectors = [coreShutdownInjector(self), coreFailureInjector(self)]

    def handle_unreachables(self):
        if len([core for core in self.unreachables if core in self.manager.cores]) > 0:
            print "unreachable cores:" #DEBUG
            print self.unreachables
            logging.error('%d cores are not responding', len(self.unreachables))
            self.fail()
            return False
        return True

    def reinitialize(self):
        self.switch_cores(self.manager.cores)

    def degrade(self):
        ''' Scratch the failing cores and use a thermal-aware placement of the subset of cores.
        It is assumed that the simulator began with a divisor of 48 as the number of cores
        '''
        max_cores = self.manager.initial_cores
        self.manager.initial_cores = [x for x in max_cores if x not in self.unreachables] # scratch out unusable cores
        
        # TODO: infoli-specific
        infoli_core_numbers = reversed([2,3,4,6,8,12,16,24])
        new_tasks = 1
        for i in infoli_core_numbers:
            if len(self.manager.initial_cores) >= i:
                new_tasks = i
                break

        self.manager.change_cores(allocate_tasks(new_tasks, self.manager.initial_cores))
        logging.info("Reducing number of cores to %d", new_tasks)

    def fail(self):
        with self.lock:
            if not self.failed:
                logging.error("%s diagnostic failed", self.__class__.__name__)
                self.failed = True
            if not self.manager.stopped:
                prev_cores = self.manager.cores
                new_cores = [x for x in prev_cores if x not in self.unreachables]
                self.manager.change_cores(new_cores)
                self.manager.stop()
                self.manager.change_cores(prev_cores)

    def countermeasure_procedure(self):
        from scc_countermeasures import restartSimulation, coreReboot, platformReinitialization
        return [[coreReboot(self.unreachables, self.manager.initial_cores), restartSimulation(self.manager)], \
                [platformReinitialization(self.manager.cores), restartSimulation(self.manager)]]

