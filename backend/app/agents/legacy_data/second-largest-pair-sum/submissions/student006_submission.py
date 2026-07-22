# student006 - infinite loop bug in count_pairs_with_sum (will time out)
def find_second_largest(nums):
    unique_vals = sorted(set(nums), reverse=True)
    if len(unique_vals) < 2:
        raise ValueError("Need at least 2 unique values")
    return unique_vals[1]


def count_pairs_with_sum(nums, target):
    count = 0
    n = len(nums)
    i = 0
    j = 1
    while i < n:                 # BUG: j and i never both advance correctly -> infinite loop
        if j < n:
            if nums[i] + nums[j] == target:
                count += 1
            j += 0  # forgot to increment j
        else:
            i += 1
            j = i + 1
    return count
