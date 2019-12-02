
from pycoshark.mongomodels import Project, VCSSystem, Commit, File, CodeEntityState, FileAction, Issue, Hunk
from pycoshark.utils import jira_is_resolved_and_fixed, java_filename_filter
from util.pmd import PMD_RULES


def get_modified_files(commit, parent):
    """Return only modified files that were available in both parent and current commit."""
    modified_files = []
    modified_lines = 0
    for fa in FileAction.objects.filter(commit_id=commit.id, mode='M', parent_revision_hash=parent.revision_hash):
        f = File.objects.get(id=fa.file_id)

        if not java_filename_filter(f.path, production_only=True):
            continue

        modified_lines += fa.lines_added
        modified_lines += fa.lines_deleted
        modified_files.append(f.path)
    return modified_files, modified_lines


def get_file_warnings(commit, parent, modified_files):

    file_warnings_current = {d['abbrev']: 0 for d in PMD_RULES}
    file_warnings_parent = {d['abbrev']: 0 for d in PMD_RULES}

    for ces_current in CodeEntityState.objects.filter(id__in=commit.code_entity_states, ce_type='file', long_name__in=modified_files):
        for l in ces_current.linter:
            file_warnings_current[l['l_ty']] += 1

    for ces_parent in CodeEntityState.objects.filter(id__in=parent.code_entity_states, ce_type='file', long_name__in=modified_files):
        for l in ces_parent.linter:
            file_warnings_parent[l['l_ty']] += 1

    return file_warnings_current, file_warnings_parent


def hunk_lines(hunk):
    lno = hunk.new_start - 1
    dlno = hunk.old_start - 1

    lines_added = []
    lines_deleted = []

    for l in hunk.content.split('\n'):
        if not l:
            continue
        if not l.startswith('-'):
            lno += 1
            lines_added.append((lno, l))
        if not l.startswith('+'):
            dlno += 1
            if l.startswith('-'):
                lines_deleted.append((dlno, l))
    return lines_added, lines_deleted


def get_inducing_warnings(commit, parent):

    inducing = {d['abbrev']: 0 for d in PMD_RULES}
    inducing['LLOC'] = 0

    fixing = {d['abbrev']: 0 for d in PMD_RULES}
    fixing['LLOC'] = 0

    sum_matched_lines = 0
    match_lines = []
    for fa in FileAction.objects.filter(commit_id=commit.id, mode='M', parent_revision_hash=parent.revision_hash).timeout(False):
        f = File.objects.get(id=fa.file_id)

        if not java_filename_filter(f.path, production_only=True):
            continue

        # get warning that match for this file
        ces = CodeEntityState.objects.get(id__in=commit.code_entity_states, ce_type='file', long_name=f.path)

        # only matched ces with LLoC?
        fixing_linter_warnings = {}
        for lw in ces.linter:
            if lw['l_ty'] not in fixing_linter_warnings.keys():
                fixing_linter_warnings[lw['l_ty']] = []
            fixing_linter_warnings[lw['l_ty']].append(lw['ln'])

        # if we do not find inducing for this fa we skip?
        # do we skip if we do not find clear inducing for every fa of the commit?
        matched_lines = {}

        for h in Hunk.objects.filter(file_action_id=fa.id):
            _, lines_deleted = hunk_lines(h)
            for line_number, line_content in lines_deleted:
                key = line_content[1:].strip()
                if len(key) > 3 and key not in matched_lines.keys():
                    matched_lines[key] = [line_number]

        # get inducing changes
        for ifa in FileAction.objects.filter(induces__match={'change_file_action_id': fa.id}).timeout(False):
            inducing_file = File.objects.get(id=ifa.file_id)

            for ind in ifa.induces:
                if ind['change_file_action_id'] != fa.id:
                    continue
                if ind['label'] != 'JLMIV+' or ind['szz_type'] == 'hard_suspect':
                    continue

                # inducing commit for CES
                ic = Commit.objects.get(id=ifa.commit_id)

                # get warning that match for this file
                ces = CodeEntityState.objects.get(id__in=ic.code_entity_states, ce_type='file', long_name=inducing_file.path)

                inducing_linter_warnings = {}
                for lw in ces.linter:
                    if lw['l_ty'] not in inducing_linter_warnings.keys():
                        inducing_linter_warnings[lw['l_ty']] = []
                    inducing_linter_warnings[lw['l_ty']].append(lw['ln'])

                # get inducing hunks
                for h in Hunk.objects.filter(file_action_id=ifa.id):
                    lines_added, _ = hunk_lines(h)
                    for line_number, line_content in lines_added:
                        key = line_content[1:].strip()
                        if key not in matched_lines.keys():
                            continue

                        # we have a match!
                        matched_lines[key].append(line_number)

                        for wtype, lines in inducing_linter_warnings.items():
                            if line_number in lines:
                                inducing[wtype] += 1

                        for wtype, lines in fixing_linter_warnings.items():
                            if matched_lines[key][0] in lines:
                                fixing[wtype] += 1

        for key, lines in matched_lines.items():
            if len(lines) > 1:
                sum_matched_lines += 1
                match_lines.append(key)
    return fixing, inducing, sum_matched_lines, match_lines


def get_file_ids(commit, parent):
    file_ids = []
    for fa in FileAction.objects.filter(commit_id=commit.id, mode='M', parent_revision_hash=parent.revision_hash):
        f = File.objects.get(id=fa.file_id)
        if not java_filename_filter(f.path, production_only=True):
            continue
        file_ids.append(f.id)
    return file_ids


