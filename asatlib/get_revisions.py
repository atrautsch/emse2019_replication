
import timeit
import pickle

from mongoengine import connect

from pycoshark.mongomodels import Project, VCSSystem

from util.path import get_commit_path
from util.asat_extraction import buildfile_changes

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
        print(project_name, end=' ')

        project = Project.objects.get(name=project_name)
        vcs_system = VCSSystem.objects.get(project_id=project.id)
        revisions = get_commit_path(vcs_system.id, last_commit=last_commit)

        changed_revisions = buildfile_changes(vcs_system, revisions)

        pickle.dump(revisions, open('./data/{}_revisions.pickle'.format(project_name), 'wb'))
        pickle.dump(changed_revisions, open('./data/{}_buildfile_changes.pickle'.format(project_name), 'wb'))

        end = timeit.default_timer() - start
        print('finished {} in {:.5f}'.format(project_name, end))

if __name__ == '__main__':
    main()
