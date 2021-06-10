import numpy as np
try:
    import gdal
    IPT_GDAL = True
except:
    IPT_GDAL = False


def open_tif(geoimg_path, to_np=False):
    '''
        打开tif文件
    '''
    if IPT_GDAL == True:
        geoimg = gdal.Open(geoimg_path)
        if to_np == False:
            return geoimg
        else:
            return tif2array(geoimg), get_geoinfo(geoimg)
    else:
        raise ImportError('can\'t import gdal!')


def tif2array(geoimg):
    if IPT_GDAL == True:
        return geoimg.ReadAsArray().transpose((1, 2, 0))  # 多波段图像默认是[c, h, w]
    else:
        raise ImportError('can\'t import gdal!')


def get_geoinfo(geoimg):
    '''
        获取tif图像的信息，输入为dgal读取的数据
    '''
    if IPT_GDAL == True:
        geoinfo = {
            'xsize': geoimg.RasterXSize,
            'ysize': geoimg.RasterYSize,
            'count': geoimg.RasterCount,
            'proj': geoimg.GetProjection(),
            'geotrans': geoimg.GetGeoTransform()
        }
        return geoinfo
    else:
        raise ImportError('can\'t import gdal!')


def save_tif(img, geoinfo, save_path):
    '''
        保存分割的图像并使其空间信息保持一致
    '''
    if IPT_GDAL == True:
        driver = gdal.GetDriverByName('GTiff')
        datatype = gdal.GDT_Byte
        dataset = driver.Create(
            save_path, 
            geoinfo['xsize'], 
            geoinfo['ysize'], 
            geoinfo['count'], 
            datatype)
        dataset.SetProjection(geoinfo['proj'])  # 写入投影
        dataset.SetGeoTransform(geoinfo['geotrans'])  # 写入仿射变换参数
        C = img.shape[-1] if len(img.shape) == 3 else 1
        if C == 1:
            dataset.GetRasterBand(1).WriteArray(img)
        else:
            for i_c in range(C):
                dataset.GetRasterBand(i_c + 1).WriteArray(img[:, :, i_c])
        del dataset  # 删除与tif的连接
    else:
        raise ImportError('can\'t import gdal!')