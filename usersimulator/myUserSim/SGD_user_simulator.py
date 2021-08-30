from .dialogUtils import DialogStatus, Action, DialogGoal
import random
import numpy as np
import copy
from .. import UMSimulator
from .. import UserModel
from utils import DiaAct, ContextLogger

logger = ContextLogger.getLogger('')

class SGDUserSimulator(UMSimulator.UMSimulator):

    def __init__(self, dstring, change_goal_prob=0.05, add_slot_prob=0.15, user_cooperation=1):
        super(SGDUserSimulator, self).__init__(dstring)
        self.dialog_status = DialogStatus.NOT_STARTED
        self.dstring = dstring
        self.agenda = UserModel.UMAgenda(self.dstring)
        self.goal = None
        self.informed_intents = []
        self.informed_slots = {}
        self.executed_agent_actions = []
        #self.already_executed_goals = []
        self.change_goal_prob = change_goal_prob
        self.add_slot_prob = add_slot_prob
        self.user_cooperation = user_cooperation
        self.in_offer = False
        self.offer_slots = {}
        self.current_intent = None
        self.finished_intents = []
        self.last_user_action = None
        self.last_agent_action = None
        self.mode = "simulator"
        self.dialog = None
        self.turn = 0
        self.yaml_goal = None
        self.max_patience = 0

    def reset(self):
        self.dialog_status = DialogStatus.NOT_STARTED
        self.goal = None
        del self.yaml_goal
        self.yaml_goal = None
        self.informed_intents = []    
        del self.informed_slots    
        self.informed_slots = {}
        self.executed_agent_actions = []
        #self.already_executed_goals = []
        self.in_offer = False
        del self.offer_slots
        self.offer_slots = {}
        self.current_intent = None
        self.finished_intents = []
        self.last_user_action = None
        self.last_agent_action = None
        self.max_patience = 0
        self.turn = 0
        if self.dialog:
            del self.dialog
            self.dialog = None

    def set_mode(self, mode):
        if mode in ["simulator", "dialog_file"]:
            self.mode = mode

    def set_dialog(self, dialog):
        self.dialog = dialog

    def init(self, goal, um_patience):
        '''
        Initializes the simulator. 
        
        This method is automatically invoked by the init method of the user model.
        
        It needs to be implemented in a sub-class.
        
        :param goal: the user goal
        :type goal: UMGoal
        :param um_patience: the max patience for this simulation run.
        :type um_patience: int'''
        self.reset()
        self.max_patience = um_patience
        # print "Patience: ",um_patience
        # print "Agenda: ", self.agenda.agenda_items
        self.yaml_goal = DialogGoal(goal.yaml_goal['goals'], goal.yaml_goal['inform_slots'], goal.yaml_goal['request_slots'])

        self.goal = goal
        old_dict = copy.deepcopy(self.yaml_goal.request_slots)
        for intent in old_dict:
            for slot in old_dict[intent]:
                if slot not in self.goal.requests:
                    del self.yaml_goal.request_slots[intent][slot]

    def receive(self, sys_act, goal):
        '''
        This method processes the new input system act and updates the agenda.
        
        It needs to be implemented in a sub-class.
        
        :param sys_act: the max patience for this simulation run.
        :type sys_act: :class:`DiaAct.DiaAct`
        :param goal: the user goal
        :type goal: :class:`UserModel.UMGoal`
        '''
        #print "Sys Act: ",sys_act
        self.agenda.push(sys_act)
    
    def respond(self, goal):
        '''
        This method is called to get the user response.

        :param goal: of :class:`UserModel.UMGoal`
        :type goal: :class:`UserModel.UMGoal`
        :returns: (instance) of :class:`DiaAct.DiaActWithProb`
        '''
        #print "GOAL: ",goal
        act = self.agenda.pop()

        act = Action.from_pydial_act(act)

        if self.mode == "simulator":
            user_act = self.next(act)
            user_act = user_act.to_pydial_act()
            return user_act
        else:
            user_act = self.get_next_act()
            pydial_acts = []
            if len(user_act) == 0:
                user_act.append(Action("GOODBYE"))
            for act in user_act:
                pydial_acts.append(act.to_pydial_act())
            
            return pydial_acts
        

    def get_next_act(self):
        actions = []
        
        if self.turn in self.dialog:
            for act in self.dialog[self.turn]:
                params = {}
                
                action = act.split("(")[0]
                slots = act.split("(")[1].split(")")[0].split(",")
                for slot in slots:
                    if len(slot.strip()):
                        if "=" in slot:
                            slot_name = slot.split("=")[0].lower().replace("_","")
                            slot_val = slot.split("=")[1].lower()
                        else:
                            slot_name = slot.replace("_","")
                            slot_val = ""
                        
                        params[slot_name] = slot_val
                actions.append(Action(action, params))
        
        self.turn += 1
        #print actions
        return actions

    def next(self, agent_action):
        user_act = None

        if self.last_agent_action != None and agent_action != None:
            if agent_action.action == self.last_agent_action.action and agent_action.params == self.last_agent_action.params:
                self.goal.patience -= 1
            else:
                self.goal.patience = self.max_patience
        
        if self.goal.patience < 1:
            return Action(action='GOODBYE')
        
        self.last_agent_action = agent_action
        # First turn -> Inform Intent
        if agent_action.action == 'HELLO' and self.dialog_status == DialogStatus.NOT_STARTED:
            self.dialog_status = DialogStatus.NO_OUTCOME_YET
            user_act = self.reply_to_ask_goal()
            self.last_user_action = user_act
            return user_act

        
        # if not self.in_offer:
        #     self.goal.update_request_slots(list(filter(lambda x: x.action!='OFFER' and x.action!='CONFIRM', agent_action))) 

        if agent_action.action == 'INFORM':
            self.save_inform(agent_action)          # userAct = None

        self.update_status(agent_action)    

        if self.dialog_status == DialogStatus.FINISHED or agent_action.action == 'GOODBYE': 
            self.dialog_status = DialogStatus.FINISHED
            user_act = Action(action='GOODBYE')
            self.last_user_action = user_act
            return user_act
        
        self.executed_agent_actions.append(agent_action)
    
        if agent_action.action == 'REQ_MORE':
            user_act = self.request_random_slot()   # possible userAct = None
        elif agent_action.action == 'CONFIRM':
            user_act = self.confirm(agent_action)
        elif agent_action.action == 'REQUEST':
            user_act = self.reply_to_ask_slot(agent_action)
        elif agent_action.action == 'REPEAT':
            user_act = self.last_user_action
        elif agent_action.action == 'OFFER':
            self.save_offer(agent_action)           # userAct = None
        elif agent_action.action == 'OFFER_INTENT':
            user_act = self.reply_to_offer_intent(agent_action) 
        elif agent_action.action in ['NOTIFY_SUCCESS', 'NOTIFY_FAILURE']: # if we have these 2 actions but we have unrequested slots, request a slot
            request_action = self.request_random_slot()
            if request_action != None and self.current_intent != None and self.yaml_goal.request_slots[self.current_intent] != None:
                return request_action

        if user_act != None:
            if user_act.action != 'NEGATE':
                self.last_user_action = user_act
                return user_act
            else:   # if NEGATE, sometimes request a new slot
                request_slot = np.random.choice([0,1], size=1, p=[0.6, 0.4])[0] # instead of negate request a random slot
                if request_slot:
                    new_user_act = self.request_random_slot()   # possible userAct = None
                    if new_user_act != None:
                        self.last_user_action = new_user_act
                        return new_user_act
                    else:
                        return user_act # NEGATE
        else:    # REQ_MORE, NOTIFY_SUCCESS, NOTIFY_FAILURE, OFFER, INFORM agent actions
            if agent_action.action in ['REQ_MORE', 'NOTIFY_SUCCESS', 'NOTIFY_FAILURE']:
                return self.reply_to_ask_goal()            
            if self.in_offer:   
                select = True   # check if all the slots in offer_slots have a value, if so select the offer
                if self.offer_slots:
                    for val in self.offer_slots.values():
                        if val == None:
                            select = False
                else:
                    select = False
                    
                if select:
                    # save offered slots in request slots
                    if self.offer_slots:
                        for slot, val in self.offer_slots.items():
                            if val != None and slot in self.goal.requests:
                                self.goal.requests[slot] = val
                                self.yaml_goal.request_slots[slot] = val
                    self.in_offer = False
                    del self.offer_slots
                    self.offer_slots = {}
                    user_act = Action(action='SELECT')
                    self.last_user_action = user_act
                    return user_act
                else: 
                    wrong_offer = True # check if the agent made a wrong offer
                    for slot in agent_action.params:
                        if slot in self.offer_slots:
                            wrong_offer = False

                    if wrong_offer: 
                        self.in_offer = False
                        del self.offer_slots
                        self.offer_slots = {}
                        user_act = Action(action="INFORM_INTENT", params={'intent':self.goal.constraints['intent']})
                    else:   # if not select chose if reply with a request or request_alts
                        choice = np.random.choice([0,1], size=1, p=[0.3, 0.7])[0] # 1 request 0 request_alts
                        if choice: # request
                            user_act = self.request_random_slot()
                        else: # request_alts
                            user_act = Action(action='REQUEST_ALTS')
            else:   # not in offer -> agent informed slot
                user_act = self.request_random_slot()
        
        if user_act == None: # request_random_slot returned None -> there are no requests
            user_act = self.reply_to_ask_goal()
        
        self.last_user_action = user_act
        return user_act

    def inform_type(self):
        return Action(action="INFORM", params={"type":self.dstring})

    def change_goal(self):
        # save already executed goals
        # for goal in self.goal.goals:
        #     if self.goal.executed_goals[goal]:
        #         self.already_executed_goals.append(goal)

        # if self.current_intent != None:
        #     self.finished_intents.append(self.current_intent)
            
        # generate new goal
        new_goal = self.domain.generate_random_goal()
        self.set_goal(copy.deepcopy(new_goal))

        # update goal with already executed agent actions
        self.goal.update_request_slots(self.executed_agent_actions)
        # update goal with already executed goals
        # for goal in self.already_executed_goals:
        #     self.goal.executed_goals[goal] = True
        
        return self.reply_to_ask_goal()

    # reply to 'AskGoal' agent action
    def reply_to_ask_goal(self):
        if self.current_intent != None:
            if self.current_intent not in self.finished_intents:
                return Action(action='INFORM_INTENT', params={'intent':self.current_intent})  

        intents = self.yaml_goal.goals
        for intent in intents:
            if intent not in self.finished_intents and intent not in self.informed_intents:
                self.informed_intents.append(intent)
                self.current_intent = intent
                
                return Action(action='INFORM_INTENT', params={'intent':intent})   
        
        # No more goals -> bye 
        self.dialog_status = DialogStatus.FINISHED
        return Action(action='GOODBYE')

    # reply to 'REQUEST' agent action
    def reply_to_ask_slot(self, agent_action):

        params = {}

        requested_slot = agent_action.params['slot']
        requested_slot_value = ''

        # If the user is cooperative it will reply with the requested slot 
        reply_requested_slot = np.random.choice([0,1], size=1, p=[1-self.user_cooperation, self.user_cooperation])[0]
        
        if reply_requested_slot:    # reply with requested slot value
            if requested_slot == 'intent':
                if self.current_intent != None:
                    return Action(action='INFORM_INTENT', params={'intent':self.current_intent})   
                else:
                    return self.reply_to_ask_goal()
            elif requested_slot in self.informed_slots:
                requested_slot_value = self.informed_slots[requested_slot]
                params.update({requested_slot: requested_slot_value})
            else:
                if self.goal.contains_slot_const(requested_slot):
                    requested_slot_value = self.goal.get_correct_const_value(requested_slot)
                    if type(requested_slot_value) == list:
                        requested_slot_value = random.choice(requested_slot_value)
                    if requested_slot_value != None:
                        self.informed_slots.update({requested_slot:requested_slot_value})
                        params.update({requested_slot:requested_slot_value})           
        else:
            # reply with another slot
            params = self.get_additional_random_slot(params, requested_slot, False) 


        # add additional non-requested slots with a given probability
        params = self.get_additional_random_slot(params, requested_slot, True) 

        if requested_slot_value != None and requested_slot_value != '': 
            user_action = Action(action='INFORM', params=params)
        else:
            user_action = Action(action='NEGATE')
            self.informed_slots[requested_slot] = 'dontcare'
        
        return user_action

    # get additional slots, different from requested_slot
    # if prob is True choose with a given probability if getting or not a new slot
    # if prob is False always get one new slot (if there are new slots available)
    def get_additional_random_slot(self, params={}, requested_slot='', prob=True):
        if prob:
            add_slot = np.random.choice([0,1], size=1, p=[1-self.add_slot_prob, self.add_slot_prob])[0]

            while add_slot and len(list(params.keys()))+1 < len(list(self.goal.constraints)): 
                random_slot = random.choice(self.goal.constraints)
                slot_name = random_slot.slot
                slot_val = random_slot.val
                # retry until the new slot is different from the requested slot
                while slot_name == requested_slot:
                    random_slot = random.choice(self.goal.constraints)
                    slot_name = random_slot.slot
                    slot_val = random_slot.val
                
                params.update({slot_name:slot_val})
                add_slot = np.random.choice([0,1], size=1, p=[1-self.add_slot_prob, self.add_slot_prob])[0] 
        else:
            if len(list(params.keys()))+1 < len(list(self.goal.constraints)):
                random_slot = random.choice(self.goal.constraints)
                slot_name = random_slot.slot
                slot_val = random_slot.val
                # retry until the new slot is different from the requested slot
                while slot_name == requested_slot:
                    random_slot = random.choice(self.goal.constraints)
                    slot_name = random_slot.slot
                    slot_val = random_slot.val
                
                params.update({slot_name:slot_val})

        self.informed_slots.update(params)

        return params

    def save_offer(self, agent_action): # Fix if adding offer agent actions
        if not self.in_offer:
            self.in_offer = True
            self.offer_slots = copy.deepcopy(self.goal.requests)
            
        for slot_key, slot_val in agent_action.params.items():
            if slot_key in self.offer_slots:
                    self.offer_slots[slot_key] = slot_val

    def save_inform(self, agent_action):
        for slot_key, slot_val in agent_action.params.items():
            if slot_key in self.goal.requests:
                self.goal.requests[slot_key] = slot_val
            
            for intent in self.yaml_goal.goals:
                if slot_key in self.yaml_goal.request_slots[intent]:
                    self.yaml_goal.request_slots[intent][slot_key] = slot_val

    def reply_to_offer_intent(self, agent_action):
        intent = agent_action.params['intent']
        if self.goal.constraints['intent']:
            goal_intent = self.goal.constraints['intent']
            if type(goal_intent.val) == list:
                if intent in goal_intent.val:            
                    return Action(action='AFFIRM_INTENT')
            else:
                if intent == goal_intent.val:
                    return Action(action='AFFIRM_INTENT')
        
        return Action(action='NEGATE_INTENT')

    def request_random_slot(self):
        request_slots = []
        # if self.in_offer and self.current_intent!=None:
        #     slots = self.offer_slots[self.current_intent]
        # else:
        if self.in_offer and self.current_intent!=None and self.current_intent in self.offer_slots:
            slots = self.offer_slots[self.current_intent]
        elif self.current_intent!=None and self.yaml_goal.request_slots[self.current_intent]:
            slots = self.yaml_goal.request_slots[self.current_intent]
        else:
            return None
        
        for slot, val in slots.items():
            if val == None:
                request_slots.append(slot)
        
        if request_slots:
            slot = random.choice(request_slots)
            return Action(action='REQUEST', params={slot:""})
        else:
            return None

    def confirm(self, action):
        
        param = list(action.params.keys())[0]
        if param == 'intent':
            if self.current_intent != None and action.params[param] == self.current_intent:
                return Action(action='AFFIRM')
            else:
                if self.current_intent == None:
                    return self.reply_to_ask_goal()
                else:
                    return Action(action='INFORM_INTENT', params={'intent':self.current_intent})
        elif param in self.informed_slots:    # param is informed
            if action.params[param] == self.informed_slots[param]:  
                return Action(action='AFFIRM')    # same as informed value
            else:
                p = {param: self.informed_slots[param]}
                return Action(action='INFORM', params=p)    # different from informed value
        else:                               # param not informed
            if param in self.goal.requests:
                val = self.goal.requests[param]
                if val != None:   # slot already requested -> check value        
                    if action.params[param] == val:             
                        return Action(action='AFFIRM')
                    else:
                        p = {param: val}
                        return Action(action='INFORM', params=p)
            else:   # param not in request slots
                slot_val = self.goal.get_correct_const_value(param)   # check in inform slots
                if slot_val != None:
                    if type(slot_val) != list:
                        if action.params[param] == slot_val:
                            return Action(action='AFFIRM')
                        else:
                            p = {param: slot_val}
                            return Action(action='INFORM', params=p)
                    else:
                        if action.params[param] in slot_val:
                            return Action(action='AFFIRM')
                        else:
                            p = {param: random.choice(slot_val)}
                            return Action(action='INFORM', params=p)

        # param not in request slots, not in informed/inform slots -> negate or return None      
        accept = np.random.choice([0,1], size=1, p=[1-self.user_cooperation, self.user_cooperation])[0]
        if accept:
            return None
        else:
            return Action(action='NEGATE')

    # Update the status of the dialog -> if all the request slots are filled the dialog is finished
    def update_status(self, agent_action):
        
        not_filled_slots = 0
        not_finished_intents = 0
        # logger.dial("Current intent: "+str(self.current_intent))
        # if self.current_intent != None:
        #     logger.dial(self.yaml_goal.request_slots[self.current_intent])
        # logger.dial("Finished intents: "+str(self.finished_intents))
        if self.current_intent != None:
            if self.yaml_goal.request_slots[self.current_intent] != None and len(self.yaml_goal.request_slots[self.current_intent]):    # the intent has request slots
                for slot in self.yaml_goal.request_slots[self.current_intent].values():  # check if all slots ar filled
                    if slot == None:
                        not_filled_slots += 1
                
                if not_filled_slots == 0:
                    self.finished_intents.append(self.current_intent)
                    self.current_intent = None
            else:   # the intent doesn't have request slots
                if agent_action.action in ["NOTIFY_SUCCESS","NOTIFY_FAILURE"]:
                    self.finished_intents.append(self.current_intent)
                    self.current_intent = None

        for intent in self.yaml_goal.goals:
            if intent not in self.finished_intents:
                not_finished_intents += 1

        if not self.goal.are_all_requests_filled() or not_finished_intents>0:
            self.dialog_status = DialogStatus.NO_OUTCOME_YET        
        else:
            self.dialog_status = DialogStatus.FINISHED  