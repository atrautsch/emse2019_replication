
from bson.objectid import ObjectId

from pycoshark.mongomodels import Commit, File, FileAction, Issue, Event, Hunk, CodeEntityState
from pycoshark.utils import java_filename_filter
from mongoengine.queryset.visitor import Q
from functools import reduce

from util.distance import levenshtein
from util.metrics import get_metrics, get_warnings, hunk_lines, get_warning_list, get_file_metrics
from util.pmd import PMD_RULES, PMD_SEVERITIES, PMD_SEVERITY_MATCH, PMD_GROUP_MATCH

# files extracted from previous run over extracted rule files
CORPUS_RULE_FILES = {
                'build-tools/src/main/resources/wss4j-pmd-ruleset.xml',
                'build-tools/cayenne-checkers/src/main/resources/cayenne-tests-pmd.xml',
                'src/conf/pmd.xml',
                'buildtools/src/main/resources/mahout-pmd-ruleset.xml',
                'pmd-ruleset.xml',
                'dev-support/ranger-pmd-ruleset.xml',
                'maven/src/main/resources/mahout-pmd-ruleset.xml',
                'etc/santuario-pmd-ruleset.xml',
                'etc/mahout-pmd-ruleset.xml',
                'src/conf/pmd-ruleset.xml',
                'pmd.xml',
                'sshd-pmd-ruleset.xml',
                'ranger-examples/dev-support/ranger-pmd-ruleset.xml',
                'build-tools/cayenne-checkers/src/main/resources/cayenne-pmd.xml',
                'build-tools/wss4j-pmd-ruleset.xml'}

OLD_NAMES = {'project.xml'}


def buildfile_changes(vcs_system, revisions, buildfile='pom.xml'):
    """Extract from each commit for the vcs_system if the buildfile was changed (added, deleted, moved, modified)."""
    changed_revisions = []
    for commit_rev in revisions:
        c = Commit.objects.get(revision_hash=commit_rev, vcs_system_id=vcs_system.id)

        changed_buildfiles = []
        for fa in FileAction.objects.filter(commit_id=c.id):
            old_file_path = ''
            file_path = File.objects.get(id=fa.file_id).path.lower()

            if fa.old_file_id:
                old_file_path = File.objects.get(id=fa.old_file_id).path.lower()

            # only build files recognized
            if file_path != buildfile and old_file_path != buildfile and not file_path.endswith('/{}'.format(buildfile)) and not old_file_path.endswith('/{}'.format(buildfile)):

                # we also continue if no old name pom.xml has changed
                if file_path not in OLD_NAMES and old_file_path not in OLD_NAMES:
                    continue

                # we still continue if a rule file has not changed
                if file_path not in CORPUS_RULE_FILES and old_file_path not in CORPUS_RULE_FILES:
                    continue

            changed_buildfiles.append(file_path)

        if changed_buildfiles:
            changed_revisions.append((commit_rev, changed_buildfiles))

    return changed_revisions


def calculate_issues(revisions, its, vcs):
    """Die Issue.created_at und Event.created_at sind in UTC (Apache Jira default ist UTC, kann aber auch vom Benutzer abhängen!).

    Commit.committer_date ist ebenfalls UTC.
    """
    results = []
    for revision in log_progress(revisions, every=1):
        c = Commit.objects.get(revision_hash=revision, vcs_system_id=vcs.id)
        timestep = c.committer_date  # UTC
        # timezone = c.committer_date_offset  # LOCAL TIMEZONE

        # get local timezone by adding / subtracting offset
        # timestep_local = timestep + timedelta(minutes=timezone)

        for iss in Issue.objects.filter(issue_system_id=its.id, created_at__lte=timestep):
            tmp = {'state': iss.status, 'type': iss.issue_type, 'priority': iss.priority, 'id': iss.external_id, 'created': iss.created_at, 'revision_hash': c.revision_hash, 'last_change': None, 'commit_date': c.committer_date, 'resolution': iss.resolution}  # set the current state incase nothing has changed

            # reapply changes done over time
            for event in Event.objects.filter(issue_id=iss.id, created_at__lte=timestep).order_by('created_at'):  # need ascending order to reconstruct values
                # set new values from the events before our timestep
                if event.status == 'status':
                    tmp['state'] = event.new_value
                elif event.status == 'resolution':
                    tmp['resolution'] = event.new_value
                elif event.status == 'issue_type':
                    tmp['type'] = event.new_value
                elif event.status == 'priority':
                    tmp['priority'] = event.new_value

                # last event
                tmp['last_change'] = event.created_at
            results.append(tmp)
    return results


