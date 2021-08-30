# Reinforcement Learning with PyDial

## Setup
1. Setup [PyDial](https://pydial.cs.hhu.de/tutorials/Introduction%20to%20PyDial.html#first-bullet) and try the introductory examples to make sure that everything works correctly.

## Generate a custom domain from sgd domains
### Generate the database file
To generate a PyDial domain from sgd you can use the [`generate_domain.py`](utils/sgd_utils/generate_domain.py) script. It requires 2 arguments: 

* `--sgd-folder`: the path to the sgd main folder 
* `--domain`: the name of the sgd domain

E.g. if the sgd folder is adjacent to the `pydial-rl` folder you can run the script from the `Utils` folder like this:

`python generate_domain.py --sgd-folder ../../dstc8-schema-guided-dialogue/ --domain Events_1`

This script will generate a `{domain_name}-dbase.db` file and a `{domain_name}-rules.json` file, however, for now, we will use only the `.db` file since the generation of the rules file is not reliable, yet.

### Generate the rules file
Now we need to generate the rules file. To do this we will need to use a pydial tool.

First of all we need to copy the generated database file in the `pydial/ontology/ontologies` folder.

Now we need to run the following command from the pydial :

`python scripts/ontologyTool.py -n -d NEW_DOMAIN_NAME -db PATH_TO_DB_FILE --type ENTITY_TYPE` 

e.g. for the Banks_1 domain:

`python2 scripts/ontologyTool.py -n -d Banks_1 -db ontology/ontologies/Banks_1-dbase.db --type Banks`

Now you will need to select the informable, system requestable, requestable and binary slots. [Here](https://pydial.cs.hhu.de/tutorials/How%20to%20add%20a%20new%20domain.html) there are more details on this step. For every step of this process you can select all the slots except the `id` slot, but be aware that if you use the pydial goal generator the user goal's slots will be chosen from the set difference `requestable-system_requestable` (requestable should be `system_requestable+goal slots`). The `name` slot should be in `requestable` but not in `system_requestable`

The binary slots are the slots that can have the values True/False or yes/no. The script should generate the rules file for your domain.

## Configuration files
You can find example of configuration files under the [config](config/) folder.

### Notes
* When the rules file is generated there is the possibility that some informable slots values are duplicated and this can cause problems if you use, for example, the `gp` policy, I will try to fix this problem in the database generation, but if you have some errors e.g. `Different number of values for slot amount 92 in ontology 93` make sure that there aren't duplicate values in the informable slots and remove also the `dontcare` value if it's present. If you still have this error on the evaluation you can try to leave only 3-4 informable values in the rules file for the slot that gives problems.
Under the [ontologies](ontology/ontologies/) folder you can find some db and rules files that should work.

* The pydial goal generator adds by default a slot called `name` in the requestable slots. To avoid problems caused by this slot I add it during the generation of the database file with 2 simple values `[{domain_name} 1, {domain_name} 2]`. If your domain contains already the `name` slot you should modify a bit the `generate_domain.py` script (e.g. by commenting the line `slots['name'] = [f'{domain_name} 1', f'{domain_name} 2']`).

* In the [`utils/sgd_utils/`](utils/sgd_utils/) folder you can find the `generate_domain.py` script and two other scripts. The `fix_ontology.py` file contains some functions used to solve some problems. In the test set  or in the user goals there could be slots missing in the generation of the ontology, to fix this there are the functions `get_missinig_slots_from_test()` and `add_goal_slots()`, moreover there is a `remove_duplicates()` function that removes the duplicate slots in the generated ontology file. The `generate_data()` file contains some functions used to generate the train and test data that is present in the [`data/`](data/) folder.

## Usage
To train an agent the command is `pydial train <config_file>`, e.g. `pydial train config/Test-Banks-DQN.cfg`. In the `_config` folder the intermediate config files will be saved. In the `_logs` folder the logs will be saved and in the `_policies` folder the policies will be saved. To train an agent starting from a given policy you can use the command `pydial train <config_file> --trainsourceiteration=N`.

To test an agent the command is `pydial train <config_file> <iteration_to_test>`, e.g. `pydial test config/Test-Banks-DQN.cfg 50`. In the `_logs` folder the logs will be saved in a new file.

To evaluate the action accuracy the command is `pydial evaluate-actions <config_file> <test_file> --trainsourceiteration=N`, e.g. `pydial evaluate-actions config/Test-Restaurants-GP.cfg data/test/Restaurants.md --trainsourceiteration=50`. In the `_logs` folder the logs will be saved in a new file. The results will be printed on the console.

## Results
Link to the zip file containing the results: [Results](https://drive.google.com/file/d/1uxEdwYMT8gbmOoQI7nl-JMyl5l00eIru/view?usp=sharing)