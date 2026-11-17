

# 解决办法：先分配整数部分，再把剩余的分钱补给小数余数最大的用户就行了。如果权重都相同，就把剩下的钱发给靠前的用户

def split_pool(pool_cents: int, weights: list[int]) -> list[int]:

    if pool_cents < 0 or any(w < 0 for w in weights):
        raise ValueError("奖池和权重不能为负数")

    total = sum(weights)

    if total == 0:
        if pool_cents == 0:
            return [0] * len(weights)
        raise ValueError("权重总和不能为0")

    amounts = []
    remainders = []

    for w in weights:
        num_temp = pool_cents * w

        amounts.append(num_temp // total)
        remainders.append(num_temp % total)

    remaining = pool_cents - sum(amounts)

    def sort_key(i):
        return (-remainders[i], i)
    order = sorted(
        range(len(weights)),
        key=sort_key
    )


    for i in order[:remaining]:
        amounts[i] += 1

    return amounts

if __name__ == "__main__":
    result = split_pool(100, [1, 1, 1])

    print("每人分到：", result)
    print("实际总和：", sum(result))
    print("应有总和：", 100)

    assert sum(result) == 100, "分账错误"

    print("测试通过！")