def warnings_coarse(revisions, vcs, poms=None):
    """Just get the sum of all ASAT warnings including added, deleted files.

    We are discerning between test code and production code.
    """
    results = []
    for revision in revisions:
        commit = Commit.objects.get(revision_hash=revision, vcs_system_id=vcs.id)

        tmp = {'revision': revision, 'date': commit.committer_date}
        tmp.update(**{'code_' + r['abbrev']: 0 for r in PMD_RULES})
        tmp.update(**{'test_' + r['abbrev']: 0 for r in PMD_RULES})
        tmp.update(**{'effective_code_' + r['abbrev']: 0 for r in PMD_RULES})

        # todo: include other metrics?
        tmp['test_loc'] = 0
        tmp['code_loc'] = 0
        tmp['effective_code_loc'] = 0
        tmp['effective_rules'] = []

        # effective fiele ids given the projects pom.xml excludes, and source_directory
        effective_file_ids = []

        # each modules (pom in poms) has its own source directory
        source_dirs = []
        excludes = []
        exclude_roots = []

        # the revision is not there if the project did not start with an pom.xml
        if poms and revision in poms.keys():

            # for each commit we have, source_directory, test_source_directory, excludes
            for pom, state in poms[revision].items():

                tmp['effective_rules'] += state['effective_rules']

                # excludes need to be prefixed with source_directory
                for ef in state['file_excludes']:
                    if ef.endswith('.java'):
                        excludes.append((state['source_directory'] + '/' + ef))
                for er in state['root_excludes']:
                    exclude_roots.append(er)

                source_dirs.append(state['source_directory'])

        source_dirs = list(set(source_dirs))

        # this only is necessary if we have effective files (only if we can read the pom.xml)
        if len(source_dirs) > 0:
            query = reduce(lambda q1, q2: q1.__or__(q2), map(lambda source_dir: Q(long_name__startswith=source_dir), source_dirs))
            qry = CodeEntityState.objects.filter(id__in=commit.code_entity_states, ce_type='file', long_name__endswith='.java').filter(query)

            # this is not very secure and will break if we get ** and * in one expression
            full = []
            prefix = []
            suffix = []
            suffix_only = []
            prefix_only = []
            for e in excludes:
                if e.startswith('**'):
                    suffix_only.append(e.split('**')[-1])
                    continue
                if e.endswith('*'):
                    prefix_only.append(e.split('*')[-1])
                    continue
                if '**' in e:
                    prefix.append(e.split('**')[0])
                    suffix.append(e.split('**')[-1])
                    continue
                if '*' in e:
                    prefix.append(e.split('*')[0])
                    suffix.append(e.split('*')[-1])
                    continue
                full.append(e)

            for ces in qry.only('id', 'long_name'):
                if ces.long_name.startswith(tuple(exclude_roots)):
                    # print('ignore {} because of root exclude {}'.format(ces.long_name, exclude_roots))
                    continue
                if ces.long_name.startswith(tuple(prefix_only)):
                    # print('ignore {} because of prefix only exclude {}'.format(ces.long_name, prefix_only))
                    continue
                if ces.long_name.endswith(tuple(suffix_only)):
                    # print('ignore {} because of suffix only exclude {}'.format(ces.long_name, suffix_only))
                    continue
                if ces.long_name in full:
                    # print('ignore {} because of full exclude {}'.format(ces.long_name, full))
                    continue
                for p, s in zip(prefix, suffix):
                    if ces.long_name.startswith(p) and ces.long_name.endswith(s):
                        # print('ignore {} because of prefix {} - suffix {} exclude'.format(ces.long_name, p, s))
                        continue

                effective_file_ids.append(ces.id)

        # get all java files, check for test, documentation, generated or other exclusions
        code_file_ids = []
        test_file_ids = []
        for ces in CodeEntityState.objects.filter(id__in=commit.code_entity_states, ce_type='file', long_name__endswith='.java').only('id', 'long_name'):
            if java_filename_filter(ces.long_name, production_only=True):
                code_file_ids.append(ces.id)
            else:
                test_file_ids.append(ces.id)

        # code_files = CodeEntityState.objects.filter(id__in=commit.code_entity_states, ce_type='file', long_name__endswith='.java', long_name__not__icontains='/test/').only('id', 'long_name')
        # code_file_ids = [ObjectId(cesf.id) for cesf in code_files]

        # test_files = CodeEntityState.objects.filter(id__in=commit.code_entity_states, ce_type='file', long_name__endswith='.java', long_name__icontains='/test/').only('id')
        # test_file_ids = [ObjectId(cesf.id) for cesf in test_files]

        # detailed warnings, grouped by type of the warning
        code_warnings = get_warning_list(code_file_ids)
        test_warnings = get_warning_list(test_file_ids)
        effective_code_warnings = get_warning_list(effective_file_ids)

        code_metrics = get_file_metrics(code_file_ids)
        test_metrics = get_file_metrics(test_file_ids)
        effective_code_metrics = get_file_metrics(effective_file_ids)

        for w in code_warnings:
            tmp['code_' + w['type']] += w['sum']
        for w in test_warnings:
            tmp['test_' + w['type']] += w['sum']
        for w in effective_code_warnings:
            tmp['effective_code_' + w['type']] += w['sum']

        # general info
        tmp['code_files'] = len(code_file_ids)
        tmp['test_files'] = len(test_file_ids)
        tmp['effective_code_files'] = len(effective_file_ids)

        if 'file_loc_sum' in code_metrics.keys():
            tmp['code_loc'] = code_metrics['file_loc_sum']
            tmp['code_mccc'] = code_metrics['file_mccc_sum']
            tmp['code_lloc'] = code_metrics['file_lloc_sum']

        if 'file_loc_sum' in test_metrics.keys():
            tmp['test_loc'] = test_metrics['file_loc_sum']
            tmp['test_mccc'] = test_metrics['file_mccc_sum']
            tmp['test_lloc'] = test_metrics['file_lloc_sum']

        if 'file_loc_sum' in effective_code_metrics.keys():
            tmp['effective_code_loc'] = effective_code_metrics['file_loc_sum']
            tmp['effective_code_mccc'] = effective_code_metrics['file_mccc_sum']
            tmp['effective_code_lloc'] = effective_code_metrics['file_lloc_sum']

        # rejoin to string because of saving in csv
        tmp['effective_rules'] = ','.join(set(tmp['effective_rules']))

        results.append(tmp)
    return results


