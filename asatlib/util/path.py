
from datetime import timedelta

import networkx as nx

from pycoshark.mongomodels import Commit, Branch


def get_vcs_graph(vcs_id):
    """Return NetworkX digraph structure from commits of this VCS."""
    g = nx.DiGraph()
    # first we add all nodes to the graph
    for c in Commit.objects.only('id', 'revision_hash').timeout(False).filter(vcs_system_id=vcs_id):
        g.add_node(c.revision_hash)

    # after that we draw all edges
    for c in Commit.objects.only('id', 'parents', 'revision_hash').timeout(False).filter(vcs_system_id=vcs_id):
        for p in c.parents:
            try:
                p1 = Commit.objects.only('id', 'revision_hash').timeout(False).get(vcs_system_id=vcs_id, revision_hash=p)
                g.add_edge(p1.revision_hash, c.revision_hash)
            except Commit.DoesNotExist:
                print("parent of a commit is missing (commit id: {} - revision_hash: {})".format(c.id, p))
                pass
    return g


def get_main_branch_tip(vcs_id):
    """Return revision of main branch tip of the repository: origin/head -> main branch of remote repo, usually origin/master."""
    b = Branch.objects.get(vcs_system_id=vcs_id, is_origin_head=True)
    c = Commit.objects.get(id=b.commit_id)
    return c.revision_hash


def get_orphan_commits(vcs_id):
    """Return a list of firts commit candidates, orphan commits ordered by date."""
    return Commit.objects.filter(vcs_system_id=vcs_id, parents__size=0).order_by('committer_date').only('revision_hash', 'committer_date')


def get_commit_path(vcs_id, last_commit=None):
    """Return a list of commits, the path from the origin/master to the oldest orphan commit."""
    g = get_vcs_graph(vcs_id)
    bt = last_commit
    if not bt:
        bt = get_main_branch_tip(vcs_id)
    path = None

    # get first commit without parents that has a path to main branch tip, by our ordering this is also the earliest
    for c in get_orphan_commits(vcs_id):
        if nx.has_path(g, c.revision_hash, bt):
            # paths = sorted(nx.all_shortest_paths(g, c.revision_hash, bt))
            # print('found {} paths from {} to {} ({})'.format(len(paths), c.revision_hash, bt, c.committer_date))
            # keep it deterministic, shortest_path returns one of the shortest path depending on the graph structure in memory
            # path = nx.shortest_path(g, c.revision_hash, bt)
            # path = paths[0]
            # path = sorted(nx.all_shortest_paths(g, c.revision_hash, bt))[0]
            path = nx.shortest_path(g, c.revision_hash, bt)
            break
    return path


def chunk_path(vcs_id, commits, window_size_days=119):
    """Return chunked paths of the given commit path."""
    date_cache = {}
    for c in Commit.objects.filter(vcs_system_id=vcs_id, revision_hash__in=commits).only('revision_hash', 'committer_date'):
        date_cache[c.revision_hash] = c.committer_date

    # discard first chunk
    start = None
    chunks = []
    current_chunk = []
    for commit in commits:
        if not start:
            start = date_cache[commit]
            current_chunk.append(commit)
            continue

        # we are over our window size, create new chunk
        if start + timedelta(days=window_size_days) < date_cache[commit]:
            chunks.append(current_chunk.copy())
            current_chunk = [commit]

        # we are within our window size append to chunk
        else:
            current_chunk.append(commit)

    return chunks
