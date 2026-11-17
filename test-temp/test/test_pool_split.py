# 问题：
# Python 的 round() 是对每个人的份额分别四舍五入。假设奖池是 100 分，三个人权重相同：
# 100/33=33.333,每个人都被取整成 33 分。最终：33+33+33=99。因此，少发了 1 分。

def split_pool(pool_cents: int, weights: list[int]) -> list[int]:
    total = sum(weights)
    return [round(pool_cents * w / total) for w in weights]


if __name__ == "__main__":
    pool_cents = 100
    weights = [1, 1, 1]

    result = split_pool(pool_cents, weights)

    print("每人分到：", result)
    print("实际总和：", sum(result))
    print("应有总和：", pool_cents)

    if sum(result) != pool_cents:
        raise AssertionError("分账错误：分配金额之和不等于奖池总额")