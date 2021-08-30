from ..baseline import RuleBasedTracker
import copy
from collections import defaultdict
import math
import re
import sys
from utils import ContextLogger, dact
from policy import SummaryUtils
from ontology import Ontology
from belieftracking import BeliefTrackingUtils
import pprint

def labels(user_act, mact, lastInformedVenue):
    
    '''
    Convert inputs to compatible info to belief state

    :param user_act: user's dialogue acts
    :type user_act: dict

    :param mact: machine's dialogue acts
    :type mact: dict

    :param lastInformedVenue:
    :type lastInformedVenue: string

    :return: informed_goals, denied_goals, requested_slots, method, discourseAct, lastInformedVenue
    '''
    # get context for "this" in inform(=dontcare)
    # get context for affirm and negate
    this_slot = None
    
    confirm_slots = []
    offer_intents = []
    offer_slots = []
    for act in mact :   # get this_slot (last system request/select or confirm)
        if act["act"] == "request" :
            this_slot = act["slots"][0][1]
        elif act["act"] == "select" :
            this_slot = act["slots"][0][0]
        elif act["act"] in ["expl-conf","impl-conf"] : # confirm
            confirm_slots += act["slots"]
            this_slot = act["slots"][0][0]
        elif act["act"] == "offer":
            this_slot = act["slots"][0][0]
            offer_slots += act["slots"]
    
    # lastInformedVenue by dk449
    for act in mact:
        if act["act"] == "offer":
            if act["slots"][0][0] == "name":
                lastInformedVenue = act["slots"][0][1]
            
    # goal_labels
    informed_goals = {}
    denied_goals = defaultdict(list)
    for act in user_act :       # for every user action
        act_slots = act["slots"]    # get the slot name and value
        slot = None
        value = None
        if len(act_slots) > 0:
            assert len(act_slots) == 1
            
            if act_slots[0][0] == "this" :
                slot = this_slot
            else :
                slot = act_slots[0][0]
            value = act_slots[0][1]
                
        
        if act["act"] == "INFORM" and slot != None: # if the action is inform
            if confirm_slots:
                for s,v in confirm_slots:       
                    if slot == s and value != v:# if the informed slot is in the confirmed slots but with a different value
                        if s not in denied_goals or v not in denied_goals[s]:  # add this slot and value to the denied goals
                            denied_goals[s].append(v)
            informed_goals[slot]=(value)    # add this slot and value to the informed goals
            
        elif act["act"] == "NEGATE" and slot != None:   # if negate add this slot to denied goals
            denied_goals[slot].append(value)
            
        elif act["act"] == "NEGATE" and len(confirm_slots)>0:   # if negate without a slot => negate the last slot that the system confirmed
            slot_values = confirm_slots
            if len(slot_values) > 1:
                #print "Warning: negating multiple slots- it's not clear what to do."
                pass
            else :
                for slot, value in slot_values :
                    denied_goals[slot].append(value)
        elif act["act"] == "NEGATE":    # negate to a request
            if this_slot:
                denied_goals[this_slot].append(-1)

        elif act["act"] == "AFFIRM" :   # if affirm => add the last slot that the system confirmed to the informed goals
            slot_values = confirm_slots
            for slot, value in confirm_slots :
                informed_goals[slot]=(value)
        
        # Manage intents
        elif act["act"] == "INFORM_INTENT" and slot == 'intent' and value != None:  # if inform intent -> add value to informed goals
            informed_goals[slot] = (value)
        elif act["act"] == "NEGATE_INTENT": # if negate intent -> add last offered intent to denied goals
            if len(offer_intents) > 1:
                pass
            else:
                for slot, value in offer_intents:
                    denied_goals[slot].append(value)
        elif act["act"] == "AFFIRM_INTENT": #  if affirm intent -> add last offered intent to informed goals
            if len(offer_intents) > 1:
                pass
            else:
                for slot, value in offer_intents:
                    informed_goals[slot]=(value)
        
        elif act["act"] == "SELECT":
            for slot, value in offer_slots:
                informed_goals[slot]=(value)
                    
    # requested slots
    requested_slots = []
    for act in user_act :
        if act["act"] == "REQUEST": 
            for _, requested_slot in act["slots"]:  # add requested slots to requested_slots
                requested_slots.append(requested_slot)
        if act["act"] == "CONFIRM": # added by dk449    # add confirm(slot=val) to requested_slots (probably not needed)
            for requested_slot, _ in act["slots"]:
                requested_slots.append(requested_slot)
    # method
    method="none"
    act_types = [act["act"] for act in user_act]
    mact_types = [act["act"] for act in mact]
    
    if "REQUEST_ALTS" in act_types :       
        method = "byalternatives"
    elif "GOODBYE" in act_types :
        method = "finished"
    elif "INFORM" in act_types:
        method = "byconstraints"
        for act in [uact for uact in user_act if uact["act"] == "INFORM"] : # for every inform user act
            slots = [slot for slot, _ in act["slots"]]
            if "name" in slots :                                            # if the slot is name -> byname
                method = "byname"
    # dk449
    elif "restart" in act_types:
        method = "restart"
    elif not "INFORM" in act_types and not "NEGATE" in act_types and ("REQUEST" in act_types or "CONFIRM" in act_types):
        if lastInformedVenue != "":
            method = "byname"

    # discourseAct
    discourseAct = "none"
    if "silence" in act_types:
        discourseAct = "silence"
    elif "repeat" in act_types:
        discourseAct = "repeat"
    elif "thankyou" in act_types:
        discourseAct = "thankyou"
    elif "ack" in act_types:
        discourseAct = "ack"
    elif "hello" in act_types:
        discourseAct = "hello"
    elif "GOODBYE" in act_types:
        discourseAct = "bye"
            
    return informed_goals, denied_goals, requested_slots, method, discourseAct, lastInformedVenue

