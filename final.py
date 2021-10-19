import numpy as np
image_list = []
from srgan import generator, discriminator
from train import SrganTrainer
import rasterio as rio
from common import resolve_single
from utils import load_image
from pathlib import Path

model_path = Path(__file__).absolute().parents[0].joinpath('gan_generator.h5')
gan_generator = generator()
gan_generator.load_weights(model_path)

def resolve_and_plot(lr):
    lr = load_image(lr).astype("float32")
    print(lr.shape)
    print("RESOLVE SINGLE STARTS")
    print(gan_generator)
    gan_sr = resolve_single(gan_generator, lr)
    print("RESOLVE SINGLE ENDS")
    images = [gan_sr]
    print("FINISHED")
    return np.moveaxis(np.array(images[0]), -1, 0).astype(rio.uint8)
