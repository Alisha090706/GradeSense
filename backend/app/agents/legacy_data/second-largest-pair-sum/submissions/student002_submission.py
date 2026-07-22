# student002 - off-by-one: inner loop stops one index early, misses the final valid pair
def find_second_largest(nums):
    unique_vals = sorted(set(nums), reverse=True)
    if len(unique_vals) < 2:
        raise ValueError("Need at least 2 unique values")
    return unique_vals[1]


def count_pairs_with_sum(nums, target):
    count = 0
    n = len(nums)
    for i in range(n):
        for j in range(i + 1, n - 1):   # BUG: should be range(i + 1, n) -- excludes last index
            if nums[i] + nums[j] == target:
                count += 1
    return count
