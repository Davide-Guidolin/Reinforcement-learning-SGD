from usersimulator.UserModel import GoalGenerator, UMGoal
import yaml
import random
from ontology import Ontology
import copy

class SGDGoalGenerator(GoalGenerator):

    def __init__(self, dstring):
        super(SGDGoalGenerator, self).__init__(dstring)

        self.domain = dstring
        self.goals = {}

        file_name = 'usersimulator/myUserSim/goals/{}.yml'.format(self.domain)
        with open(file_name, 'r') as f:
            self.goals = yaml.safe_load(f)

    def init_goal(self, otherDomainsConstraints, um_patience):
        
        um_goal = UMGoal(um_patience, domainString=self.domain)
        goal = self.generate_goal(um_goal)

        return goal

    def generate_goal(self, um_goal):
        goal_name = random.choice(list(self.goals.keys()))
        goal = self.goals[goal_name]
        
        if self.domain == "Calendar":               # substitute event_name with name
            for slot in copy.deepcopy(goal["inform_slots"]):
                if slot == "event_name":
                    del goal["inform_slots"][slot]
            for intent in goal['goals']['intent']:
                if goal['request_slots'][intent] != None:
                    if "event_name" in goal['request_slots'][intent]:
                        goal['request_slots'][intent]["name"] = "UNK"
                        del goal['request_slots'][intent]["event_name"]

        if self.domain == "Restaurants":               # substitute restaurant_name with name
            for slot in copy.deepcopy(goal["inform_slots"]):
                if slot == "restaurant_name":
                    del goal["inform_slots"][slot]
            for intent in goal['goals']['intent']:
                if goal['request_slots'][intent] != None:
                    if "restaurant_name" in goal['request_slots'][intent]:
                        goal['request_slots'][intent]["name"] = "UNK"
                        del goal['request_slots'][intent]["restaurant_name"]
        
        um_goal.yaml_goal = goal

        # constraints
        for slot in goal['inform_slots']:
            val = goal['inform_slots'][slot]
            if type(val) == list:
                val = val[0]
            slot = slot.replace('_','')
            if not Ontology.global_ontology.is_value_in_slot(self.domain, val, slot):
                val = Ontology.global_ontology.getRandomValueForSlot(self.domain, slot=slot, nodontcare=True)
            
            um_goal.add_const(slot=slot, value=val)
        
        # intents
        intents = []
        for intent in goal['goals']['intent']:
            intents.append(intent)
            um_goal.add_const(slot='intent', value=intent.lower())

        valid_requests = Ontology.global_ontology.getValidRequestSlotsForTask(self.domain)
        #requests
        for intent in intents:
            if goal['request_slots'][intent] != None:
                for slot in goal['request_slots'][intent]:
                    slot = slot.replace('_','')

                    if slot in valid_requests:
                        um_goal.requests[slot] = None

        if 'name' not in um_goal.requests:
            um_goal.requests['name'] = None

        return um_goal
