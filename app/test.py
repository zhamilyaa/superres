import shutil
import sys

import geopandas as gpd
import shapely.wkt as shwkt
import shapely.wkt
import shapely.geometry as shg
import os
from itertools import product
import rasterio as rio
from rasterio import windows

from config import settings
from final import resolve_and_plot
import numpy as np
from scipy import ndimage
from shapely.geometry import box, Polygon, MultiPolygon, GeometryCollection, Point
import logging
import geopandas
import fiona
import rasterio.mask
import hashlib
from box import Box
import pickle
from rasterio.merge import merge as merge_tool
from pathlib import Path
import json

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

from flask import Flask, render_template, request, render_template_string

app = Flask(__name__)
path = Path(__file__).absolute().parents[1]
storage_folder = Path(settings.PROJECT.dirs.sr_folder)
# storage_folder = path


# CROP POLYGON GEOJSON FROM FP2 FILE
def crop(polygon: shg.Polygon, image_path, image_crs):
    new_name = hashlib.md5((str(image_path)+str(polygon)).encode('utf-8')).hexdigest()

    working_folder = Path(storage_folder.joinpath(str(new_name))).absolute()
    working_folder.mkdir(exist_ok=True)

    geom = gpd.GeoSeries([polygon], crs='epsg:3857')
    geom_path = working_folder.joinpath(f'{new_name}.geojson')
    geom.to_file(str(geom_path), driver='GeoJSON')

    converted_image_path = working_folder.joinpath(f'{new_name}.tiff')
    write = f'gdalwarp -overwrite -r cubic {str(image_path)} {converted_image_path} -s_srs {image_crs} -t_srs {image_crs}'
    print(write)
    os.system(write)

    tiles_folder = Path(storage_folder.joinpath(str(new_name)+'_cropped_tci')).absolute()
    tiles_folder.mkdir(exist_ok=True)
    cropped_image_path = tiles_folder.joinpath(f'{new_name}_cropped.tiff')
    crop_alpha = f'gdalwarp -overwrite -cutline {geom_path} -crop_to_cutline -r cubic -dstalpha -t_srs EPSG:3857 {converted_image_path} {cropped_image_path}'
    os.system(crop_alpha)

    with rasterio.open(cropped_image_path) as src:
        meta = src.meta

    meta.update(nodata=255)
    export_to_tiff_light(cropped_image_path, meta)

    processed_path = tiles_folder.joinpath(f'{new_name}_final.tiff')
    change_epsg = f'gdal_translate -b 1 -b 2 -b 3 -of GTiff -a_srs EPSG:3857 {cropped_image_path} {processed_path}'
    os.system(change_epsg)
    shutil.rmtree(working_folder, ignore_errors=True)
    return processed_path


# SPLIT POLYGON INTO MANY POLYGONS
def katana(geometry, threshold, count=0):
    """Split a Polygon into two parts across it's shortest dimension"""
    bounds = geometry.bounds
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]

    if max(width, height) <= threshold or count == 250:
        # either the polygon is smaller than the threshold, or the maximum
        # number of recursions has been reached
        return [geometry]
    if height >= width:
        # split left to right
        a = box(bounds[0], bounds[1], bounds[2], bounds[1] + height / 2)
        b = box(bounds[0], bounds[1] + height / 2, bounds[2], bounds[3])
    else:
        # split top to bottom
        a = box(bounds[0], bounds[1], bounds[0] + width / 2, bounds[3])
        b = box(bounds[0] + width / 2, bounds[1], bounds[2], bounds[3])
    result = []

    for d in (a, b,):
        c = geometry.intersection(d)
        if not isinstance(c, GeometryCollection):
            c = [c]
        for e in c:
            if isinstance(e, (Polygon, MultiPolygon)):
                result.extend(katana(e, threshold, count + 1))

    if count > 0:
        return result
    # convert multipart into singlepart
    final_result = []
    for g in result:
        if isinstance(g, MultiPolygon):
            final_result.extend(g)
        else:
            final_result.append(g)
    return final_result


# EROSION
def export_to_tiff(name, meta):

    with rio.open(name) as a:
        mask = a.read()
        mask = np.where(mask.sum(axis=0) >= 251*3, 0, 1)
        res = ndimage.binary_erosion(mask, structure=np.ones((51, 51)))
        zh = np.where(res == 1, a.read(), 255)
        meta.update(nodata=255)

    with rio.open(name, 'w', **meta) as dst:
        dst.write(np.array(zh).astype(rio.uint8))
        print("salem", meta)

    return np.array(zh).astype(rio.uint8)



