# 【修改：时长选填】模型按学习依赖分配日期；后端仅检查天数，不预测耗时。
"""day_number 从1开始，每项任务只归属一天，保留同一天内的原始顺序。"""
def allocate_tasks(tasks, days):
    if not tasks or not days:
        raise ValueError('任务和计划日期不能为空')
    output = [[] for _ in days]
    previous = 0
    for task in tasks:
        if not 1 <= task.day_number <= len(days):
            raise ValueError(f'任务所属天数超出计划范围：{task.title}')
        if task.day_number < previous:
            raise ValueError('请按照第1天至最后一天的学习顺序输出任务')
        previous = task.day_number
        output[task.day_number - 1].append(task)
    if len(tasks) >= len(days) and any(not items for items in output):
        raise ValueError('请将任务合理分配到每天，避免遗漏计划日期')
    return output
