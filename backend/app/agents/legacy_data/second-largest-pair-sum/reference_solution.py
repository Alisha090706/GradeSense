"""
Reference solution for the demo assignment.

Assignment brief given to students:

    Implement two functions:

    1. find_second_largest(nums: list[int]) -> int
       Return the second largest UNIQUE value in nums.
       Raise ValueError if nums has fewer than 2 unique values.

    2. count_pairs_with_sum(nums: list[int], target: int) -> int
       Return the number of index pairs (i, j) with i < j such that
       nums[i] + nums[j] == target.
"""


def find_second_largest(nums):
    unique_vals = sorted(set(nums), reverse=True)
    if len(unique_vals) < 2:
        raise ValueError("Need at least 2 unique values")
    return unique_vals[1]


def count_pairs_with_sum(nums, target):
    count = 0
    n = len(nums)
    for i in range(n):
        for j in range(i + 1, n):
            if nums[i] + nums[j] == target:
                count += 1
    return count