# def export_to_tiff_light(name, meta):
#     with rio.open(name) as a:
#         mask = a.read()
#         mask = np.where(mask.sum(axis=0) == 0, 0, 1)
#         res = ndimage.binary_erosion(mask, structure=np.ones((23, 23)))
#         zh = np.where(res == 1, a.read(), 255)
#
#     with rio.open(name, 'w', **meta) as dst:
#         print(meta)
#         dst.write(np.array(zh))
#
#     return np.array(zh)

def export_to_tiff_light(name, meta):
    meta.update(nodata=255)
    with rio.open(name) as a:
        mask = a.read()
        print(mask.shape)
        mask = np.where(mask.sum(axis=0) == 0, 255, a.read())

    with rio.open(name, 'w', **meta) as dst:
        print(meta)
        dst.write(np.array(mask))

    return np.array(mask)




def perform_merge(dss, method='last', **kwargs):
    num_datasets = len(dss)
    print("SHAPE", dss[0].shape)
    mem_files = [rasterio.MemoryFile() for _ in range(num_datasets)]
    mem_datasets = [mem_file.open(**Box(ds.meta) + dict(count=3, driver='GTiff'))
                    for mem_file, ds in zip(mem_files, dss)]
    print("MEM DATASETS", type(mem_datasets[0]))
    for i, (mem_dataset, ds) in enumerate(zip(mem_datasets, dss)):
        print(f'Reading data {i + 1}/{num_datasets} with shape {ds.shape}')
        data_ = ds.read()
        print(f'Writing to memory {i + 1}/{num_datasets}')
        mem_dataset.write(data_)
    data, transform = rasterio.merge.merge(dss, method=method, **kwargs)
    for mem_dataset, mem_file in zip(mem_datasets, mem_files):
        mem_dataset.close()
        mem_file.close()
    return Box(data=data, transform=transform)


@app.route('/')
def form():
    return render_template('form.html')

def merge(folder_path, merged_path, hash_name):
    folder = dict(results=str(folder_path))
    sm = folder['results']
    to_text = f'ls {sm}/*.tiff > {merged_path}/{hash_name}.txt'
    os.system(to_text)
    merging = f'gdal_merge.py -ot Byte -of GTiff -n 255 -o {merged_path}/{hash_name}.tiff --optfile {merged_path}/{hash_name}.txt'
    os.system(merging)
    os.remove(f'{merged_path}/{hash_name}.txt')
    return

