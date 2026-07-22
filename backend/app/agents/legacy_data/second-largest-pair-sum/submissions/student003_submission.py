# student003 - does not de-duplicate before finding second largest
def find_second_largest(nums):
    ordered = sorted(nums, reverse=True)   # BUG: no set(), duplicates not removed
    if len(ordered) < 2:
        raise ValueError("Need at least 2 unique values")
    return ordered[1]


def count_pairs_with_sum(nums, target):
    count = 0
    n = len(nums)
    for i in range(n):
        for j in range(i + 1, n):
            if nums[i] + nums[j] == target:
                count += 1
    return count
