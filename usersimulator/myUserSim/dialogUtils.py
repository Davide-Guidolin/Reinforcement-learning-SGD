from enum import Enum
from utils import DiaAct
import random

'''
Enum used to represent the dialog status
'''
class DialogStatus(Enum):
    NOT_STARTED = 0 
    NO_OUTCOME_YET = 1
    FINISHED = 2  

'''
Class used to represent an action
'''
class Action:

    def __init__(self, action=None, params={}):
        self.action = action
        self.params = params

    def to_pydial_act(self):
        
        if self.action == "GOODBYE":
            return DiaAct.DiaAct("GOODBYE()")
        elif self.action == "AFFIRM":
            return DiaAct.DiaAct("AFFIRM()")
        elif self.action == "NEGATE":
            return DiaAct.DiaAct("NEGATE()")
        elif self.action == "INFORM":
            slot, val = self.params.items()[0]
            return DiaAct.DiaAct("INFORM({}={})".format(slot, val))
        elif self.action == "REQUEST":
            slot = self.params.keys()[0]
            return DiaAct.DiaAct("REQUEST({})".format(slot))
        elif self.action == "INFORM_INTENT":
            val = self.params['intent']
            return DiaAct.DiaAct("INFORM_INTENT(intent={})".format(val))
        elif self.action == "SELECT":
            return DiaAct.DiaAct("SELECT()")
        else:
            return DiaAct.DiaAct("{}()".format(self.action))
    
    @classmethod
    def from_pydial_act(cls, action):
        if action.act == 'hello':
            return cls(action="HELLO")
        elif action.act == 'bye':
            return cls(action="GOODBYE")        
        elif action.act == 'request':
            slot = action.items[0].slot
            return cls(action="REQUEST", params={"slot":slot})
        elif action.act == 'requalts' or action.act == 'reqmore':
            return cls(action="REQ_MORE")
        elif action.act == 'inform':
            params = {}
            for slot in action.items:
                params.update({slot.slot: slot.val})
            return cls(action="INFORM", params=params)
        elif action.act == 'confirm':
            slot = action.items[0]
            return cls(action="CONFIRM", params={slot.slot: slot.val})
        elif action.act == 'affirm':
            return cls(action='AFFFIRM')
        elif action.act == 'negate':
            return cls(action='NEGATE')
        elif action.act == 'repeat':
            return cls(action='REPEAT')
        elif action.act == 'notify':
            return cls(action='NOTIFY_SUCCESS')
        elif action.act == 'offer':
            params = {}
            for slot in action.items:
                params.update({slot.slot: slot.val})
            return cls(action="OFFER", params=params)
            
        return None
        

    def set_utterance(self, utterance):
        self.utterance = utterance
    
    def __str__(self):
        return "{}({})".format(self.action, self.params)

class DialogGoal:

    def __init__(self, goals={}, inform_slots={}, request_slots={}):

        self.goals = []
        for intent in goals['intent']:
            self.goals.append(intent.lower())

        if inform_slots is None:
            self.inform_slots = {}
        else:    
            self.inform_slots = {}
            for slot in inform_slots:
                slot1 = slot.replace('_','')
                self.inform_slots[slot1] = inform_slots[slot]
        
        self.request_slots = {}
        for intent in request_slots:
            intent1 = intent.lower()
            self.request_slots[intent1] = {}
            if request_slots[intent]:
                for slot in request_slots[intent]:
                    slot1 = slot.replace('_','')
                    self.request_slots[intent1][slot1] = None
        
        self.request_slots[(self.request_slots.keys())[0]]['name'] = None


    def get_inform_slot_value(self, slot):
        if slot in self.inform_slots.keys():
            value = self.inform_slots[slot]
            if isinstance(value, list):
                value = random.choice(value)
            return {slot: value}
        else:
            return 'UNK'
    
    def get_random_inform_slot_value(self):
        key = random.choice(list(self.inform_slots.keys()))
        val = self.inform_slots[key]
        if isinstance(val, list):
            val = random.choice(val)
        return {key: val}

    def update_request_slots(self, executed_actions):
        for action in executed_actions:
            for slot, value in action.params.items():
                for intent in self.request_slots.keys():
                    if self.request_slots[intent] != None:
                        if slot in self.request_slots[intent].keys():
                            self.request_slots[intent][slot] = value
    
    def has_request_slots(self, slot):
        for intent in self.request_slots.keys():
            if self.request_slots[intent] != None:
                if slot in self.request_slots[intent].keys():
                    return slot, self.request_slots[intent][slot]

        return 'UNK', 'UNK'

    def to_dict(self):
        return {
            'goals': self.goals,
            'inform_slots': self.inform_slots,
            'request_slots': self.request_slots
        }

    
