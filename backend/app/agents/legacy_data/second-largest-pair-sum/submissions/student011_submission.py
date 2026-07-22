# student011 - fully correct, slightly different but valid style (for demo diversity)
def find_second_largest(nums):
    if len(set(nums)) < 2:
        raise ValueError("Need at least 2 unique values")
    top, second = float("-inf"), float("-inf")
    for v in set(nums):
        if v > top:
            top, second = v, top
        elif top > v > second:
            second = v
    return second


def count_pairs_with_sum(nums, target):
    total = 0
    for i in range(len(nums)):
        for j in range(i + 1, len(nums)):
            if nums[i] + nums[j] == target:
                total += 1
    return total
