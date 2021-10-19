import celery
from app.celery_worker import app

@app.task(name = "new_tasks", queue = "new_tasks")
def add(x, y, **kwargs):
    return x * y, kwargs

@app.task(name = "mul", queue = "new_tasks")
def mul(x, y):
    return x * y

@app.task
def xsum(numbers):
    return sum(numbers)

def main():
    tasks = celery.group(add.s(5,2)).delay().get()
    # tasks = add.delay(2,2).get()
    #
    # tasks = add.apply_async((2,2)).get()
    # print(tasks)
    #
    #
    # print(add(2,2))
    #
    # res = add.delay(2,3)
    # print(res.get())
    #
    # print(type(res)) # <class 'celery.result.AsyncResult'>

    # res = add.s(2,2).delay()
    # print(res.get())
    #
    # s2 = add.s(3)
    # new = s2.delay(5).get()
    # print(new)

    res = add.s(2,3).delay()
    print(res.get())
    return

    chain = celery.chain(add.s(4,4, haha = "haha")).delay().get()
    print(chain)
    print(type(chain))
    group = celery.group(add.s(i,) for i in range(10))
    print(group(0).get()[0])


    return


    g = celery.group(add.s(i) for i in range(10))
    print(g(0).get())

    pass


if __name__ == '__main__':
    main()
