import shapely.wkt
import shapely.geometry as shg
import os
from itertools import product
import rasterio as rio
from rasterio import windows
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

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

from flask import Flask, render_template, request, render_template_string

app = Flask(__name__)


# CROP POLYGON GEOJSON FROM FP2 FILE
def crop(polygon: shg.Polygon, image_path, image_crs):
    # todo: save polygon to file.

    write = "gdalwarp -overwrite " + str(image_path) + " " + str(
        image_path) + f" -s_srs {image_crs} -t_srs EPSG:3857"  # todo change dst path
    os.system(write)
    new_name = hashlib.md5(str(image_path).encode('utf-8')).hexdigest()
    input_path = Path(__file__).absolute().parents[1]

    logger.info(f"CROPPED POLYGON {str(new_name)}")
    cut = "gdalwarp -overwrite -crop_to_cutline -cutline " + str(polygon) + " -t_srs EPSG:3857 " + str(
        image_path) + " " + str(input_path) + str(new_name) + ".tiff"
    os.system(cut)
    return input_path, new_name


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
        mask = np.where(mask.sum(axis=0) == 0, 0, 1)
        res = ndimage.binary_erosion(mask, structure=np.ones((13, 13)))
        zh = np.where(res == 1, a.read(), 0)

    with rio.open(name, 'w', **meta) as dst:
        dst.write(np.array(zh).astype(rio.uint8))

    return np.array(zh).astype(rio.uint8)


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


@app.route('/app/v1/perform_sr', methods=['POST'])
def perform_sr():
    form_data = request.json
    print(form_data)
    polygon_wkt = form_data["geometry"]
    polygon = shapely.wkt.loads(polygon_wkt)
    image_path = form_data["tci_path"]
    with rasterio.open(image_path) as ds:
        crs = ds.crs
    in_path, input_filenamee = crop(polygon, image_path, crs)
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
            buff = []
            arr = []

            for i in range(len(res)):
                buffered = res[i].buffer(800, join_style=2)
                buff.append(buffered)

            gdf = geopandas.GeoDataFrame(geometry=buff, crs="EPSG:3857")
            shapefile_name = str(input_filenamee) + ".shp"
            gdf.to_file(shapefile_name)
            pew = Path(__file__).absolute().parents[1].joinpath(shapefile_name)
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
                                nodata=0)

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
                                 "count": 3})
                logger.debug(img.shape)
                if not os.path.exists((str(tiles_path) + '_results')):
                    os.mkdir((str(tiles_path) + '_results'), mode=0o755)
                with rio.open(os.path.join((str(tiles_path) + '_results'), "resolved_tile_" + str(i) + ".tif"), 'w',
                              **out_meta) as imgs:
                    img = np.where(img <= 4, 0, img)
                    imgs.write(img)
                new_img = export_to_tiff(
                    os.path.join((str(tiles_path) + '_results'), "resolved_tile_" + str(i) + ".tif"), out_meta)

    return dict(results=str(tiles_path) + '_results')


@app.route('/data/', methods=['POST', 'GET'])
def data():
    if request.method == 'GET':
        return f"The URL /data is accessed directly. Try going to '/form' to submit form"
    if request.method == 'POST':
        form_data = request.form
        logger.debug('Start')
        polygon = form_data["Polygon Path"]
        image = form_data["Image Path"]
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
                buff = []
                arr = []

                for i in range(len(res)):
                    buffered = res[i].buffer(800, join_style=2)
                    buff.append(buffered)

                gdf = geopandas.GeoDataFrame(geometry=buff, crs="EPSG:3857")
                shapefile_name = str(input_filenamee) + ".shp"
                gdf.to_file(shapefile_name)
                pew = Path(__file__).absolute().parents[1].joinpath(shapefile_name)
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
                                    nodata=0)

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
                                     "count": 3})
                    logger.debug(img.shape)
                    if not os.path.exists((str(tiles_path) + '_results')):
                        os.mkdir((str(tiles_path) + '_results'), mode=0o755)
                    with rio.open(os.path.join((str(tiles_path) + '_results'), "resolved_tile_" + str(i) + ".tif"), 'w',
                                  **out_meta) as imgs:
                        img = np.where(img <= 4, 0, img)
                        imgs.write(img)
                    new_img = export_to_tiff(
                        os.path.join((str(tiles_path) + '_results'), "resolved_tile_" + str(i) + ".tif"), out_meta)

        return render_template_string('<h2>{{form_data}}</h2>', form_data=(str(tiles_path) + '_results'))


def main():
    print("hi")
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
                                nodata=0)

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
                                 "count": 3})
                logger.debug(img.shape)
                if not os.path.exists((str(tiles_path) + '_results')):
                    os.mkdir((str(tiles_path) + '_results'), mode=0o755)
                with rio.open(os.path.join((str(tiles_path) + '_results'), "resolved_tile_" + str(i) + ".tif"), 'w',
                              **out_meta) as imgs:
                    img = np.where(img <= 4, 0, img)
                    imgs.write(img)
                new_img = export_to_tiff(
                    os.path.join((str(tiles_path) + '_results'), "resolved_tile_" + str(i) + ".tif"), out_meta)

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


app.run(host='0.0.0.0', port=5000)

if __name__ == '__main__':
    main()
