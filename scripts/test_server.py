
import requests
import fiona
from shapely.geometry import shape


def main():

    list_of_tiles = "/home/zhamilya/PycharmProjects/superres/tiler_test.shp"

    with fiona.open(list_of_tiles, "r") as shapefile:
        shapes = [feature["geometry"] for feature in shapefile]
        for i in range(len(shapes)):
            g2 = shape(shapes[i])
        print(type(g2))
        url = 'http://54.93.234.138:16823/api/v1/superresolution'
        out = requests.post(url=url, json={"area": g2, "date_of_interest": "2021-7-15"}).json()
        # out = requests.post(url=url,
        #                           json=dict(area = geometry,
        #                                     date_of_interest ='2021-8-1')).json()
        print(i)
        print(out)
    pass


if __name__ == '__main__':
    main()

