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
            logging.error("Timeout exceeded for %s cores", expected)
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

    def perform(self):
        logging.info("performing the Restart Simulation countermeasure")
        print self.manager.checkpoints
        if any(isinstance(x, infoli_diagnostics.infoliOutputDivergence) for x in self.manager.failed_diagnostics()):   #infoli-specific
            # check if the SDC detection diagnostic has failed, and use the SDC checkpoint
            print sorted(self.manager.checkpoints)
            checkpoint = max(self.manager.checkpoints)
        else:
            checkpoint = max(self.manager.checkpoints)

        print "Restarting from step" + str(checkpoint)
        logging.info("Restarting from step " + str(checkpoint))

        with self.manager.lock:
            # Copy safe checkpoints
            for i in range(self.manager.num_cores):
                call( ['cp', '-f', '-u', safe_location + str(checkpoint) + '/ckptFile%d.bin' %i, sim_dump_location])
                call( ['cp', '-f', '-u', safe_location + str(checkpoint) + '/InferiorOlive_Output%d.txt' %i, sim_dump_location]) 
            self.manager.rccerun([self.manager.restart_exec] + self.manager.exec_list[1:])
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
