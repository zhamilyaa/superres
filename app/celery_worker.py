from celery import Celery

from config import settings

app = Celery('hello', )
app.config_from_object(settings.CELERY.config)


def main():
    app.start()
    pass

@app.task
def hello():
    return 'hello world'

@app.task
def add(x,y):
    return (x+y)

if __name__ == '__main__':
    main()


# from celery import Celery
#
# app = Celery('hello', broker='amqp://guest@localhost//')
#
# @app.task
# def hello():
#     return 'hello world'