def do_sr(geometry, tci_path):
    polygon = shapely.wkt.loads(geometry)
    with rasterio.open(tci_path) as ds:
        crs = ds.crs
    cropped_tci_path = crop(polygon, tci_path, crs)
    tasks = list()
    hash_name = hashlib.md5((str(tci_path)+str(polygon)).encode('utf-8')).hexdigest()

    with rio.Env(OGR_SQLITE_CACHE=1024, GDAL_CACHEMAX=128, GDAL_SWATH_SIZE=128000000,
                 GDAL_MAX_RAW_BLOCK_CACHE_SIZE=128000000, VSI_CACHE=True, VSI_CACHE_SIZE=1073741824,
                 GDAL_FORCE_CACHING=True):
        with rio.open(cropped_tci_path) as inds:
            # meta = inds.meta
            # meta.update(nodata=255)
            # export_to_tiff(cropped_tci_path,meta)
            bounds = inds.bounds
            geom = box(*bounds)
            print(geom)
            logger.info("KATANA STARTS")
            res = katana(polygon, threshold=10000)
            print(type(res))
            logger.info("KATANA ENDS")
            buff = []
            arr = []

            for i in range(len(res)):
                buffered = res[i].buffer(800, join_style=2)
                buff.append(buffered)

            gdf = geopandas.GeoDataFrame(geometry=buff, crs="EPSG:3857")
            logger.debug("CREATED SHAPE TILES FOLDER")
            tiles_working_folder = Path(storage_folder.joinpath(str(hash_name)+'_files')).absolute()
            tiles_working_folder.mkdir(exist_ok=True)
            list_of_tiles = tiles_working_folder.joinpath(str(hash_name) + ".shp")
            gdf.to_file(list_of_tiles)
            # list_of_tiles = Path(__file__).absolute().parents[1].joinpath(shapefile_name)

            shapefile = geopandas.read_file(list_of_tiles)
            print(shapefile)
            with fiona.open(list_of_tiles, "r") as shapefile:
                shapes = [feature["geometry"] for feature in shapefile]
            print(len(shapes))

            for i in range(len(shapes)):
                with rasterio.open(cropped_tci_path) as src:
                    out_image, out_transform = rasterio.mask.mask(src, shapes[i:i + 1], crop=True)
                    out_meta = src.meta

                out_meta.update({"driver": "GTiff",
                                 "height": out_image.shape[1],
                                 "width": out_image.shape[2],
                                 "transform": out_transform},
                                )

                # if not os.path.exists(hash_name):
                #     os.mkdir(hash_name, mode=0o755)
                # tiles_path = Path(__file__).absolute().parents[1].joinpath(hash_name)

                with rasterio.open((str(tiles_working_folder) + '/tiles_') + str(i), "w", **out_meta) as dest:
                    dest.write(out_image)

                print(f"RESOLUTION STARTS {i+1}/{len(shapes)}")

                #     task = resolution_task.s("./tiles/tile_" + str(i))
                #     tasks.append(task)
                #
                # result = celery.group(tasks).delay().get()
                # logger.debug(len(result))
                # return
                #
                #
                #     # task = celery.group(resolution.s("./tiles/tile_" + str(i))).apply_async().get()
                #     # print(task)
                img = resolve_and_plot(tiles_working_folder.joinpath('tiles_' + str(i)))
                # img = resolve_and_plot((str(tiles_path) + '/tiles_') + str(i))
                print(f"RESOLUTION ENDS {i+1}/{len(shapes)}")
                out_meta.update({"driver": "GTiff",
                                 "height": out_image.shape[1] * 4,
                                 "width": out_image.shape[2] * 4,
                                 "transform": out_transform * out_transform.scale(1 / 4),
                                 "count": 3})
                logger.debug(img.shape)
                logger.debug(f"META:{out_meta}")

                resulting_path = Path(storage_folder.joinpath(f'{hash_name}_results')).absolute()
                resulting_path.mkdir(exist_ok=True)
                # if not os.path.exists((str(tiles_path) + '_results')):
                #     os.mkdir((str(tiles_path) + '_results'), mode=0o755)
                with rio.open(os.path.join(resulting_path, "resolved_tile_" + str(i) + ".tiff"), 'w',
                              **out_meta) as imgs:
                    # img = np.where(img <= 4, 0, img)
                    imgs.write(img)
                new_img = export_to_tiff(
                    os.path.join(resulting_path, "resolved_tile_" + str(i) + ".tiff"), out_meta)

    shutil.rmtree(tiles_working_folder, ignore_errors=True)
    shutil.rmtree(storage_folder.joinpath(str(hash_name)+'_cropped_tci'))
    logger.debug("DELETED  TCI FOLDER")
    logger.debug("DELETED SHAPE TILES FOLDER")
    logger.debug("MERGING")
    merged_folder = Path(storage_folder.joinpath('merged')).absolute()
    merged_folder.mkdir(exist_ok=True)
    merge(folder_path=str(resulting_path), merged_path=merged_folder, hash_name=hash_name)
    logger.debug("MERGING EROSION")
    merged = f'{str(merged_path)}/{str(hash_name)}.tiff'
    logger.debug(merged)
    with rio.open(str(merged)) as a:
        meta = a.meta
    export_to_tiff(str(merged), meta)
    logger.debug("FINISHED")
    return dict(results=str(resulting_path))


@app.route('/app/v1/perform_sr', methods=['POST'])
def perform_sr():
    print("hello zhamilya")
    form_data = request.json
    print("here i am")
    return do_sr(**form_data)


