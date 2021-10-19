import os
import sys
from pathlib import Path

import celery
from app.celery_worker import app
import logging
from final import resolve_and_plot
import rasterio
import tensorflow as tf
from utils import load_image
from srgan import generator, discriminator
from train import SrganTrainer

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

from celery import Task


# class NaiveAuthenticateServer(Task):
#     def __init__(self):
#         path = './'
#         gan_generator = generator()
#         gan_generator.load_weights(path + 'pre_generator.h5')
#         gan_trainer = SrganTrainer(generator=gan_generator, discriminator=discriminator())
#         gan_trainer.generator.save_weights(path + 'gan_generator.h5')
#         gan_trainer.discriminator.save_weights(path + 'gan_discriminator.h5')
#         pre_generator = generator()
#         gan_generator = generator()
#         pre_generator.load_weights(path + 'pre_generator.h5')
#         gan_generator.load_weights(path + 'gan_generator.h5')
#         self.gan_generator = gan_generator
#
#     @app.task(name="resolution", queue="resolution")
#     def run(self, image):
#         return resolve_and_plot(self, image)

class Resolution(Task):
    name = "resolution"
    queue = "resolution"

    def __init__(self):
        super(Resolution, self).__init__()
        self.model_path = Path(__file__).absolute().parents[2].joinpath('gan_generator.h5')


    def run(self, image):
        gan_generator = generator()
        gan_generator.load_weights(self.model_path)
        return resolve_and_plot(gan_generator, image)


resolution_task = Resolution()
app.tasks.register(resolution_task)


def main():
    logger.debug("EVERYTHINHG WORKS FINE")
    tiles_path = Path(__file__).absolute().parents[2].joinpath('tiles')
    print(tiles_path)

    tiles = os.listdir(tiles_path)
    hello = sorted(tiles, key=lambda k: int(k.split('_')[-1]))
    tiles = list()
    tasks = list()
    for i in range(5):
        hello_dir = os.path.join(str(tiles_path) + '/'+ hello[i])
        logger.debug(hello_dir)
        logger.debug(type(hello_dir))
        tiles.append(hello_dir)
        task = res.s(hello_dir)
        tasks.append(task)
    result = celery.group(tasks).delay().get()
    logger.debug(result) # list of arrays


    return



    logger.debug(type(tiles[0]))

    task = celery.group(res.delay(tiles[0]))
    logger.debug(task.get())
    logger.debug(type(task))
    return

    # task = resolution.s(hello_dir)
    # print(task.delay().get())
    hello_dir = load_image(hello_dir).astype('float32')
    print("THAT IS THE HELLO DIR")
    print(hello_dir)
    print(type(hello_dir))

    input = tf.expand_dims(hello_dir, axis=0)
    print("THAT IS THE INPUT")
    print(input)
    print(type(input))
    return
    cast = tf.cast(input, tf.float32)
    print("THAT IS THE CAST")
    print(cast)
    print(type(cast))
    return
    with rasterio.open(hello_dir) as dst:
        read = dst.read()
    print(read)

    task = celery.group(resolution.s(hello_dir))
    print(task.delay().get())
    print(hello)

    return
    hello = list()
    for i in range(1, 11):
        hello.append(i)
    print(hello)
    task = celery.group(resolution.s(hello)).delay().get()
    print(task)
    pass


if __name__ == '__main__':
    main()