def Uacts(turn):
    '''
    Convert turn info to hypotheses

    :param turn:
    :type turn: dict

    :return: list -- converted hypotheses
    '''
    # return merged slu-hyps, replacing "this" with the correct slot
    mact = []
    if "dialog-acts" in turn["output"] :
        mact = turn["output"]["dialog-acts"]
    this_slot = None
    for act in mact :
        if act["act"] == "request" :
            this_slot = act["slots"][0][1]
    this_output = []
    for slu_hyp in turn['input']["live"]['slu-hyps'] :
        score = slu_hyp['score']
        this_slu_hyp = slu_hyp['slu-hyp']
        these_hyps =  []
        
        for hyp in this_slu_hyp :
            for i in range(len(hyp["slots"])) :
                slot,_ = hyp["slots"][i]
                if slot == "this" :
                    hyp["slots"][i][0] = this_slot
            these_hyps.append(hyp)
        this_output.append((score, these_hyps))
    this_output.sort(key=lambda x:x[0], reverse=True)
    
    return this_output

def normalise_dict(x) :
    x_items = x.items()
    total_p = sum([p for k,p in x_items])
    if total_p > 1.0 :
        x_items = [(k,p/total_p) for k,p in x_items]
    return dict(x_items)

def clip(x) :
    if x > 1:
        return 1
    if x<0 :
        return 0
    return x

