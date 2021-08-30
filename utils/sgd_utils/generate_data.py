import os
import json
import random

def get_sgd_dialogs(sgd_folder):
        train_path = os.path.join(sgd_folder, "train")
        test_path = os.path.join(sgd_folder, "test")
        n_dialogs = {}
        n_dialogs_total = 0
        for path in [train_path]:  # test_path
            files = sorted(os.listdir(path))

            out_files = {}

            for f in files[:-1]:
                file_path = os.path.join(path, f)
                with open(file_path, 'r') as fp:
                    dialogs = json.load(fp)

                for dialog in dialogs:
                    n_dialogs_total += 1
                    
                    if len(dialog['services']) == 1: #single-domain uncomment this if and move things below 1 tab forward to convert only single domain dialogs
                        for service in dialog['services']:

                            if service not in out_files:
                                n_dialogs[service] = 0
                                out_files[service] = f"../../data/{path.split('/')[-1]}/{service}.md"
                                out = open(out_files[service], 'w')  # create file
                                out.close()
                            n_dialogs[service] += 1
                            out = open(out_files[service], 'a')
                            print(f"## {dialog['dialogue_id']}", file=out)
                            for turn in dialog['turns']:
                                if turn['speaker'] == "USER":
                                    for frame in turn['frames']:
                                        user = []
                                        for action in frame['actions']:
                                            if len(action['values']) == 1:
                                                if '"' in action['values'][0]:
                                                    val = action['values'][0].replace(
                                                        '"', " ")
                                                else:
                                                    val = action['values'][0]

                                                val = val.replace(",","")

                                                user.append(f"USER: {action['act']}({action['slot']}={val})")
                                            elif action['act'] == 'REQUEST':
                                                user.append(f"USER: {action['act']}({action['slot']})")
                                            else:
                                                user.append(f"USER: {action['act']}()")
                                        
                                        user = merge_actions(user)
                                        
                                        for act in user:
                                            print(act, file=out)
                                else:   # agent
                                    for frame in turn['frames']:
                                        agent = []
                                        for action in frame['actions']:
                                            if action['act'] == 'REQUEST':
                                                #agent.append(f"\t- slot{{\"slot\":\"{action['slot']}\"}}")
                                                agent.append(f"AGENT: {action['act']}({action['slot']})")
                                            elif action['act'] in [ 'OFFER', 'INFORM', 'CONFIRM', 'INFORM_COUNT', 'OFFER_INTENT']:
                                                if '"' in action['values'][0]:
                                                    val = action['values'][0].replace('"', " ")
                                                else:
                                                    val = action['values'][0]
                                                val = val.replace(",","")
                                                if action['act'] == 'OFFER_INTENT':
                                                    agent.append(f"AGENT: {action['act']}(intent={val})")
                                                else:
                                                    if action['act'] != 'INFORM_COUNT':
                                                       agent.append(f"AGENT: {action['act']}({action['slot']}={val})")
                                            else:
                                                agent.append(f"AGENT: {action['act']}()")
                                        for act in agent:
                                            print(act, file=out)
                            
                            out.close()   


# merge similar actions e.g. INFORM(city=ny) INFORM(time=11) => INFORM(city=ny, time=11)
def merge_actions(actions_list):
    actions = []
    slots = []
    for a in actions_list:
        if '(' in a:
            actions.append(a.split(': ')[1].split('(')[0])
            slots.append(a.split('(')[1].split(')')[0])
        else:
            actions.append(a.split('* ')[1])
            slots.append("")
    
    merge_dict = {}

    for i in range(len(actions)):
        if actions[i] not in merge_dict:
            merge_dict[actions[i]] = []
        merge_dict[actions[i]].append(i)

    merged = []
    
    for act, indexes in merge_dict.items():
        to_print = "USER: "
        to_print += act
        to_print += "("
        for i, index in enumerate(indexes):
            to_print += slots[index]
            if i!=len(indexes)-1:
                to_print += ', '
        to_print += ")"
        merged.append(to_print)

    return merged

def merge_same_domain(dir):
    files = os.listdir(dir)

    same_domain = {}

    for file in files:
        domain = file.split('_')[0]
        if domain not in same_domain:
            same_domain[domain] = []
        same_domain[domain].append(file)

    for domain in same_domain:
        domain_file_path = os.path.join(dir, f"{domain}.md")
        out_file = open(domain_file_path, 'w')
        for file in same_domain[domain]:
            file_path = os.path.join(dir, file)
            with open(file_path, 'r') as f:
                out_file.write(f.read())
            os.remove(file_path)
        out_file.close()

# delete all files in a folder
def delete_all(dir):
    files = os.listdir(dir)
    for file in files:
        file_path = os.path.join(dir, file)
        os.remove(file_path)

# get number of dialogs for a training or test file
def get_number_of_dialogs(dir, file):
    file_path = os.path.join(dir, file)
    with open(file_path, 'r') as f:
        data = f.read()

    return len(data.split('##'))-1

# split a file in 2 files: training and test files
def split_train_test(train_dir, test_dir, test_pct=0.1, max_train_dialogs=None):
    train_files = os.listdir(train_dir)

    for file in train_files:
        file_path = os.path.join(train_dir, file)
        n_dialogs = get_number_of_dialogs(train_dir, file)
        if max_train_dialogs:
            n_train = min(int((1-test_pct)*n_dialogs), max_train_dialogs)
        else:
            n_train = int((1-test_pct)*n_dialogs)
            
        n_test = n_dialogs - n_train

        with open(file_path, 'r') as f:
            dialogs = f.read().split('##')[1:]
        
        random.shuffle(dialogs)
        train_dialogs = []
        test_dialogs = []
        for i in range(len(dialogs)):
            if i < n_train:
                train_dialogs.append(dialogs[i])
            else:
                test_dialogs.append(dialogs[i])

        with open(file_path, 'w') as f:
            f.write('##')
            f.write('\n##'.join(train_dialogs))

        test_path = os.path.join(test_dir, file)
        with open(test_path, 'w') as f:
            f.write('##')
            f.write('\n##'.join(test_dialogs))

if __name__ == '__main__':
    delete_all("../../data/train/")
    delete_all("../../data/test/")
    get_sgd_dialogs("../../../dstc8-schema-guided-dialogue")
    merge_same_domain("../../data/train/")
    split_train_test("../../data/train/", "../../data/test/", test_pct=0.15) 