
import pickle
import lxml
import subprocess
import copy
import timeit
import os

import pandas as pd

from util.buildfile import PomPom, MavenError

def get_states(project_name, revisions):
    path = '../repos/{}'.format(project_name)

    old_states = {}

    final_states = []
    error_states = []
    debug_output = []
    for (revision_hash, buildfiles) in revisions:

        try:
            # if this fails it is critical
            r = subprocess.run(['git', 'checkout', revision_hash, '-f'], cwd=path, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if r.returncode != 0:
                print('error')
                print(r.stderr)
                print(r.stdout)
                break

            p = PomPom(path, project_name, revision_hash)
            p.preflight_check()
            output, replacements = p.create_effective_pom()
            states = p.parse_effective_pom(output)

            if replacements:
                print('replacements needed: ', replacements)

            if not states:
                print('[{}] no data in pom'.format(revision_hash))

            if states != old_states:
                for name, state in states.items():
                    tmp = copy.deepcopy(state)
                    tmp['pom'] = name
                    tmp['revision'] = revision_hash

                    tmp['effective_rules'] = ','.join(tmp['rules'])
                    tmp['custom_rule_files'] = ','.join(tmp['custom_rule_files'])

                    tmp['file_excludes'] = ','.join(tmp['excludes'])
                    tmp['file_includes'] = ','.join(tmp['includes'])

                    tmp['root_excludes'] = ','.join(tmp['exclude_roots'])

                    final_states.append(tmp)
                # print('[{}] changes OK'.format(revision_hash))
                old_states = states
            else:
                pass
                # print('[{}] no changes OK'.format(revision_hash))
            debug_output.append((revision_hash, output, states))
        except OSError as e:
            print('[{}] OSError ({})'.format(revision_hash, e))
            error_states.append({'revision': revision_hash, 'error_type': 'OSError', 'line': 'pom.xml not found', 'output': ''})
        except lxml.etree.XMLSyntaxError as e:
            print('[{}] XMLSyntax Error'.format(revision_hash))
            error_states.append({'revision': revision_hash, 'error_type': 'XMLSyntaxError', 'line': str(e), 'output': ''})
        except MavenError as e:
            print('[{}] Maven Error ({}) "{}"'.format(revision_hash, e.type, e.line))
            if e.type == 'unknown':
                print(e.output)
            error_states.append({'revision': revision_hash, 'error_type': 'MavenError: ' + e.type, 'line': e.line, 'output': e.output})
        except Exception as e:
            print('[{}] {}'.format(revision_hash, e))
            raise
    return final_states, error_states, debug_output


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
        print('extracting: {}'.format(project_name))
        start = timeit.default_timer()

        changed_revisions = pickle.load(open('./data/{}_buildfile_changes.pickle'.format(project_name), 'rb'))

        states, error_states, debug = get_states(project_name, changed_revisions)

        dfs = pd.DataFrame(states)
        dfs['project'] = project_name
        dfs.to_csv('./data/{}_pmd_states6.csv'.format(project_name), index=False)

        dfe = pd.DataFrame(error_states)
        dfe['project'] = project_name
        dfe.to_csv('./data/{}_pmd_error_states6.csv'.format(project_name), index=False)

        end = timeit.default_timer() - start
        print("Finished pompom for {} in {:.5f}s".format(project_name, end))

if __name__ == '__main__':
    main()
