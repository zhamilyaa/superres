from celery import Celery

from config import settings

app = Celery('tasks', )
app.config_from_object(settings.CELERY.config)


def main():
    app.start()
    pass


if __name__ == '__main__':
    main()
