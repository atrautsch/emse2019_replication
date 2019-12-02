
import numpy as np


def levenshtein(prevs, currs):
    """Levenshtein distance metric implemented with Wagner-Fischer algorithm."""
    ops = []

    # trivial cases
    if not prevs:
        for cur in currs:
            ops.append('add:{}'.format(cur))
    if not currs:
        for prev in prevs:
            ops.append('del:{}'.format(prev))

    # 1. initialize matrix with words including 0 word
    rows = len(prevs) + 1
    cols = len(currs) + 1
    matrix = np.zeros((rows, cols))

    matrix[0] = range(cols)
    matrix[:, 0] = range(rows)

    # 2. fill matrix according to levenshtein rules
    for row in range(1, rows):
        for col in range(1, cols):
            # we skip 0 word with range(1, ) need to subtract again from word sequence
            prev = prevs[row - 1]
            curr = currs[col - 1]

            # if char is the same use character use previous diagonal element because nothing has changed
            if prev == curr:
                matrix[row, col] = matrix[row - 1, col - 1]

            # else use minval of upper, leftmost and previous diagonal element + 1
            else:
                # but we do not necessarily know which one
                # matrix[row, col - 1] insertions
                # matrix[row - 1, col] deletion
                # matrix[row - 1, col - 1] substitution
                minval = min(matrix[row, col - 1], matrix[row - 1, col], matrix[row - 1, col - 1])
                matrix[row, col] = minval + 1
    # print(matrix)

    distance = matrix[rows - 1, cols - 1]
    # operations by using the matrix again from bottom right to top left
    # https://stackoverflow.com/questions/41149377/extracting-operations-from-damerau-levenshtein

    row = rows - 1
    col = cols - 1

    last_traversal = None
    while row > 0 and col > 0:
        idx = min([matrix[row, col - 1], matrix[row - 1, col], matrix[row - 1, col - 1]])

        # es gibt kein minimum kleiner als aktuelle zelle und wir sind noch nicht am rand im nächsten schritt
        if idx == matrix[row, col] and not (row - 1 == 0 or col - 1 == 0):
            row -= 1
            col -= 1
            continue

        # wir sind am rand der matrix angekommen
        if row - 1 == 0 and not col -1 == 0: # oberer rand rest ist insert oder keine änderung
            last_traversal = 'left'
            if idx < matrix[row, col]:
                ops.append('add:{}'.format(currs[col - 1]))
            col -= 1
            continue
        if col - 1 == 0 and not row -1 == 0:  # unterer rand, rest ist delete oder keine änderung
            last_traversal = 'up'
            if idx < matrix[row, col]:
                ops.append('del:{}'.format(prevs[row - 1]))
            row -= 1
            continue
        if col - 1 == 0 and row - 1 == 0:  # ende erreicht, letzte änderung basiert auf unserer letzten operation, wenn es keine gab dann ist es eine subst
            if idx < matrix[row, col]:
                if last_traversal == 'up':
                    ops.append('del:{}'.format(prevs[row - 1]))
                elif last_traversal == 'left':
                    ops.append('add:{}'.format(currs[col - 1]))
                else:
                    # ops.append('substitution:{}->{}'.format(prevs[row - 1], currs[col - 1]))
                    ops.append('del:{}'.format(prevs[row - 1]))
                    ops.append('add:{}'.format(currs[col - 1]))
            col -= 1
            row -= 1
            continue

        # es gibt ein minimum dem wir folgen
        if idx < matrix[row, col]:
            # finden wir die richtung, präferenz deletion, insertion, substitution
            if matrix[row - 1, col] < matrix[row, col]:
                ops.append('del:{}'.format(prevs[row - 1]))
                row -= 1
            elif matrix[row, col - 1] < matrix[row, col]:
                ops.append('add:{}'.format(currs[col - 1]))
                col -= 1
            elif matrix[row - 1, col - 1] < matrix[row, col]:
                # ops.append('substitution:{}->{}'.format(prevs[row - 1], currs[col - 1]))
                ops.append('del:{}'.format(prevs[row - 1]))
                ops.append('add:{}'.format(currs[col - 1]))
                row -= 1
                col -= 1

    return distance, list(reversed(ops))
