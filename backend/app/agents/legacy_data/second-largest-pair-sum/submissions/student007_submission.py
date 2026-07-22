# student007 - correct second_largest, but pairs counted with a set() so duplicates collapse
def find_second_largest(nums):
    unique_vals = sorted(set(nums), reverse=True)
    if len(unique_vals) < 2:
        raise ValueError("Need at least 2 unique values")
    return unique_vals[1]


def count_pairs_with_sum(nums, target):
    seen = set(nums)               # BUG: collapses duplicates, undercounts pairs like [2,2,2]
    count = 0
    seen_list = list(seen)
    n = len(seen_list)
    for i in range(n):
        for j in range(i + 1, n):
            if seen_list[i] + seen_list[j] == target:
                count += 1
    return count
