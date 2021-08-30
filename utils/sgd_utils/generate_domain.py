# Generate domain-rules.json files to suit pydial format
import os
import json
import sys
import sqlite3
from sqlite3 import Error
import random
import argparse

def get_domains_slots(sgd_folder, folder='train'):
    schema_path = os.path.join(sgd_folder, folder, 'schema.json')

    with open(schema_path, 'r') as f:
        schema = json.load(f)

    domains = {}
    
    for domain in schema:
        domain_name = domain["service_name"]
        domains[domain_name] = {}
        slots = []

        for slot in domain["slots"]:
            slots.append(slot["name"])
        
        domains[domain_name]['slots'] = slots

        intents = []
        for intent in domain['intents']:
            intents.append(intent['name'])
        
        domains[domain_name]['intents'] = intents        

    return domains


def get_slots_values(slot_list):
    with open('slots_values.json') as f:
        slots_values = json.load(f)

    slot_vals = {}
    for slot in slot_list:
        slot_vals[slot] = slots_values[slot]
    
    return slot_vals


def generate_rules_file(sgd_folder, domain_name, domains, slots):

    rules = {}
    rules['type'] = domain_name
    rules['requestable'] = domains[domain_name]
    rules['discourseAct'] = ["ack","hello","none","repeat","silence","thankyou"]
    rules['system_requestable'] = domains[domain_name]
    rules['method'] = ["none","byconstraints","byname","finished","byalternatives","restart"]
    rules['informable'] = slots

    file_name = domain_name+'-rules.json'

    with open(file_name, 'w') as f:
        json.dump(rules, f, indent=4)


def create_connection(db_file):
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        print(sqlite3.version)
    except Error as e:
        print(e)
    
    return conn


def create_db(domain_name, slots, intents):
    db_name = domain_name+'-dbase.db'
    print(db_name)
    conn = create_connection(db_name)
    
    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {domain_name}(
        id integer PRIMARY KEY
        """

    if domain_name == "Calendar":
        slots['name'] = slots['event_name']
        del slots['event_name']
    elif domain_name == "Restaurants":
        slots['name'] = slots['restaurant_name']
        del slots['restaurant_name']
    
    if 'name' not in slots:
        slots['name'] = [f'{domain_name} 1', f'{domain_name} 2']
        
    for slot in slots:
        if '_' in slot:
            # slot1 = slot.split('_')
            # slot = slot1[0]+''.join([i.capitalize() for i in slot1[1:]])
            # print(slot)
            slot = slot.replace('_','')
        create_table_sql +=  f",{slot} TEXT"
    create_table_sql += f",intent TEXT" #intents
    create_table_sql += ");"

    try:
        c = conn.cursor()
        c.execute(create_table_sql)
    except Error as e:
        print(e)

    ## INSERT
    insert_sql = f"INSERT INTO {domain_name} VALUES(?"
    for slot in slots:
        insert_sql += ",?"
    insert_sql += ",?"  #intents
    insert_sql += ")"

    for i in range(1000):
        values = [i+1]
        for slot in slots:
            values.append(random.choice(slots[slot]))
        values.append(random.choice(intents))   #intents
        try:
            c = conn.cursor()
            c.execute(insert_sql, tuple(values))
            conn.commit()
        except Error as e:
            print(e)
        

def merge_domains(domains):

    domains_new = {}
    for dom in domains:
        name = dom.split("_")[0]
        if name not in domains_new:
            domains_new[name] = domains[dom]
        else:
            domains_new[name]["intents"].extend(domains[dom]["intents"])
            domains_new[name]["slots"].extend(domains[dom]["slots"])
            domains_new[name]["intents"] = list(set(domains_new[name]["intents"]))
            domains_new[name]["slots"] = list(set(domains_new[name]["slots"]))
    
    return domains_new

def generate_domain(sgd_folder, domain_name):
    
    domains = get_domains_slots(sgd_folder)

    domains = merge_domains(domains)

    domain_name = domain_name.split("_")[0]
    if domain_name not in domains:
        print("Error: this domain is not present in the sgd domains")
        sys.exit(0)
    
    slots = get_slots_values(domains[domain_name]['slots'])

    #generate_rules_file(sgd_folder, domain_name, domains, slots)
    create_db(domain_name, slots, domains[domain_name]['intents'])

    print("Done")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('--sgd-folder', dest='sgd_folder', default='../../../dstc8-schema-guided-dialogue',
                        help='Path to the sgd folder')
    
    parser.add_argument('--domain', dest='domain', default='Banks_1',
                        help='Name of the sgd domain')

    parsed_args = parser.parse_args()
 
    generate_domain(parsed_args.sgd_folder, parsed_args.domain)