def find_warning_changes2(revisions):
    """Find deltas of warnings between consecutive revisions."""
    results = []

    # for each revision in our history
    for i, revision in enumerate(log_progress(revisions, every=1)):

        # first commit skip the the next
        if not i:
            continue

        commit = Commit.objects.get(revision_hash=revision)
        previous_commit = Commit.objects.get(revision_hash=revisions[i - 1])

        # for each file in the revision
        for fa in FileAction.objects.filter(commit_id=commit.id):
            cdata = {}
            cdata.update(**{r['abbrev']: 0 for r in PMD_RULES})  # init PMD counts
            cdata.update(**{'method_lloc_sum': 0, 'method_lloc_avg': 0, 'method_mccc_sum': 0, 'method_mccc_avg': 0, 'method_mims_sum': 0, 'method_mims_avg': 0, 'nr_methods': 0, 'file_path': None, 'change_location': None})  # init metrics and meta data

            f1 = File.objects.get(id=fa.file_id)
            f2 = None

            old_file = f1
            if fa.old_file_id:
                f2 = File.objects.get(id=fa.old_file_id)
                old_file = f2

            # only java files
            if not f1.path.lower().endswith('.java') or not old_file.path.lower().endswith('.java'):
                continue

            check_id = ObjectId(f1.id)
            cdata['file_path'] = f1.path
            cdata['change_location'] = 'code'
            if '/test/' in f1.path:
                cdata['change_location'] = 'test'

            # only modifications no delete or add operations
            if fa.mode.lower() != 'm':
                continue

            # need to aggregate the quality metrics here
            if f1.path.lower().endswith('.java') and old_file.path.lower().endswith('.java'):
                metrics = get_metrics(previous_commit, commit, f1, old_file)
                for k, v in metrics.items():
                    cdata[k] += v

            warnings_current = get_warnings(commit, f1.path)
            warnings_previous = get_warnings(previous_commit, old_file.path)

            added_warnings = []
            deleted_warnings = []

            # find narrowest CES for each hunk line?
            # find narrowest CES for each line
            for hunk in Hunk.objects.filter(file_action_id=fa.id):
                lines_added, lines_deleted = hunk_lines(hunk)

                added_warnings = []
                deleted_warnings = []
                for k, v in warnings_current.items():
                    tmp = k.split(':')
                    added_warnings.append(tmp[2])
                for k2, v2 in warnings_previous.items():
                    tmp2 = k2.split(':')
                    deleted_warnings.append(tmp2[2])

                distance, obs = levenshtein(deleted_warnings, added_warnings)
                if distance > 0 and not obs:
                    print('error: distance > 0 and no ops')
                    print(deleted_warnings)
                    print(added_warnings)
                    print(obs)
                    print('--')
                if distance > 0:
                    for o in obs:
                        tmp = o.split(':')
                        if tmp[0] == 'add':
                            cdata[tmp[1]] += 1
                        elif tmp[0] == 'del':
                            cdata[tmp[1]] -= 1
                        else:
                            print('error no such op')
            # each change to a file for each revision
            results.append(cdata)
    return results


