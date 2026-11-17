from datetime import date,datetime,timedelta

from pydantic import BaseModel, Field

class dayBudget(BaseModel):
    day:date
    num: list[int] = Field(default_factory=list)


class time_pydanic(BaseModel):
    days: list[dayBudget]=Field(min_length=1,max_length=10)

d1 = dayBudget(day="2026-04-03")

d = d1.model_dump(mode='json')
print(d)
#d2 = dayBudget(day=date(2026,5,1),num=3)
#d3 = dayBudget(day=date(2026,5,2),num=2)

#out = sorted([d1,d2,d3],key=lambda p: p.day)
#print(out)
print(d1)


#t2 = datetime()
#print(t1)
#print(t2)