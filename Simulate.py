###############################################################################
# PyDial: Multi-domain Statistical Spoken Dialogue System Software
###############################################################################
#
# Copyright 2015 - 2019
# Cambridge University Engineering Department Dialogue Systems Group
#
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
###############################################################################

'''
Simulate.py - semantic level user simulator system.
====================================================

Copyright CUED Dialogue Systems Group 2015 - 2017

**Basic Execution**: 
    >>> python Simulate.py [-h] -C CONFIG [-n -r -l -t -g -s]

Optional arguments/flags [default values]::

    -n Number of dialogs [1]
    -r semantic error rate [0]
    -s set random seed 
    -g generate text prompts
    -h help

   
**Relevant Config variables** [Default values]::

    [simulate]
    maxturns = 30 
    continuewhensuccessful = False
    forcenullpositive = False
    confscorer = additive


.. seealso:: CUED Imports/Dependencies: 

    import :mod:`utils.ContextLogger` |.|
    import :mod:`utils.Settings` |.|
    import :mod:`usersimulator.SimulatedUsersManager` |.|
    import :mod:`ontology.FlatOntology` |.|
    import :mod:`Agent` |.|

************************

'''
import os
import random
import copy
import argparse
import Agent
from usersimulator import SimulatedUsersManager
from utils import Settings
from utils import ContextLogger
from ontology import Ontology
logger = ContextLogger.getLogger('')

__author__ = "cued_dialogue_systems_group"
__version__ = Settings.__version__

