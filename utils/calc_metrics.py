import os
import argparse
import sys
import matplotlib.pyplot as plt
from matplotlib.ticker import StrMethodFormatter

def read_logs(logs_file):
    
    try:
        with open(logs_file, "r") as f:
            logs = f.read()
    except:
        print "Error reading the file"
        sys.exit(1)

    iterations = logs.split("*** Training Iteration")[1:]
    training_results = []
    eval_results = []
    for iter in iterations:
        training = iter.split("*** Evaluating")[0]
        evaluation = iter.split("*** Evaluating")[1]
        
        training_results.append(training.split("Results for domain:")[-1])
        eval_results.append(evaluation.split("Results for domain:")[-1])
    
    return training_results, eval_results

def calc_metrics(logs_file):

    training_results, eval_results = read_logs(logs_file)

    convergence_rate = []

    for train,eval in zip(training_results, eval_results):
        train_success = float(train.split("Average success = ")[1].split("+")[0].strip())
        eval_success = float(eval.split("Average success = ")[1].split("+")[0].strip())

        convergence_rate.append(round((1-eval_success)/(1-train_success), 2))
    
    return convergence_rate
    
def plot_metrics(logs_dir):

    if not os.path.exists(logs_dir):
        print "Please specify a valid logs directory with the -d argument"
        sys.exit(1)
    
    convergence_rate = []

    logs_files = os.listdir(logs_dir)
    for file in logs_files:
        file_path = os.path.join(logs_dir, file)
        convergence_rate.extend(calc_metrics(file_path))

    x = list(map(lambda x: x+1, range(len(convergence_rate))))
    plt.plot(x, convergence_rate)
    plt.axhline(y=1, color='r', linestyle='-')
    plt.grid(True)
    plt.xticks(x)
    plt.gca().yaxis.set_major_formatter(StrMethodFormatter('{x:,.2f}')) 
    plt.show()

if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument("-d", dest="logs_file", default="", help="Path to the logs file")

    parsed_args = parser.parse_args()

    plot_metrics(parsed_args.logs_file)