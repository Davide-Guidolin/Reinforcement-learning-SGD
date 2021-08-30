
from numpy.lib.type_check import real
import Agent
from usersimulator import SimulatedUsersManager
from utils import DiaAct, Settings, ContextLogger
from usersimulator.myUserSim.dialogUtils import Action
import json

import os

logger = ContextLogger.getLogger('')

class ActionEvaluator:

    def __init__(self, error_rate):
        # Dialogue Agent Factory:
        #-----------------------------------------
        self.agent_factory = Agent.AgentFactory(hub_id='simulate')
     
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

        self.dialogs = None

        self.correct = 0
        self.wrong = 0
        self.action_scores = {}
    
    def run_eval(self, test_file):
       
        self.dialogs = self.read_file(test_file)

        for i in range(len(self.dialogs)):
            dialog_name = list(self.dialogs.keys())[i]
            #print "Dialog {}/{}      \r".format(i, len(self.dialogs)),
            dialog = self.dialogs[dialog_name]
            logger.info('Dialogue %s' % (dialog_name))
            self.run(session_id='simulate_dialog'+str(i), dialog=dialog, sim_level=self.sim_level)
 
        self.agent_factory.power_down_factory()

        self.calc_results()
        self.print_results()
        #print json.dumps(self.action_scores, indent=4)

    def run(self, session_id, dialog, agent_id='Smith', sim_level='dial_act'):
        '''
        Runs one episode through the simulator
        
        :param session_id: session id
        :type session_id: int
        :param agent_id: agent id, default = 'Smith'
        :type agent_id: string
        :return: None
        '''
        
        # RESET THE USER SIMULATOR:
        self.simulator.restart()
        for domain in self.simulator.simUserManagers:
            if self.simulator.simUserManagers[domain]:
                self.simulator.simUserManagers[domain].um.hdcSim.set_mode('dialog_file')
                self.simulator.simUserManagers[domain].um.hdcSim.set_dialog(dialog['USER'])
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
                logger.dial('| User > ' + str(user_act))
            else:
                logger.dial('| User > ' + text_user_act)
                
            #print "| User > " + str(user_act)
            # SYSTEM ACT:
            #-------------------------------------------------------------------------------------------------------------
            
            sys_act = self.agent_factory.agents[agent_id].continue_call(asr_info = hyps, 
                                                                          domainString=user_actsDomain,
                                                                          domainSimulatedUsers=self.simulator.simUserManagers)
            
            if turn in dialog["AGENT"]:
                logger.dial('| Real Sys > ' + str(dialog["AGENT"][turn]))
            #print "| Sys >" + sys_act.to_string()
            prompt_str = sys_act.prompt
            if prompt_str is not None:      # if we are generating text, versus remaining only at semantic level.
                if self.traceDialog>1: print '   Prompt >', prompt_str
                logger.info('| Prompt > ' + prompt_str)

            if self.sim_level != 'sys2text':
                for a in user_act:
                    if 'GOODBYE' == a.act or 'bye' == sys_act.act:
                        endingDialogue = True
            else:
                if 'bye' in text_user_act or 'bye' == sys_act.act:
                    endingDialogue = True
            
            self.evaluate_turn(sys_act, turn, dialog["AGENT"])
            turn += 1

        self.agent_factory.agents[agent_id].end_call(domainSimulatedUsers=self.simulator.simUserManagers)
        
        return

    def evaluate_turn(self, sys_act, turn, test_dialog):

        original_agent_act = sys_act.act
        if sys_act.items:
            original_slots = [item.slot for item in sys_act.items]
        else:
            original_slots = [None]
        
        # if sys_act.items:                   #INFORM(city=ny, time=11) -> INFORM(city), INFORM(time)
        #     for item in sys_act.items:
        #         agent_slot_name = item.slot
        #         agent_acts.append((agent_act, agent_slot_name))
        # else:
        #     agent_slot_name = None
        #     agent_acts.append((agent_act, agent_slot_name))

        test_acts = []
        if turn in test_dialog:
            for action in test_dialog[turn]:
                real_act = action.split("(")[0].lower()
                real_slot_name = action.split("(")[1].split(")")[0]
                if real_act != "request":
                    if "=" in real_slot_name:
                        real_slot_name = real_slot_name.split("=")[0]
                    else:
                        real_slot_name = None

                if real_act in ["notify_success","notify_failure"]:
                    real_act = "notify"
                elif real_act == 'goodbye':
                    real_act = 'bye'
                elif real_act == 'req_more':
                    real_act = 'reqmore'
                elif real_act == 'offer_intent':
                    real_act = 'offer'
                    real_slot_name = 'intent'

                test_acts.append((real_act, real_slot_name))
        

        for act,slot in test_acts:
            if act not in self.action_scores:
                self.action_scores[act] = {}
                self.action_scores[act]["TP"] = 0
                self.action_scores[act]["FP"] = 0
                self.action_scores[act]["FN"] = 0
                self.action_scores[act]["slots"] = {}
            if slot not in self.action_scores[act]["slots"]:
                self.action_scores[act]["slots"][slot] = {}
                self.action_scores[act]["slots"][slot]["TP"] = 0
                self.action_scores[act]["slots"][slot]["FP"] = 0
                self.action_scores[act]["slots"][slot]["FN"] = 0
        
        if original_agent_act not in self.action_scores:
            self.action_scores[original_agent_act] = {}
            self.action_scores[original_agent_act]["TP"] = 0
            self.action_scores[original_agent_act]["FP"] = 0
            self.action_scores[original_agent_act]["FN"] = 0
            self.action_scores[original_agent_act]["slots"] = {}
        for slot in original_slots:
            if slot not in self.action_scores[original_agent_act]["slots"]:
                self.action_scores[original_agent_act]["slots"][slot] = {}
                self.action_scores[original_agent_act]["slots"][slot]["TP"] = 0
                self.action_scores[original_agent_act]["slots"][slot]["FP"] = 0
                self.action_scores[original_agent_act]["slots"][slot]["FN"] = 0
        
        #print agent_acts, test_acts
        action_correct = False
        slot_correct = False
        for test_act in test_acts:
            if original_agent_act == test_act[0]:
                action_correct = True
                if test_act[1] in original_slots:
                    slot_correct = True
                    correct_slot = test_act[1]

        # for agent_act in agent_acts:
        #     action_correct = False
        #     slot_correct = False
        #     for test_act in test_acts:
        #         if agent_act[0] == test_act[0]:
        #             action_correct = True
        #             if agent_act[1] == test_act[1]:
        #                 slot_correct = True

        if action_correct:
            self.action_scores[original_agent_act]["TP"] += 1
            self.correct += 1
            if slot_correct:
                self.action_scores[original_agent_act]["slots"][correct_slot]["TP"] += 1
            else:
                for slot in original_slots:
                    self.action_scores[original_agent_act]["slots"][slot]["FP"] += 1
                for act,slot in test_acts:
                    self.action_scores[act]["slots"][slot]["FN"] += 1
        else:
            self.wrong += 1
            self.action_scores[original_agent_act]["FP"] += 1
            for slot in original_slots:
                self.action_scores[original_agent_act]["slots"][slot]["FP"] += 1
            for act,slot in test_acts:
                self.action_scores[act]["FN"] += 1
                self.action_scores[act]["slots"][slot]["FN"] += 1


        
        #action_scores

    def calc_results(self):
        self.slot_scores = {}
        for action in self.action_scores:
            if self.action_scores[action]["FP"] != 0 or self.action_scores[action]["TP"] != 0:
                precision = round(float(self.action_scores[action]["TP"])/(self.action_scores[action]["TP"]+self.action_scores[action]["FP"]), 2)
            else:
                precision = 0

            if self.action_scores[action]["FN"] != 0 or self.action_scores[action]["TP"]:
                recall = round(float(self.action_scores[action]["TP"])/(self.action_scores[action]["TP"]+self.action_scores[action]["FN"]), 2)
            else:
                recall = 0

            self.action_scores[action]["precision"] = precision
            self.action_scores[action]["recall"] = recall

            for slot in self.action_scores[action]["slots"]:
                if self.action_scores[action]["slots"][slot]["FP"] != 0 or self.action_scores[action]["slots"][slot]["TP"] != 0:
                    precision = round(float(self.action_scores[action]["slots"][slot]["TP"])/(self.action_scores[action]["slots"][slot]["TP"]+self.action_scores[action]["slots"][slot]["FP"]), 2)
                else:
                    precision = 0

                if self.action_scores[action]["slots"][slot]["FN"] != 0 or self.action_scores[action]["slots"][slot]["TP"]:
                    recall = round(float(self.action_scores[action]["slots"][slot]["TP"])/(self.action_scores[action]["slots"][slot]["TP"]+self.action_scores[action]["slots"][slot]["FN"]), 2)
                else:
                    recall = 0
                
                if slot not in self.slot_scores:
                    self.slot_scores[slot] = {}
                
                if action not in self.slot_scores[slot]:
                    self.slot_scores[slot][action] = {}
                

                self.slot_scores[slot][action]["precision"] = precision
                self.slot_scores[slot][action]["recall"] = recall


    def print_results(self):
        print "\nCORRECT ACTIONS: ", self.correct, "\nWRONG ACTIONS: ", self.wrong, "\nAccuracy: ", round(float(self.correct)/(self.wrong+self.correct),2)
        #print json.dumps(self.action_scores, indent=4)

        print "\n"
        print "="*15,"ACTIONS","="*15
        print """+----------------+-----------+--------+
|     ACTION     | PRECISION | RECALL |
+----------------+-----------+--------+"""
        for act in self.action_scores:
            print "|{:^16}|{:^11.2f}|{:^8.2f}|".format(act, self.action_scores[act]["precision"], self.action_scores[act]["recall"])
            print "+----------------+-----------+--------+"

        print "\n"
        print "="*16,"SLOTS","="*16
        for slot in self.slot_scores:
            print slot,":"
            print """+----------------+-----------+--------+
|     ACTION     | PRECISION | RECALL |
+----------------+-----------+--------+"""
            for act in self.slot_scores[slot]:
                print "|{:^16}|{:^11.2f}|{:^8.2f}|".format(act, self.slot_scores[slot][act]["precision"], self.slot_scores[slot][act]["recall"])
                print "+----------------+-----------+--------+"

    def read_file(self, test_file):

        with open(test_file, "r") as f:
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