class SimulationSystem(object):
    '''
    Semantic level simulated dialog system
    '''
    def __init__(self, error_rate):
        '''
        :param error_rate: error rate of the simulated environment
        :type error_rate: float
        '''
        # Dialogue Agent Factory:
        #-----------------------------------------
        self.agent_factory = Agent.AgentFactory(hub_id='simulate')
        # NOTE - using agent factory here rather than just an agent - since for simulate I can easily envisage wanting to 
        # have multiple agents and looking at combining their policies etc... This is not being used now though; will just use
        # a single agent in here at present. 
        
        
        # Simulated User.
        #-----------------------------------------
        self.simulator = SimulatedUsersManager.SimulatedUsersManager(error_rate)
        self.traceDialog = 2
        self.sim_level = 'dial_act'
        self.text_sampling = 'dict'

        if Settings.config.has_option("GENERAL", "tracedialog"):
            self.traceDialog = Settings.config.getint("GENERAL", "tracedialog")
        if Settings.config.has_option("usermodel", "simlevel"):
            self.sim_level = Settings.config.get("usermodel", "simlevel")
        if Settings.config.has_option("usermodel", "textsampling"):
            self.text_sampling = Settings.config.get("usermodel", "textsampling")
        if self.sim_level == 'text':
            #Load the text generator
            if self.text_sampling == 'dict':
                sampling_dict = os.path.join(Settings.root, 'usersimulator/textgenerator/textgen_dict.pkl')
            else:
                sampling_dict = None
            import usersimulator.textgenerator.textgen_toolkit.SCTranslate as SCT
            self.SCT = SCT.SCTranslate(sampling_dict=sampling_dict)
        elif self.sim_level == 'sys2text':
            pass #load here florians model
            
        self.semi_supervised = False
        if Settings.config.has_option("exec_config","supervised"):
            self.semi_supervised = Settings.config.getboolean("exec_config","supervised")
            if self.semi_supervised:
                if Settings.config.has_option("exec_config","numsuperviseddialogs"):
                    self.num_supervised_dialogs = max(0, Settings.config.getint("exec_config","numsuperviseddialogs"))
                if Settings.config.has_option("exec_config","trainingfile"):
                    self.training_file = Settings.config.get("exec_config","trainingfile")
                    self.executed_dialogs = []
                else:
                    self.semi_supervised = False

    def read_file(self, training_file):

        with open(training_file, "r") as f:
            dialogs_data = f.read().split("##")[1:]

        dialogs = {}

        for dialog in dialogs_data:
            user_turns = {}
            u_turn = 0
            in_user = False
            agent_turns = {}
            a_turn = 0
            in_agent = False
            dialog_name = dialog.split("\n")[0].strip()
            for line in dialog.split("\n")[1:]:
                if line.startswith("USER: "):
                    if in_agent:
                        a_turn += 1
                    in_agent = False
                    in_user = True
                    if u_turn not in user_turns:
                        user_turns[u_turn] = []
                    user_turns[u_turn].append(line.split("USER: ")[1])
                elif line.startswith("AGENT: "):
                    if in_user:
                        u_turn += 1
                    in_agent = True
                    in_user = False
                    if a_turn not in agent_turns:
                        agent_turns[a_turn] = []
                    agent_turns[a_turn].append(line.split("AGENT: ")[1])

            dialogs[dialog_name] = {}
            dialogs[dialog_name]["USER"] = user_turns
            dialogs[dialog_name]["AGENT"] = agent_turns

        return dialogs

    def get_training_dialog(self, dialogs):

        if not self.executed_dialogs:
            self.executed_dialogs = []

        keys = list(dialogs.keys())

        key = random.choice(keys)
        if len(self.executed_dialogs) < len(keys):
            while key in self.executed_dialogs:
                key = random.choice(keys)
            self.executed_dialogs.append(key)
        else:
            self.executed_dialogs = []
        
        return key, copy.deepcopy(dialogs[key])

    def run_dialogs(self, numDialogs):
        '''
        run a loop over the run() method for the given number of dialogues.
        
        :param numDialogs: number of dialogues to loop over.
        :type numDialogs: int
        :return: None
        '''
        if self.semi_supervised:
            self.dialogs = self.read_file(self.training_file)
            self.num_supervised_dialogs = min(numDialogs, self.num_supervised_dialogs)
            self.count_supervised = 0

        for i in range(numDialogs):
            logger.info('Dialogue %d' % (i+1))
            # print i
            if self.semi_supervised and i%(numDialogs//self.num_supervised_dialogs) == 0:
                logger.dial("**SUPERVISED**")
                self.run(session_id='simulate_dialog'+str(i), sim_level=self.sim_level, supervised=True)
                self.count_supervised += 1
                if self.count_supervised == self.num_supervised_dialogs:
                    self.semi_supervised = False
            else:        
                self.run(session_id='simulate_dialog'+str(i), sim_level=self.sim_level, supervised=False)
 
        self.agent_factory.power_down_factory() # Important! -uses FORCE_SAVE on policy- which will finalise learning and save policy.
       
    def run(self, session_id, agent_id='Smith', sim_level='dial_act', supervised=False):
        '''
        Runs one episode through the simulator
        
        :param session_id: session id
        :type session_id: int
        :param agent_id: agent id, default = 'Smith'
        :type agent_id: string
        :return: None
        '''
        if supervised:
            dialog_name, training_dialog = self.get_training_dialog(self.dialogs)
            logger.dial("Dialog name: "+dialog_name)

        # RESET THE USER SIMULATOR:
        self.simulator.restart()
        for domain in self.simulator.simUserManagers:
            if self.simulator.simUserManagers[domain] and self.sim_level != 'sys2text':
                if not supervised:
                    self.simulator.simUserManagers[domain].um.hdcSim.set_mode('simulator')
                    goal = self.simulator.simUserManagers[domain].um.goal
                    logger.dial('User will execute the following goal: {}'
                                .format(str(goal.request_type) + str(goal.constraints) + str([req for req in goal.requests])))
                else:
                    self.simulator.simUserManagers[domain].um.hdcSim.set_mode('dialog_file')
                    self.simulator.simUserManagers[domain].um.hdcSim.set_dialog(training_dialog['USER'])
        user_act = ''
        
        endingDialogue = False

        # SYSTEM STARTS THE CALL:
        sys_act = self.agent_factory.agents[agent_id].start_call(session_id,
                                                                   domainSimulatedUsers=self.simulator.simUserManagers,
                                                                   maxNumTurnsScaling=self.simulator.number_domains_this_dialog)
        prompt_str = sys_act.prompt

        if prompt_str is not None:      # if we are generating text, versus remaining only at semantic level.
            if self.traceDialog > 1: print ' Prompt >', prompt_str
            logger.info('| Prompt > '+ prompt_str)
        
        turn = 0
        # LOOP OVER TURNS:
        while not endingDialogue:
            
            # USER ACT:  
            #-------------------------------------------------------------------------------------------------------------
            sys_act = self.agent_factory.agents[agent_id].retrieve_last_sys_act()
            if sim_level == 'sys2text':
                text_user_act, user_actsDomain, _ = self.simulator.act_on(sys_act)
                #user_actsDomain = 'CamRestaurants'
                hyps = [(text_user_act, 1.0)]
            else:
                user_act, user_actsDomain, hyps = self.simulator.act_on(sys_act)    #REQUEST(intent), Banks_1, [REQUEST(intent)]
                
                if sim_level == 'text':
                    #todo: convert dialact to text
                    #text_user_act = raw_input('Translate user act: {} > '.format(user_act))
                    text_user_act = self.SCT.translateUserAct(str(user_act),1)[2]
                    try:
                        text_user_act = text_user_act[0]
                    except:
                        logger.error('Wrong user act: ' + user_act, text_user_act)
                    hyps = [(text_user_act, 1.0)]


            #actually also output user_actsDomain (the TRUE DOMAIN) here too - which can be used to avoid doing topic tracking  
            # print "TURN: ", self.agent_factory.agents[agent_id].currentTurn
            # print sys_act
            # print user_act
            if self.traceDialog>1:
                print '   User >', user_act
            if self.sim_level != 'sys2text':
                if type(user_act) == list:
                    logger.dial('| User > ' + str(user_act))
                else:
                    logger.dial('| User > ' + user_act.to_string())
            else:
                logger.dial('| User > ' + text_user_act)
                
            # SYSTEM ACT:
            #-------------------------------------------------------------------------------------------------------------
            if supervised:
                if turn in training_dialog['AGENT']:
                    real_sys_act = training_dialog['AGENT'][turn]
                else:
                    real_sys_act = None
            else:
                real_sys_act = None

            sys_act = self.agent_factory.agents[agent_id].continue_call(asr_info = hyps, 
                                                                          domainString=user_actsDomain,
                                                                          domainSimulatedUsers=self.simulator.simUserManagers,
                                                                          supervised=supervised,
                                                                          real_sys_act=real_sys_act)
            prompt_str = sys_act.prompt
            if prompt_str is not None:      # if we are generating text, versus remaining only at semantic level.
                if self.traceDialog>1: print '   Prompt >', prompt_str
                logger.info('| Prompt > ' + prompt_str)

            if self.sim_level != 'sys2text':
                if type(user_act) == list:
                    for a in user_act:
                        if 'bye' == a.act or 'GOODBYE' == a.act or 'bye' == sys_act.act:
                            endingDialogue = True    
                else:
                    if 'bye' == user_act.act or 'bye' == sys_act.act:
                        endingDialogue = True
            else:
                if 'bye' in text_user_act or 'bye' == sys_act.act:
                    endingDialogue = True

            turn += 1
            
        # Process ends.
        for domain in self.simulator.simUserManagers:
            if self.simulator.simUserManagers[domain]:
                if self.sim_level != 'sys2text':
                    goal = self.simulator.simUserManagers[domain].um.goal
                    logger.dial('User goal at the end of the dialogue: {}'
                                .format(str(goal.request_type) + str(goal.constraints) + str([req for req in goal.requests])))
        self.agent_factory.agents[agent_id].end_call(domainSimulatedUsers=self.simulator.simUserManagers)

        return

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Simulate')
    parser.add_argument('-C', '-c', '--config', help='set config file', required=True, type=argparse.FileType('r'))
    parser.add_argument('-n', '--number', help='set the number of dialogues', type=int)
    parser.add_argument('-r', '--error', help='set error rate', type=int)
    parser.set_defaults(use_color=True)
    parser.add_argument('--nocolor', dest='use_color',action='store_false', help='no color in logging. best to\
                        turn off if dumping to file. Will be overriden by [logging] config setting of "usecolor=".')
    parser.add_argument('-s', '--seed', help='set random seed', type=int)
    args = parser.parse_args()
    if args.error is None:
        args.error = 0      # default simulated error rate
    if args.number is None:
        args.number = 1     # default number of dialogs

    seed = Settings.init(config_file=args.config.name,seed=args.seed)
    ContextLogger.createLoggingHandlers(config=Settings.config, use_color=args.use_color)
    logger.info("Random Seed is {}".format(seed))
    Ontology.init_global_ontology()

    simulator = SimulationSystem(error_rate=float(args.error)/100)
    simulator.run_dialogs(args.number)


#END OF FILE