def find_warning_changes(revisions):
    """Find deltas of warnings between consecutive revisions."""
    linter_filter = []
    results = []

    # global state, overall deltas
    state = {}
    state.update(**{'global_' + r['abbrev']: 0 for r in PMD_RULES})
    state.update(**{'global_method_lloc_sum': 0, 'global_method_lloc_avg': 0, 'global_method_mccc_sum': 0, 'global_method_mccc_avg': 0, 'global_method_mims_sum': 0, 'global_method_mims_avg': 0, 'global_nr_methods': 0})

    for i, revision in enumerate(log_progress(revisions, every=1)):
        commit = Commit.objects.get(revision_hash=revision)
        previous_commit = Commit.objects.get(revision_hash=revisions[i - 1])

        # print(revision, commit.parents)

        cdata = {}
        cdata.update(**{r['abbrev']: 0 for r in PMD_RULES})
        cdata.update(**{'method_lloc_sum': 0, 'method_lloc_avg': 0, 'method_mccc_sum': 0, 'method_mccc_avg': 0, 'method_mims_sum': 0, 'method_mims_avg': 0, 'nr_methods': 0, 'file_path': None, 'change_location': None})

        for fa in FileAction.objects.filter(commit_id=commit.id):
            f1 = File.objects.get(id=fa.file_id)
            f2 = None

            old_file = f1
            if fa.old_file_id:
                f2 = File.objects.get(id=fa.old_file_id)
                old_file = f2

            # only java files
            if not f1.path.lower().endswith('.java') or not old_file.path.lower().endswith('.java'):
                continue

            check_id = ObjectId(f1.id)
            cdata['file_path'] = f1.path
            cdata['change_location'] = 'code'
            if '/test/' in f1.path:
                cdata['change_location'] = 'test'

            # only modifications no delete or add operations
            if fa.mode.lower() != 'm':
                continue

            # need to aggregate the quality metrics here
            if f1.path.lower().endswith('.java') and old_file.path.lower().endswith('.java'):
                metrics = get_metrics(previous_commit, commit, f1, old_file)
                for k, v in metrics.items():
                    cdata[k] += v

            warnings_current = get_warnings(commit, f1.path)
            warnings_previous = get_warnings(previous_commit, old_file.path)

            added_warnings = []
            deleted_warnings = []

            # find narrowest CES for each hunk line?
            # find narrowest CES for each line
            for hunk in Hunk.objects.filter(file_action_id=fa.id):
                lines_added, lines_deleted = hunk_lines(hunk)

                added_warnings = []
                deleted_warnings = []
                for k, v in warnings_current.items():
                    tmp = k.split(':')
                    added_warnings.append(tmp[2])
                for k2, v2 in warnings_previous.items():
                    tmp2 = k2.split(':')
                    deleted_warnings.append(tmp2[2])

                distance, obs = levenshtein(deleted_warnings, added_warnings)
                if distance > 0 and not obs:
                    print('error: distance > 0 and no ops')
                    print(deleted_warnings)
                    print(added_warnings)
                    print(obs)
                    print('--')
                if distance > 0:
                    for o in obs:
                        tmp = o.split(':')
                        if tmp[0] == 'add':
                            cdata[tmp[1]] += 1
                        elif tmp[0] == 'del':
                            cdata[tmp[1]] -= 1
                        else:
                            print('error no such op')
        for k, v in cdata.items():
            if k not in ['file_path', 'change_location']:
                state['global_' + k] += v

        cdata.update(**state)

        results.append(cdata)
    return results


def log_progress(results, every):
    """Dummy offline no-notebook log_progress."""
    return results
