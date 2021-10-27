import shapely.wkt as shwkt
import geopandas as gpd
import requests
from pathlib import Path
import json

def main():
    geometry = 'MultiPolygon (((9179005.3084421195089817 5663138.53135722782462835, 9179728.39327027834951878 5664965.2719757342711091, 9184637.75868251360952854 5662910.1887799147516489, 9187834.55476490035653114 5659599.22140887193381786, 9192591.69179225899279118 5654613.74180419929325581, 9192553.63469604030251503 5652178.087646191008389, 9190194.09473047032952309 5651683.34539534524083138, 9187035.35574430227279663 5654423.4563231049105525, 9185436.9577031098306179 5657696.36659792810678482, 9182049.87613962963223457 5660055.90656349901109934, 9180223.13552112318575382 5661996.81847066152840853, 9179005.3084421195089817 5663138.53135722782462835)))'
    # geom = gpd.GeoSeries([shwkt.loads(geometry)], crs='epsg:3857')
    # geom.to_file('qweqwe.geojson', driver='GeoJSON')
    # return
    path = Path(__file__).absolute().parents[1]

    out = requests.post('http://superres_server:5000/app/v1/perform_sr',
                              json=dict(geometry = geometry,
                                        tci_path ='/home/zhamilya/PycharmProjects/superres/T44TPR_20210926T052651_TCI.jp2')).json()
    # print(out)
    print(out['results'])
    pass


if __name__ == '__main__':
    main()

