import abc
import logging
from time import sleep, time
from subprocess import call, check_output
from monitors import corePinger
from config import sim_dump_location, safe_location, devel
import infoli_diagnostics

class countermeasure(object):
    ''' Countermeasure class '''
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def perform(self):
        return


''' defines an ordering among the different countermeasures, based on MTTR '''
countermeasure_enum = {
    'restartSimulation':0,
    'coreReboot':1,
    'platformReinitialization':2
}


def wait_for_cores(core_names, timeout):
    ''' Utility function that blocks until a set of cores is available 
        or until the timeout is reached
    '''
    if devel:
        return True

    t0 = time()
    available_cores = 0

    while available_cores < len(core_names):
        status = check_output(['sccBoot', '-s'])

        if status[-11:-8] == "All":
            available_cores = 48
        elif status[-10:-8] == "No":
            available_cores = 0
        else:
            available_cores = int(status[-10:-8])

        if time() - t0 > timeout:
            logging.error("Boot Timeout exceeded for %s cores", len(core_names))
            return False
    sleep(10)
    status = check_output(['sccBoot', '-s'])
    print status
    return True


def boot_linux():
    ''' Utility function that boots linux on all cores '''

    logging.info("Booting linux on all cores")
    if devel:
        ret = call(['echo', '-l'])
    else:
        ret = call(['sccBoot', '-l'])
    if ret != 0:
        logging.warning("sccBoot returned %d during boot_linux", ret)
        return False
    return True


class restartSimulation(countermeasure):
    """ Restarts the simulation """
    __name__ = 'restartSimulation'

    def __init__(self, manager):
        self.manager = manager

    def delete_checkpoint(self, step):
        call(['rm', '-rf', safe_location + str(step)])
        print "Discarding checkpoint at step " + str(step)
        logging.info("Discarding checkpoints at step " + str(step))

    def perform(self):
        self.manager.restarted = True

        logging.info("performing the Restart Simulation countermeasure") #DEBUG
        self.manager.checkpoints = sorted(self.manager.checkpoints) 
        print self.manager.checkpoints
        #TODO: min_step is infoli-specific
        while len(self.manager.checkpoints) >= 2 and \
                    self.manager.checkpoints[1] < self.manager.min_step:    
            self.delete_checkpoint(self.manager.checkpoints.pop(0))

        # infoli-specific: check if the SDC detection diagnostic has failed
        if any(isinstance(x, infoli_diagnostics.infoliOutputDivergence) for x \
                   in self.manager.failed_diagnostics()):   
            checkpoint = self.manager.checkpoints[0]
            for step in sorted(self.manager.checkpoints)[1:]:
                self.delete_checkpoint(step)
            self.manager.checkpoints = [self.manager.checkpoints[0]]

            if checkpoint > self.manager.min_step:
                #FUTURE-TODO: eradicate this case
                logging.warning("Could not locate a checkpoint before the SDC detector. The file should be rechecked")
        else:
            checkpoint = max(self.manager.checkpoints)

        print "Restarting from simulation step " + str(checkpoint)
        logging.info("Restarting from simulation step " + str(checkpoint))

        with self.manager.lock:
            # Copy safe checkpoints
            for i in range(self.manager.num_cores):
                call( ['cp', '-f', '-u', safe_location + str(checkpoint) + '/ckptFile%d.bin' %i, sim_dump_location])
                call( ['cp', '-f', '-u', safe_location + str(checkpoint) + '/InferiorOlive_Output%d.txt' %i, sim_dump_location]) 
            self.manager.rccerun([self.manager.restart_exec] + self.manager.exec_list[1:], False)   # use False to avoid piping stdout for diagnostics - useful for measurements
        logging.info("Restart Simulation countermeasure completed")
        return True


class coreReboot(countermeasure):
    """ Reboots a list of cores """
    __name__ = 'coreReboot'

    def __init__(self, reboot_cores, all_cores):
        self.core_names = reboot_cores
        self.cores = map(lambda x : x[3:], reboot_cores) # strip the 'rck' prefix
        self.all_cores = all_cores

    def perform(self):
        if devel:
            ex = 'echo'
        else:
            ex = 'sccReset'
        logging.info("Core Reboot countermeasure started for %d cores", len(self.cores))
        call( [ex] + ['-p'] + self.cores)  # Are both -p and -r needed?
        call( [ex] + ['-r'] + self.cores)
        if not boot_linux():
            return False
        logging.info("Waiting for response from %d cores", len(self.all_cores))
        if not wait_for_cores(self.all_cores, 180):
            return False
        logging.info("Core Reboot countermeasure completed")
        return True


class platformReinitialization(countermeasure):
    """ Reinitializes the SCC board """
    __name__ = 'platformReinitialization'

    def __init__(self, expected_cores):
        self.expected_cores = expected_cores

    def perform(self):
        logging.info("Reinitializing the SCC board")
        if devel:
            ret = call(['echo', '-i', 'Tile533_Mesh800_DDR800']) #devel
        else:
            ret = call(['sccBmc', '-i', 'Tile533_Mesh800_DDR800']) #SCC
        if ret != 0:
            logging.warning("sccBmc returned exit code %d during platform reinitialization", ret)
            return False
        if not boot_linux():
            return False
        logging.info("Waiting for response from %d cores", len(self.expected_cores))
        if not wait_for_cores(self.expected_cores, 180):
            return False

        logging.info("Platform Reinitialization countermeasure completed")
        return True
