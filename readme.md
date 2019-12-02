# How to reproduce

These are the complete steps to reproduce the results. Be aware that there might be slight differences due to non-deterministic behavior.
For example get_revisions.py utilizes get_shortest_path from NetworkX which returns the first shortest path if there are more than one. The order of the graph traversal in turn depends on the representation of the graph in memory which gets build in the order the data is returned from the MongoDB.


## 0. What if I only want to reproduce the plots and figures?

The whole process is described here but if you just want to reproduce the plots and tables you can use the extracted and aggregated information provided by us. 
In that case you have to fetch the pre-aggregated data beforehand and put it into ./data/

```bash
cd ./data/
wget http://www.user.informatik.uni-goettingen.de/~trautsch2/emse2019/aggregated_full.zip
unzip aggregated_full.zip
```

After that you can just run the Plots_Tables jupyter notebook with default settings (just create the virtualenv like described in 2, then open the jupyter notebook and proceed with 2.2).


## 1. Raw data

This section provides information about how the raw data is extracted. As mentioned above this step is not mandatory to just reproduce the plots and figures.

### 1.1. Import MongoDB Data into local MongoDB

The MongoDB is provided as a ZIP file which can be extracted and dropped into a empty MongoDB installation. The data in the MongoDB is collected via [SmartSHARK](https://www.github.com/smartshark/). 
It can be reproduced via executing the SmartSHARK plugins vcsSHARK, issueSHARK, mecoSHARK, linkSHARK, and labelSHARK on all repositories. Be aware that this collects a large amount of metrics and PMD warnings for every file in every commit. This is a VERY time expensive operation.


```bash
wget http://www.user.informatik.uni-goettingen.de/~trautsch2/emse2019/mongodb.zip
```

### 1.2. Checkout Repositories

We need a checked out version of the repository to collect buildfile information.
The next steps expect the data in the repos folder.

```bash
# create python virtualenv for asatlib and install dependencies
cd asatlib
python -m venv .
source bin/actviate
pip install -r requirements.txt
```

```bash
# fetch tar.gz with repository from MongoDB gridfs and extract it to ../repos/
python get_repositories.py
```


### 1.3. Get commit path (list of commits) through the commit graph

This saves a pickled list of commits for further processing by the next steps.

```bash
python get_revisions.py
```

### 1.4. Get ASAT buildfile information about the changes in the path

This creates CSV files containing changes in buildfiles that are used in the next step and also in the Aggregation notebook to determine introduction commits and removal commits for supported ASATS.

```bash
python pmd_states_local.py
```

### 1.5. Extract ASAT warnings

This creates CSV files containing ASAT warnings of PMD together with metrics that utilize the previous buildfile information.

```bash
python main.py
```


## 2 Aggregation / Analysis

This section is completely based on jupyter notebooks.
The notebooks aggregate the data and generate the plots and tables used in the paper.
An additional notebook (Data_Enrichment.ipynb) provides the code for creating the supplemental plots on the website.

```bash
# create python virtualenv for the jupyter notebooks and install dependencies
cd notebooks
python -m venv .
source bin/activate
pip install -r requirements.txt

# execute jupyter lab
jupyter lab
```

### 2.1. Run all steps in the Aggregation notebook

This is the main aggregation step. The result are project specific pickle files (intermediate results) and one pickle file containing the resulting Pandas DataFrame. 


### 2.2. Run all steps in the Defect_Density notebook

This provides additional information about defects from the MongoDB and creates an additional CSV file.


### 2.2. Run all steps in the Plots_Tables notebook

This generates the plots and tables used in the paper utilizing the pickle file containing all projects and the defect information CSV file.