def main():
    print("hello")
    # geometry = 'MultiPolygon (((9179005.3084421195089817 5663138.53135722782462835, 9179728.39327027834951878 5664965.2719757342711091, 9184637.75868251360952854 5662910.1887799147516489, 9187834.55476490035653114 5659599.22140887193381786, 9192591.69179225899279118 5654613.74180419929325581, 9192553.63469604030251503 5652178.087646191008389, 9190194.09473047032952309 5651683.34539534524083138, 9187035.35574430227279663 5654423.4563231049105525, 9185436.9577031098306179 5657696.36659792810678482, 9182049.87613962963223457 5660055.90656349901109934, 9180223.13552112318575382 5661996.81847066152840853, 9179005.3084421195089817 5663138.53135722782462835)))'
    # tci_path = '/home/zhamilya/PycharmProjects/superres/T44TPR_20210926T052651_TCI.jp2'
    # do_sr(geometry, tci_path)
    #
    # cache_folder = Path(settings.PROJECT.dirs.cache_folder)
    # data_folder = Path(settings.PROJECT.dirs.data_folder)
    # print(cache_folder)

    # return
    app.run(host='0.0.0.0', port=5000)
    return
    logger.debug('Start')
    polygon = "./hello.geojson"
    image = "./T42UVA_20210825T062631_TCI_10m.jp2"
    in_path, input_filenamee = crop(polygon, image)
    input_filename = str(input_filenamee) + ".tiff"
    tasks = list()

    with rio.Env(OGR_SQLITE_CACHE=1024, GDAL_CACHEMAX=128, GDAL_SWATH_SIZE=128000000,
                 GDAL_MAX_RAW_BLOCK_CACHE_SIZE=128000000, VSI_CACHE=True, VSI_CACHE_SIZE=1073741824,
                 GDAL_FORCE_CACHING=True):
        with rio.open(os.path.join(in_path, input_filename)) as inds:
            bounds = inds.bounds
            geom = box(*bounds)
            print(geom)
            logger.info("KATANA STARTS")
            res = katana(geom, threshold=10000)
            print(type(res))
            logger.info("KATANA ENDS")
            logger.info("KATANA ENDS")
            buff = []
            arr = []

            for i in range(len(res)):
                buffered = res[i].buffer(800, join_style=2)
                buff.append(buffered)

            gdf = geopandas.GeoDataFrame(geometry=buff, crs="EPSG:3857")
            gdf.to_file("my_buffer.shp")
            pew = Path(__file__).absolute().parents[1].joinpath('my_buffer.shp')
            image = Path(__file__).absolute().parents[1].joinpath(str(input_filename))

            shapefile = geopandas.read_file(pew)
            print(shapefile)
            with fiona.open(pew, "r") as shapefile:
                shapes = [feature["geometry"] for feature in shapefile]
            print(len(shapes))
            for i in range(len(shapes)):
                with rasterio.open(image) as src:
                    out_image, out_transform = rasterio.mask.mask(src, shapes[i:i + 1], crop=True)
                    out_meta = src.meta

                out_meta.update({"driver": "GTiff",
                                 "height": out_image.shape[1],
                                 "width": out_image.shape[2],
                                 "transform": out_transform},
                                nodata=255)

                if not os.path.exists(input_filenamee):
                    os.mkdir(input_filenamee, mode=0o755)
                tiles_path = Path(__file__).absolute().parents[1].joinpath(input_filenamee)

                with rasterio.open((str(tiles_path) + '/tiles_') + str(i), "w", **out_meta) as dest:
                    dest.write(out_image)

                print("RESOLUTION STARTS")

                #     task = resolution_task.s("./tiles/tile_" + str(i))
                #     tasks.append(task)
                #
                # result = celery.group(tasks).delay().get()
                # logger.debug(len(result))
                # return
                #
                #
                #     # task = celery.group(resolution.s("./tiles/tile_" + str(i))).apply_async().get()
                #     # print(task)
                img = resolve_and_plot((str(tiles_path) + '/tiles_') + str(i))
                print("RESOLUTION ENDS")
                out_meta.update({"driver": "GTiff",
                                 "height": out_image.shape[1] * 4,
                                 "width": out_image.shape[2] * 4,
                                 "transform": out_transform * out_transform.scale(1 / 4),
                                 "count": 3},nodata=255)
                logger.debug(img.shape)
                if not os.path.exists((str(tiles_path) + '_results')):
                    os.mkdir((str(tiles_path) + '_results'), mode=0o755)
                with rio.open(os.path.join((str(tiles_path) + '_results'), "resolved_tile_" + str(i) + ".tif"), 'w',
                              **out_meta) as imgs:
                    # img = np.where(img <= 4, 0, img)
                    imgs.write(img)
                # new_img = export_to_tiff(
                #     os.path.join((str(tiles_path) + '_results'), "resolved_tile_" + str(i) + ".tif"), out_meta)

            #     mem_file = rio.MemoryFile()
            #     # meta = Box(inds.meta)
            #     # meta.width = img.shape[1]
            #     # meta.height = img.shape[-1]
            #     # meta.transform = out_transform * out_transform.scale(1 / 4)
            #     mem_datasets = mem_file.open(**out_meta)
            #     logger.debug("MEMORY WRITE ")
            #     mem_datasets.write(new_img)
            #     logger.debug("ARRAY APPEND START ")
            #     arr.append(mem_datasets)
            #     logger.debug(f"ARRAY LENGTH {len(arr)}")
            #     logger.debug(f"ARRAY shape {arr[-1].shape}")
            # logger.debug("MERGE STARTS ")
            # result = perform_merge(arr)
            # logger.debug(f'Shape of result is {result.data.shape}')
            # # with rasterio.open('asdasd.tiff', 'w', transform=result.transform) as res_ds:
            # #     res_ds.write(result.data)
            # # with open('merge_result1.pickle', 'wb') as file:
            # #     pickle.dump(result, file)
            #
            # with rio.open(image, 'w', width=result.data.shape[-1], height=result.data.shape[1],
            #               driver='GTiff', dtype='uint8', nodata=0,
            #               count=3, transform=result.transform, tiled=False, interleave='pixel') as dst:
            #     result.data = np.where(result.data <= 4, 0, result.data)
            #     dst.write(np.array(result.data).astype(rio.uint8))
            #     dst.crs = "EPSG:3857"
            #     final_meta = dst.meta
            #     print("FINAL META", final_meta)
            #
            # export_to_tiff(image, final_meta)

            return


if __name__ == '__main__':
    main()