class SGDBeliefTracker(RuleBasedTracker): 

    def __init__(self, dstring):
        super(SGDBeliefTracker, self).__init__(dstring)
        self.restart()
        self.lastInformedVenue = ""

    def update_belief_state(self, lastact, obs, constraints=None):
        '''
        Does the actual belief tracking via tracker.addTurn

        :param lastact: last system dialgoue act
        :type lastact: string

        :param obs: current observation
        :type obs: list
        
        :param constraints:
        :type constraints: dict

        :return: dict -- previous belief state
        '''
        curturn = self._convertHypToTurn(lastact, obs)  
        last_feature = None
        
        if self.prevbelief is not None and 'features' in self.prevbelief.keys():
            last_feature = copy.deepcopy(self.prevbelief['features'])
 
        if self.turn == 0:
            self.prevbelief = self._init_belief(constraints)

        curturn['lastSysAct'] = lastact
        curturn['lastUserAct'] = None
        if obs:
            curturn['lastUserAct'] = obs[0][0]
        self.prevbelief = self._updateBelief(curturn)   
        
        self._updateMactFeat(last_feature, lastact) 
        self.turn += 1
        #logger.debug(self.str())            

        #print self.prevbelief
            
        return self.prevbelief

    def _convertHypToTurn(self, lastact, obs):
        '''
        Convert hypotheses to turn
        
        :param lastact: last system dialogue act
        :type lastact: string

        :param obs: current observation
        :type obs: list
        
        :return: dict -- turn dict
        '''
        curturn = {'turn-index': self.turn}
        
        # Last system action
        slastact = []
        if self.turn > 0:
            slastact = dact.ParseAct(lastact, user=False)
            slastact = BeliefTrackingUtils._transformAct(slastact, {}, 
                                                         Ontology.global_ontology.get_ontology(self.domainString), 
                                                         user=False)
        curturn['output'] = {'dialog-acts': slastact}

        # User act hyps
        accumulated = defaultdict(float)
        for (hyp, prob) in obs:
            hyp = self.parseAct(hyp)
            hyp = BeliefTrackingUtils._transformAct(hyp, {}, Ontology.global_ontology.get_ontology(self.domainString))
            hyp = dact.inferSlotsForAct(hyp)    # if slot is "this" get slot from value if ontology is provided
            
            prob = min(1.0, prob)
            if prob < 0:
                prob = math.exp(prob)
            accumulated = BeliefTrackingUtils._addprob(accumulated, hyp, prob)
            
        sluhyps = BeliefTrackingUtils._normaliseandsort(accumulated)
        
        curturn['input'] = {'live': {'asr-hyps':[], 'slu-hyps':sluhyps}}
        
        return curturn
    
    def parseAct(self, raw_act_text, user=True):
        final = []
        
        for act_text in raw_act_text.split("|") :
            try:
                final += self._parseAct(act_text, user=user)
            except RuntimeError:
                pass # add nothing to final if junk act recieved
        return final

    def _parseAct(self, raw_act_text, user=True):
    
        raw_act = self.__parseAct(raw_act_text)
        final_dialog_act = []

        if raw_act['act'] == "SELECT" and user :
            raw_act['act'] = "INFORM"

        main_act_type = raw_act['act']
        if raw_act['act'] == "REQUEST": # if request, get requested slots
            for requested_slot in [slot for slot, value in raw_act['slots'] if value == None] :
                final_dialog_act.append( {
                    'act': 'REQUEST',
                    'slots': [['slot',requested_slot]],
                    })

            main_act_type = "INFORM"
            
        elif (raw_act['act'] in ['NOTIFY_SUCCESS', 'NOTIFY_FAILURE', 'AFFIRM_INTENT', 'NEGATE_INTENT','NEGATE','repeat','AFFIRM','GOODBYE','restart','REQUEST_ALTS','hello','silence','THANK_YOU','ack','help','canthear','REQ_MORE']):
            if raw_act['act'] == "hello" and not user:
                raw_act['act'] = "welcomemsg"
            final_dialog_act.append( {
                    'act': raw_act['act'],
                    'slots': [],
                    })
            main_act_type = 'INFORM'
        elif (raw_act['act'] not in ['OFFER', 'INFORM_INTENT', 'OFFER_INTENT', 'INFORM','deny','CONFIRM','SELECT','null', 'badact']):
            
            print raw_act_text
            print raw_act
            raise RuntimeError,'Dont know how to convert raw act type %s' % (raw_act['act'])


        if raw_act['act'] == "INFORM_INTENT":
            for slot, val in raw_act['slots']:  
                if slot == 'intent':
                    # final_dialog_act.append( {
                    #         'act': "INFORM",
                    #         'slots': [['intent', raw_act['slots']['intent']]],
                    #         })
                    main_act_type = 'INFORM'
                
        if raw_act['act'] == "OFFER_INTENT" and not user:
            main_act_type = "INFORM"

        if raw_act['act'] == "CONFIRM" and not user :
            main_act_type = "CONFIRM"

        if raw_act['act'] == "SELECT" and not user and "other" in [v for s,v in raw_act['slots']] :
            main_act_type = "CONFIRM"
        
        if raw_act['act'] == "NEGATE" and len(raw_act["slots"]) ==0 :
            final_dialog_act.append( {
                    'act': "NEGATE",
                    'slots': [],
                    })
        
        if not user and "none" in [v for _,v in raw_act["slots"]] :
            
            name_value, = [v for s,v in raw_act["slots"] if s=="name"]
            other_slots = [[slot,value] for slot,value in raw_act["slots"] if value != "none"]
            
            if other_slots:
                raw_act = ({'act':'INFORM', 'slots':other_slots})
            else :
                raw_act = {"slots":[],"act":"INFORM"}
        
        # group slot values by type
        # try to group date and time into inform acts
        # put location fields in their own inform acts
        main_act_slots_dict = {}
        for (raw_slot_name,raw_slot_val) in raw_act['slots']:
            slot_name = raw_slot_name
            slot_val = raw_slot_val
            slot_group = slot_name
            if (slot_group not in main_act_slots_dict):
                main_act_slots_dict[slot_group] = {}
            if (slot_name not in main_act_slots_dict[slot_group]):
                main_act_slots_dict[slot_group][slot_name] = []
            if (slot_val not in main_act_slots_dict[slot_group][slot_name]):
                main_act_slots_dict[slot_group][slot_name].append(slot_val)
                
        for slot_group_name,slot_group_items in main_act_slots_dict.items():
            for slot,vals in slot_group_items.items():
                # if slot in ["task", "type"] :
                #     continue
                # we shouldn't skip this
                if slot == "" :
                    slot = "this"
                if main_act_type == "NEGATE" and len(vals) == 2 and "dontcare" not in vals :
                    # deal with deny(a=x, a=y)
                    false_value = vals[0]
                    true_value = vals[1]
                    final_dialog_act.append({
                                    'act': "NEGATE",
                                    'slots': [[slot,false_value]],
                                })
                    final_dialog_act.append({
                                    'act': "NEGATE",
                                    'slots': [[slot,true_value]],
                                })
                else :
                    for val in vals:
                        
                        if val == None or val == "other":
                            
                            continue
                        
                        if len(slot)>0 and slot[-1] == "!" :
                            slot = slot[:-1]
                            slots = [ [slot,val] ]
                            final_dialog_act.append({
                                    'act': "NEGATE",
                                    'slots': slots,
                                    })
                        else :
                            slots = [ [slot,val] ]
                            if ((slot,val) == ("this","dontcare")) and (main_act_type != "INFORM") :
                                continue
                            
                            final_dialog_act.append({
                                    'act': ("INFORM" if slot=="count" else main_act_type),
                                    'slots': slots,
                                })
                        
        if not user and len(final_dialog_act)==0 :
            final_dialog_act.append({"act":"REQ_MORE","slots":[]}) # Repeat ??

        return final_dialog_act

    def __parseAct(self, t):

        r = {}
        r['slots'] = []

        if t == "BAD ACT!!":
            r['act'] = 'null'
            return r
            
        #m = re.search('^(.*)\((.*)\)$',t.strip())
        m = re.search('^([^\(\)]*)\((.*)\)$',t.strip())
        if (not m):
            r['act'] = 'null'
            return r

        r['act'] = m.group(1)
        content = m.group(2)
        while (len(content) > 0):
            m = re.search('^([^,=]*)=\s*\"([^\"]*)\"\s*,?',content)
            if (m):
                slot = m.group(1).strip()
                val = m.group(2).strip("' ")
                content = re.sub('^([^,=]*)=\s*\"([^\"]*)\"\s*,?','',content)
                r['slots'].append( [slot,val] )
                continue
            m = re.search('^([^,=]*)=\s*([^,]*)\s*,?',content)
            if (m):
                slot = m.group(1).strip()
                val = m.group(2).strip("' ")
                content = re.sub('^([^,=]*)=\s*([^,]*)\s*,?','',content)
                r['slots'].append( [slot,val] )
                continue
            m = re.search('^([^,]*),?',content)
            if (m):
                slot = m.group(1).strip()
                val = None
                content = re.sub('^([^,]*),?','',content)
                r['slots'].append( [slot,val] )
                continue
            raise RuntimeError,'Cant parse content fragment: %s' % (content)

        for slot_pair in r['slots']:
            if (slot_pair[1] == None):
                continue
            slot_pair[1] = slot_pair[1].lower()
            if slot_pair[0] == "count" :
                try :
                    int_value = int(slot_pair[1])
                    slot_pair[1] = int_value
                except ValueError:
                    pass
        return r

    def _addTurn(self, turn):
        '''
        Add turn info

        :param turn:
        :type turn: dict
        
        :return: None
        '''
        '''
        turn => {'output': {'dialog-acts': [{'slots': [('slot', 'intent')], 'act': 'request'}]}, 'turn-index': 19, 'input': {'live': {'asr-hyps': [], 'slu-hyps': [{'slu-hyp': [{u'slots': [[u'intent', None]], u'act': u'REQUEST'}], 'score': 1.0}]}}}
        '''
        
        hyps = copy.deepcopy(self.hyps)
        if "dialog-acts" in turn["output"] :
            mact = turn["output"]["dialog-acts"]
        else :
            mact = []
        slu_hyps = Uacts(turn)
        
        this_u = defaultdict(lambda : defaultdict(float))
        method_stats = defaultdict(float)
        requested_slot_stats = defaultdict(float)
        discourseAct_stats = defaultdict(float)
        hyps["denied-goals"] = []
        for score, uact in slu_hyps :
            informed_goals, denied_goals, requested, method, discourseAct, self.lastInformedVenue = labels(uact, mact, self.lastInformedVenue)
             
            method_stats[method] += score
            for slot in requested:  # save requested slots score
                requested_slot_stats[slot] += score
            # goal_labels
            for slot in informed_goals: # save informed slot score
                this_u[slot][informed_goals[slot]] += score
        
            discourseAct_stats[discourseAct] += score

            for slot in denied_goals.keys():
                if slot not in hyps["denied-goals"]:
                    hyps["denied-goals"].append(slot)
        
        for slot in set(this_u.keys() + hyps["goal-labels"].keys()) :
            q = max(0.0,1.0-sum([this_u[slot][value] for value in this_u[slot]])) # clipping at zero because rounding errors
            
            if slot not in hyps["goal-labels"] :
                hyps["goal-labels"][slot] = {}
                
            for value in hyps["goal-labels"][slot] :
                hyps["goal-labels"][slot][value] *= q

            prev_values = hyps["goal-labels"][slot].keys()
            for value in this_u[slot] :
                if value in prev_values :
                    hyps["goal-labels"][slot][value] += this_u[slot][value]
                else :
                    hyps["goal-labels"][slot][value]=this_u[slot][value]
        
            hyps["goal-labels"][slot] = normalise_dict(hyps["goal-labels"][slot])
        
        # method node, in 'focus' manner:
        q = min(1.0,max(0.0,method_stats["none"]))
        method_label = hyps["method-label"]
        for method in method_label:
            if method != "none" :
                method_label[method] *= q
        for method in method_stats:
            if method == "none" :
                continue
            if method not in method_label :
                method_label[method] = 0.0
            method_label[method] += method_stats[method]
        
        if "none" not in method_label :
            method_label["none"] = max(0.0, 1.0-sum(method_label.values()))
        
        hyps["method-label"] = normalise_dict(method_label)

        # discourseAct (is same to non-focus)
        hyps["discourseAct-labels"] = normalise_dict(discourseAct_stats)
        
        # requested slots
        informed_slots = []
        for act in mact :
            if act["act"] == "inform" :             
                for slot,value in act["slots"]:
                    informed_slots.append(slot)
        
                    
        for slot in set(requested_slot_stats.keys() + hyps["requested-slots"].keys()):
            p = requested_slot_stats[slot]
            prev_p = 0.0
            if slot in hyps["requested-slots"] :
                prev_p = hyps["requested-slots"][slot]
            x = 1.0-float(slot in informed_slots)
            new_p = x*prev_p + p
            hyps["requested-slots"][slot] = clip(new_p)
        
        hyps["sysAct"] = turn['lastSysAct']
        hyps["userAct"] = turn['lastUserAct']

        self.hyps = hyps 
        return self.hyps
    
    def restart(self):
        '''
        Reset some private members
        '''
        super(SGDBeliefTracker, self).restart()
        self.hyps = {"goal-labels":{},"method-label":{}, "requested-slots":{}}