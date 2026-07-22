# student004 - double counts pairs (uses i <= j including self-pairing at times)
def find_second_largest(nums):
    unique_vals = sorted(set(nums), reverse=True)
    if len(unique_vals) < 2:
        raise ValueError("Need at least 2 unique values")
    return unique_vals[1]


def count_pairs_with_sum(nums, target):
    count = 0
    n = len(nums)
    for i in range(n):
        for j in range(n):        # BUG: should start at i+1, this double counts and self-pairs
            if i != j and nums[i] + nums[j] == target:
                count += 1
    return count // 1  # left as-is, still wrong (double counted)
