import abc
import logging
from threading import Thread, Lock
from subprocess import call
from random import randrange, random
from time import sleep, time
from config import *
from math import exp


class injector(object):
    # injectors must have a filename attribute
    __metaclass__= abc.ABCMeta
    disabled = False

    def __init__(self, diagnostic):
        self.diagnostic = diagnostic
        self.f = open(self.filename, 'r')
        self.timestamp = time()
        self.probability = 0

    @abc.abstractmethod
    def inject(self):
        return

    def new_timestamp(self):
        ''' replace the old timestamp - used to to avoid high probabilities after restart'''
        self.timestamp = time()

    def update(self):
        ''' update the injector's probability for the next timestep '''
        timestamp = time()
        while True:
            try:
                self.mttf = int(self.f.readline())
                deltat = timestamp - self.timestamp
                self.probability = 1 - exp(-(deltat/self.mttf)) # TODO: parameterize for different TTF distributions
                break
            except ValueError: # raised by empty line, EOF or error
                self.f.seek(0)  # start from the top of the file
            except ZeroDivisionError:
                self.diagnostic.manager.halt_injectors()
                logging.error("Zero TTF specified on file %s, injectors halted" \
                        + self.filename)
                break
        self.timestamp = timestamp


class injectorManager(object):
    ''' The injector manager spawns a thread from a list of diagnostics that 
        manages a set of injectors, calculating and evaluating their probabilities
    '''
    def __init__(self, diagnostics):
        self.injectors = []
        self.halt = False
        for i in diagnostics:
            self.injectors += i.injectors
        self.min_Deltat = 0 # The minimum interval between probability evaluations
        self._spawn_injector_processor()

    def _spawn_injector_processor(self):
        self.t = Thread(target=self.process_injectors)
        self.t.daemon = True
        self.t.start()

    def reinit_injectors(self):
        ''' Spawn a new injector manager thread '''
        sleep(3) # TODO: give some time for the simulation to checkpoint
        self.halt = False
        map(lambda x:x.new_timestamp(), self.injectors) 
        self._spawn_injector_processor()

    def process_injectors(self):
        while True:
            if self.halt:
                break

            map(lambda x:x.update(), self.injectors)
            sleep(self.min_Deltat)
            for i in self.injectors:
                rand = random()
                #print "rand: " + str(rand) + " probab: " + str(i.probability)
                if rand < i.probability and not i.disabled:
                    print "Injecting " + i.__class__.__name__
                    logging.info("Injecting " + i.__class__.__name__)
                    i.inject()
                    break
        self.halt = False


class processExitInjector(injector):
    ''' Injects an RCCE process exit failure '''
    filename = processExitInjectorFile

    def inject(self):
        print "Injecting stdout error"
        failine = "[0] FAILURE:  inject @ rckINJ w 12 "
        self.diagnostic.process_line(failine)


class infoliInjector(injector):
    ''' Injects an SDC of one bit flip on an infoli output file '''
    filename = infoliInjectorFile

    def inject(self):
        reader = randrange(len(self.diagnostic.readers))
        self.diagnostic.readers[reader].injectSDC()

class coreShutdownInjector(injector):
    filename = coreShutdownInjectorFile

    def inject(self):
        # shut down one core at random by pulling the release
        core = randrange(len(self.diagnostic.manager.cores))
        if devel:
            ex = 'echo'
        else:
            ex = 'sccReset'
        call( [ex , '-p', ' '.join(self.diagnostic.manager.cores[core][3:])])
        #call( ['echo' , '-p', self.diagnostic.manager.cores[core][3:]])
        self.diagnostic.fail()


class coreFailureInjector(injector):
    filename = coreFailureInjectorFile

    def inject(self):
        # consider one core as permanently failed
        self.disabled = True
        core = randrange(len(self.diagnostic.manager.cores))
        core = self.diagnostic.manager.cores[core]
        self.diagnostic.perm_unreachables.append(core)
        self.diagnostic.fail()
