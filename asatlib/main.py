
import timeit
import pickle

import pandas as pd
from mongoengine import connect

from pycoshark.mongomodels import Project, VCSSystem, IssueSystem

from util.path import get_commit_path
from util.asat_extraction import find_warning_changes, find_warning_changes2, calculate_issues, warnings_coarse

loc = {'host': '127.0.0.1',
       'port': 27017,
       'db': 'smartshark',
       'username': 'root',
       'password': '',
       'authentication_source': 'smartshark',
       'connect': False}
connect(**loc)


def main():
    full = [
        ('commons-bcel', None),
        ('commons-vfs', None),
        ('commons-jcs', None),
        ('commons-beanutils', None),
        ('commons-codec', None),
        ('commons-collections', None),
        ('commons-compress', None),
        ('commons-configuration', None),
        ('commons-dbcp', None),
        ('commons-digester', None),
        ('commons-imaging', None),
        ('commons-io', None),
        ('commons-jexl', None),
        ('commons-lang', None),
        ('commons-math', 'c4218b83851c8dba1f275e3095913d9636aa5000'),
        ('commons-net', None),
        ('commons-rdf', None),
        ('commons-scxml', None),
        ('commons-validator', None),
        ('falcon', None),
        ('jspwiki', None),
        ('kylin', None),
        ('mahout', None),
        ('pdfbox', None),
        ('ranger', None),
        ('struts', None),
        ('systemml', None),
        ('tez', None),
        ('tika', None),
        ('wss4j', None),
        ('eagle', None),
        ('cayenne', None),
        ('opennlp', None),
        ('calcite', None),
        ('zeppelin', None),
        ('flume', None),
        ('parquet-mr', None),
        ('storm', None),
        ('lens', None),
        ('knox', None),
        ('giraph', None),
        ('gora', None),
        ('helix', None),
        ('archiva', None),
        ('santuario-java', None),
        ('phoenix', None),
        ('manifoldcf', None),
        ('httpcomponents-client', None),
        ('httpcomponents-core', None),
        ('streams', None),
        ('mina-sshd', None),
        ('roller', None),
        ('jena', None),
        ('nifi', None),
    ]

    for project_name, last_commit in full:
        start = timeit.default_timer()
        project = Project.objects.get(name=project_name)
        vcs_system = VCSSystem.objects.get(project_id=project.id)

        revisions = pickle.load(open('./data/{}_revisions.pickle'.format(project_name), 'rb'))

        df = pd.read_csv('./data/{}_pmd_states6.csv'.format(project_name))
        poms = {}
        state = {}
        for revision in revisions:
            if revision in df[df['project'] == project_name]['revision'].unique():
                state = {}
                for pom in df[(df['project'] == project_name) & (df['revision'] == revision)]['pom'].unique():
                    if len(df[(df['project'] == project_name) & (df['revision'] == revision) & (df['pom'] == pom)]) > 1:
                        raise Exception('this should be unique')

                    ef = df[(df['project'] == project_name) & (df['revision'] == revision) & (df['pom'] == pom)]['effective_rules'].values[0]

                    if type(ef) != str:
                        ef = []
                    else:
                        ef = ef.split(',')

                    excludes = df[(df['project'] == project_name) & (df['revision'] == revision) & (df['pom'] == pom)]['file_excludes'].values[0]
                    if type(excludes) != str:
                        excl = []
                    else:
                        excl = excludes.split(',')

                    rexcludes = df[(df['project'] == project_name) & (df['revision'] == revision) & (df['pom'] == pom)]['root_excludes'].values[0]
                    if type(rexcludes) != str:
                        rexcl = []
                    else:
                        rexcl = rexcludes.split(',')

                    state[pom] = {
                        'source_directory': df[(df['project'] == project_name) & (df['revision'] == revision) & (df['pom'] == pom)]['source_directory'].values[0],
                        'file_excludes': excl,
                        'root_excludes': rexcl,
                        'effective_rules': ef,
                    }
            if state:
                poms[revision] = state
        print('extracting: {}'.format(project_name))
        coarse = warnings_coarse(revisions, vcs_system, poms=poms)
        dfs = pd.DataFrame(coarse)
        dfs['project'] = project_name
        dfs.to_csv('./data/{}_coarse5.csv'.format(project_name), index=False)
        end = timeit.default_timer() - start
        print('finished {} in {:.5f}'.format(project_name, end))

if __name__ == '__main__':
    main()
