import json
import re
import copy
import yaml

def get_missinig_slots_from_test(slot, test_file, ont_file):

    with open(ont_file, "r") as f:
        ont = json.load(f)

    if slot not in ont["informable"]:
        raise NameError("The {} slot is not present in ontology".format(slot))
    
    with open(test_file, "r") as f:
        dialogs = f.read().split("##")[1:]
    
    pattern = "{}=".format(slot)
    slot_values = []
    for dialog in dialogs:
        indexes = [m.end() for m in re.finditer(pattern, dialog)]

        for i in indexes:
            end = i 
            for j in range(i, len(dialog)):
                if dialog[j] == ',' or dialog[j] == ')':
                    end = j
                    break
            
            slot_val = dialog[i:end]
            if slot_val not in slot_values and slot_val not in ont["informable"][slot]:
                slot_values.append(slot_val)

    for slot in slot_values:
        print(f'"{slot}",')

def remove_duplicates(ont_file):
    with open(ont_file, "r") as f:
        ont = json.load(f)

    new_ont = copy.deepcopy(ont)
    informable = ont["informable"]
    
    for slot in informable:
        while "dontcare" in informable[slot]:
            informable[slot].remove("dontcare")
        new_ont["informable"][slot] = list(map(lambda x: x.replace(",","").replace("\'",""), list(set(informable[slot])))) #remove ',' and remove duplicates
    


    with open(ont_file, "w") as f:
        json.dump(new_ont, f, indent=4)

def add_goal_slots(ont_file, goal_file):
    with open(ont_file, "r") as f:
        ont = json.load(f)
    
    new_ont = copy.deepcopy(ont)

    with open(goal_file, "r") as f:
        goals = yaml.safe_load(f)

    for _, goal in goals.items():

        for slot,values in goal["inform_slots"].items():
            slot = slot.replace("_","")
            if slot not in new_ont["informable"]:
                new_ont["informable"][slot] = []
            for val in values:
                val = val.replace(",","").lower()
                if val not in new_ont["informable"][slot] and val != "dontcare":
                    new_ont["informable"][slot].append(val)
    
    with open(ont_file, "w") as f:
        json.dump(new_ont, f, indent=4)

if __name__ == "__main__":
    get_missinig_slots_from_test("eventtime", "../../data/test/Calendar.md", "../../ontology/ontologies/Calendar-rules.json")
    #remove_duplicates("../../ontology/ontologies/Restaurants-rules.json")
    #add_goal_slots("../../ontology/ontologies/Restaurants-rules.json","../../usersimulator/myUserSim/goals/Restaurants.yml")
    #remove_duplicates("../../ontology/ontologies/Calendar-rules.json")