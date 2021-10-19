import time

import celery

from app.celery_worker import app


@app.task(name='do_something', queue='do_something')
def do_something(*args, **kwargs):
    print(args)
    print(kwargs)
    time.sleep(5)
    return args, kwargs


def main():
    tasks = list()
    for i in range(1):
        task = do_something.s(i, i + 5, haha=f"{i * 10}_dee")
        tasks.append(task)
    results = celery.group(tasks).delay().get()
    print(len(results))
    for result in results:
        print(result)

    pass


if __name__ == '__main__':
    main()
