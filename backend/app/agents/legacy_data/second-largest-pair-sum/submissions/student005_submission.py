# student005 - crashes with IndexError, no length guard
def find_second_largest(nums):
    unique_vals = sorted(set(nums), reverse=True)
    return unique_vals[1]          # BUG: no check for len < 2 -> IndexError, no ValueError


def count_pairs_with_sum(nums, target):
    count = 0
    n = len(nums)
    for i in range(n):
        for j in range(i + 1, n):
            if nums[i] + nums[j] == target:
                count += 1
    return count