def get_subfile_metrics(commit, parent):
    file_ids = get_file_ids(commit, parent)

    subfile_metrics_current = {}
    subfile_metrics_parent = {}

    for ces_current_subfile in CodeEntityState.objects.filter(id__in=commit.code_entity_states, ce_type__in=['method', 'class'], file_id__in=file_ids):
        for metric, value in ces_current_subfile.metrics.items():
            if metric not in subfile_metrics_current.keys():
                subfile_metrics_current[metric] = []
            subfile_metrics_current[metric].append(value)
    subfile_sums_current = {k: sum(v) for k, v in subfile_metrics_current.items()}

    for ces_parent_subfile in CodeEntityState.objects.filter(id__in=parent.code_entity_states, ce_type__in=['method', 'class'], file_id__in=file_ids):
        for metric, value in ces_parent_subfile.metrics.items():
            if metric not in subfile_metrics_parent.keys():
                subfile_metrics_parent[metric] = []
            subfile_metrics_parent[metric].append(value)
    subfile_sums_parent = {k: sum(v) for k, v in subfile_metrics_parent.items()}

    return subfile_sums_current, subfile_sums_parent


def get_file_metrics(commit, parent, modified_files):

    file_metrics_current = {}
    file_metrics_parent = {}

    for ces_current in CodeEntityState.objects.filter(id__in=commit.code_entity_states, ce_type='file', long_name__in=modified_files):
        for metric, value in ces_current.metrics.items():
            if metric not in file_metrics_current.keys():
                file_metrics_current[metric] = []
            file_metrics_current[metric].append(value)

    for ces_parent in CodeEntityState.objects.filter(id__in=parent.code_entity_states, ce_type='file', long_name__in=modified_files):
        for metric, value in ces_parent.metrics.items():
            if metric not in file_metrics_parent.keys():
                file_metrics_parent[metric] = []
            file_metrics_parent[metric].append(value)

    file_sums_parent = {k: sum(v) for k, v in file_metrics_parent.items()}
    file_sums_current = {k: sum(v) for k, v in file_metrics_current.items()}

    return file_sums_current, file_sums_parent


def extract_project_fixed_asats(project_name):
    p = Project.objects.get(name=project_name)
    vcs = VCSSystem.objects.get(project_id=p.id)

    deltas = []
    for c in Commit.objects.filter(vcs_system_id=vcs.id, fixed_issue_ids__0__exists=True).only('id', 'message', 'parents', 'revision_hash', 'fixed_issue_ids', 'committer_date').timeout(False):

        all_fixed_issues = set()
        for issue in Issue.objects.filter(id__in=c.fixed_issue_ids):
            if issue.issue_type_verified and issue.issue_type_verified.lower() == "bug" and jira_is_resolved_and_fixed(issue):
                all_fixed_issues.add(issue)

        if len(all_fixed_issues) == 0:
            continue

        for parent in c.parents:
            delt = {'commit': c.revision_hash, 'parent': parent, 'date': c.committer_date, 'project': project_name, 'num_parents': len(c.parents), 'message': c.message}
            p = Commit.objects.get(vcs_system_id=vcs.id, revision_hash=parent)

            modified_files, modified_lines = get_modified_files(c, p)

            delt['num_files'] = len(modified_files)
            delt['num_lines'] = modified_lines

            fc = Commit.objects.get(id=c.id)
            current_file, parent_file = get_file_warnings(fc, p, modified_files)

            fixing, inducing, number_matched_lines, matched_lines = get_inducing_warnings(fc, p)
            delt['num_matched_lines'] = number_matched_lines
            delt['matched_lines'] = '\n'.join(matched_lines)

            for metric in current_file.keys():
                delt['bugfix_sum_' + metric] = current_file[metric] - parent_file[metric]

            for metric in fixing.keys():
                delt['delta_' + metric] = fixing[metric] - inducing[metric]
                delt['fixing_' + metric] = fixing[metric]
                delt['inducing_' + metric] = inducing[metric]

            deltas.append(delt)
    return deltas


def extract_project_all_deltas(project_name, get_categories):
    p = Project.objects.get(name=project_name)
    vcs = VCSSystem.objects.get(project_id=p.id)

    deltas = []
    for c in Commit.objects.filter(vcs_system_id=vcs.id).only('id', 'parents', 'revision_hash', 'committer_date', 'message').timeout(False):

        # skip merge commits
        if len(c.parents) > 1:
            continue

        # msg = filter_commit_message(c.message)

        for parent in c.parents:
            delt = {'commit': c.revision_hash, 'parent': parent, 'date': c.committer_date, 'project': project_name, 'num_parents': len(c.parents), 'message': c.message}

            # add keywords vector
            delt.update(**get_categories(c.message))

            p = Commit.objects.get(vcs_system_id=vcs.id, revision_hash=parent)
            fc = Commit.objects.get(id=c.id)  # need full commit here for code entity states

            modified_files, modified_lines = get_modified_files(c, p)

            delt['num_files'] = len(modified_files)
            delt['num_lines'] = modified_lines

            current_sums, parent_sums = get_subfile_metrics(fc, p)
            current_file, parent_file = get_file_metrics(fc, p, modified_files)

            current_metric = {}
            parent_metric = {}

            current_metric.update(**current_file)
            current_metric.update(**current_sums)

            parent_metric.update(**parent_file)
            parent_metric.update(**parent_sums)

            if len(current_metric.keys() ^ parent_metric.keys()) > 0:
                # print('found a difference in metrics! revision {}, skipping'.format(c.revision_hash))
                # print(current_metric.keys() ^ parent_metric.keys())
                # print(len(current_metric.keys()), len(parent_metric.keys()))
                continue

            for metric in current_metric.keys():
                delt[metric] = current_metric[metric] - parent_metric[metric]

            deltas.append(delt)
    return deltas
