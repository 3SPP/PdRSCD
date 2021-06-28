import numpy as np
import cv2
import random
import math
from functools import reduce
from ppcd.transforms import functional as func


# ----- compose -----
class Compose:
    """ 
    根据数据增强算子对输入数据进行操作
    所有操作的输入图像流形状均是 [H, W, C]，其中H为图像高，W为图像宽，C为图像通道数
    Args:
        transforms (list/None): 数据增强算子，默认为None
        data_format ("HWC"/"CHW"): 如果数据是npy/npz格式，数据形状如何，默认为"HWC"
        classes_num (int): 标签有多少类，默认为2（单一的变化检测）
    """
    def __init__(self, transforms=None, data_format="HWC", classes_num=2):
        if data_format != "HWC" and data_format != "CHW":
            raise ValueError('The data_format must be "HWC" or "CHW"!')
        self.transforms = transforms
        self.data_format = data_format
        self.classes_num = classes_num

    def __call__(self, imgs, labs=None):
        """
        Args:
            A_img (list[str/ndarray]): 多期图像路径 (.tif/.img/.npy/.jpg/.mat等)
            lab (list[ndarray]): 标注图像路径 (.png)，默认为None
            当为ndarray时，就是大图像处理的时候
        """
        timgs = []
        tlabs = []
        for i in range(len(imgs)):
            if isinstance(imgs[i], str):
                timgs.append(func.read_img(imgs[i], self.data_format, is_lab=False))
            else:
                timgs.append(imgs[i])
        if labs is not None:
            for i in range(len(labs)):
                if isinstance(labs[i], str):
                    tlabs.append(func.read_img(labs[i], self.data_format, \
                                               is_lab=True, classes_num=self.classes_num))
                else:
                    tlabs.append(labs[i])
        else:
            tlabs = None
        # 数据增强
        if self.transforms is not None:
            for op in self.transforms:
                timgs, tlabs = op(timgs, tlabs)
        if tlabs is None:
            return timgs
        else:
            tlabst = [np.array(tlab).astype('int64') for tlab in tlabs]
            return timgs, tlabst


# ----- transforms -----
class Resize:
    """
    调整图像和标注图大小
    Args:
        target_size (int/list/tuple): 目标大小
        interp (str): 插值方式，可选参数为 ['NEAREST', 'LINEAR', 'CUBIC', 'AREA', 'LANCZOS4']，默认为'NEAREST'
    """
    interp_dict = {
        'NEAREST': cv2.INTER_NEAREST,
        'LINEAR': cv2.INTER_LINEAR,
        'CUBIC': cv2.INTER_CUBIC,
        'AREA': cv2.INTER_AREA,
        'LANCZOS4': cv2.INTER_LANCZOS4
    }
    def __init__(self, target_size, interp='NEAREST'):
        if isinstance(target_size, list) or isinstance(target_size, tuple):
            if len(target_size) != 2:
                raise ValueError(
                    'when target is list or tuple, it should include 2 elements, but it is {}.'
                    .format(target_size))
        elif not isinstance(target_size, int):
            raise TypeError(
                'Type of target_size is invalid. Must be Integer or List or tuple, now is {}.'
                .format(type(target_size)))
        assert interp in self.interp_dict, \
            'interp should be one of {}.'.format(self.interp_dict.keys())
        self.target_size = target_size
        self.interp = interp

    def __call__(self, image, label=None):
        if isinstance(self.target_size, int):
            size = (self.target_size, self.target_size)
        else:
            size = self.target_size
        for i in range(len(image)):
            if not isinstance(image[i], np.ndarray):
                raise TypeError("ResizeImage: image type is not np.ndarray.")
            if len(image[i].shape) != 3:
                raise ValueError('ResizeImage: image is not 3-dimensional.')
            image[i] = cv2.resize(image[i], size, interpolation=self.interp_dict[self.interp])
        if label is not None:
            label = [cv2.resize(lab, size, interpolation=self.interp_dict['NEAREST']) \
                     for lab in label]
        return image, label
            

class Normalize:
    """
    对图像进行标准化
        1.图像像素归一化到区间 [0.0, 1.0]
        2.对图像进行减均值除以标准差操作
    Args:
        mean (list): 图像数据集的均值列表，有多少波段需要多少个元素
        std (list): 图像数据集的标准差列表，有多少波段需要多少个元素
        bit_num (int): 图像的位数，默认为8
        band_num (int): 操作的波段数，默认为3
    """
    def __init__(self, mean, std, bit_num=8, band_num=3):
        if bit_num not in [8, 16, 24]:
            raise ValueError('{} is not effective bit_num, bit_num should be one of 8, 16, 24.'
                             .format(bit_num))
        if band_num != len(mean) or band_num != len(std):
            raise ValueError('band_num should be equal to len of mean/std.')
        if not (isinstance(mean, list) and isinstance(std, list)):
            raise ValueError('{}: input type is invalid.'.format(self))
        if reduce(lambda x, y: x * y, std) == 0:
            raise ValueError('{}: std is invalid!'.format(self))
        self.mean = mean
        self.std = std
        self.band_num = band_num
        self.min_val = [0] * band_num
        self.max_val = [2**bit_num - 1] * band_num

    def __call__(self, image, label=None):
        mean = np.array(self.mean)[np.newaxis, np.newaxis, :]
        std = np.array(self.std)[np.newaxis, np.newaxis, :]
        images = []
        for i in range(len(image)):
            images.append(func.normalize(
                image[i], self.min_val, self.max_val, mean, std, self.band_num))
        return images, label


class RandomFlip:
    """
    对图像和标注图进行翻转
    Args:
        prob (float): 随机翻转的概率。默认值为0.5
        direction (str): 翻转方向，可选参数为 ['Horizontal', 'Vertical', 'Both']，默认为'Both'
    """
    flips_list = ['Horizontal', 'Vertical', 'Both']
    def __init__(self, prob=0.5, direction='Both'):
        if prob < 0 or prob > 1:
            raise ValueError('prob should be between 0 and 1.')
        assert direction in self.flips_list, 'direction should be one of {}.'.format(self.flips_list)
        self.prob = prob
        self.direction = direction

    def __call__(self, image, label=None):
        if random.random() < self.prob:
            images = []
            for i in range(len(image)):
                images.append(func.mode_flip(image[i], self.direction))
            if label is not None:
                label = [func.mode_flip(lab, self.direction) for lab in label]
            return images, label
        else:
            return image, label


class RandomRotate:
    """
    对图像和标注图进行随机1-89度旋转，保持图像大小
    Args:
        prob (float): 选择的概率。默认值为0.5
        ig_pix (int): 标签旋转后周围填充的忽略值，默认为255
    """
    def __init__(self, prob=0.5, ig_pix=255):
        if prob < 0 or prob > 1:
            raise ValueError('prob should be between 0 and 1.')
        self.prob = prob
        self.ig_pix = ig_pix

    def __call__(self, image, label=None):
        ang = random.randint(1, 89)
        if random.random() < self.prob:
            images = []
            for i in range(len(image)):
                images.append(func.rotate_img(image[i], ang))
            if label is not None:
                label = [func.rotate_img(lab, ang, ig_pix=self.ig_pix) for lab in label]
            return images, label
        else:
            return image, label


class RandomEnlarge:
    """
    对图像和标注图进行随机裁剪，然后拉伸到到原来的大小 (局部放大)
    Args:
        prob (float): 裁剪的概率。默认值为0.5
        min_clip_rate (list/tuple): 裁剪图像行列占原图大小的最小倍率。默认为 [0.5, 0.5]
    """
    def __init__(self, prob=0.5, min_clip_rate=[0.5, 0.5]):
        if prob < 0 or prob > 1:
            raise ValueError('prob should be between 0 and 1.')
        if isinstance(min_clip_rate, list) or isinstance(min_clip_rate, tuple):
            if len(min_clip_rate) != 2:
                raise ValueError(
                    'when min_clip_rate is list or tuple, it should include 2 elements, but it is {}.'
                    .format(min_clip_rate))
        self.prob = prob
        self.min_clip_rate = list(min_clip_rate)

    def __call__(self, image, label=None):
        h, w = image[0].shape[:2]
        h_clip = math.floor(self.min_clip_rate[0] * h)
        w_clip = math.floor(self.min_clip_rate[1] * w)
        x = random.randint(0, (w - w_clip))
        y = random.randint(0, (h - h_clip))
        if random.random() < self.prob:
            images = []
            for i in range(len(image)):
                images.append(func.enlarge_img(image[i], x, y, h_clip, w_clip))
            if label is not None:
                label = [func.enlarge_img(lab, x, y, h_clip, w_clip) for lab in label]
            return images, label
        else:
            return image, label



class RandomNarrow:
    """
    对图像和标注图进行随机缩小，然后填充到到原来的大小
    Args:
        prob (float): 缩小的概率。默认值为0.5
        min_size_rate (list/tuple): 缩小图像行列为原图大小的倍率。默认为 [0.5, 0.5]
        ig_pix (int): 标签缩小后周围填充的忽略值，默认为255
    """
    def __init__(self, prob=0.5, min_size_rate=[0.5, 0.5], ig_pix=255):
        if prob < 0 or prob > 1:
            raise ValueError('prob should be between 0 and 1.')
        if isinstance(min_size_rate, list) or isinstance(min_size_rate, tuple):
            if len(min_size_rate) != 2:
                raise ValueError(
                    'when min_size_rate is list or tuple, it should include 2 elements, but it is {}.'
                    .format(min_size_rate))
        self.prob = prob
        self.min_size_rate = list(min_size_rate)
        self.ig_pix = ig_pix

    def __call__(self, image, label=None):
        x_rate = random.uniform(self.min_size_rate[0], 1)
        y_rate = random.uniform(self.min_size_rate[1], 1)
        if random.random() < self.prob:
            images = []
            for i in range(len(image)):
                images.append(func.narrow_img(image[i], x_rate, y_rate))
            if label is not None:
                label = [func.narrow_img(lab, x_rate, y_rate, ig_pix=self.ig_pix) for lab in label]
            return images, label
        else:
            return image, label


class RandomBlur:
    """
    对图像进行高斯模糊
    Args：
        prob (float): 图像模糊概率。默认为0.1
        ksize (int): 高斯核大小，默认为3
        band_num (int): 操作的波段数，默认为3
        img_do (bool): 对哪几个时段进行操作，默认为[0, 1]
    """
    def __init__(self, prob=0.1, ksize=3, band_num=3, img_do=[0, 1]):
        if prob < 0 or prob > 1:
            raise ValueError('prob should be between 0 and 1.')
        if not isinstance(img_do, list):
            raise ValueError('img_do should be list.')
        self.prob = prob
        self.ksize = ksize
        self.band_num = band_num
        self.img_do = img_do

    def __call__(self, image, label=None):
        if random.random() < self.prob:
            for i in range(len(image)):
                if i in self.img_do:
                    image[i][:, :, :self.band_num] = cv2.GaussianBlur(
                        image[i][:, :, :self.band_num], (self.ksize, self.ksize), 0)
            return image, label
        else:
            return image, label


class RandomSharpening:
    """
    对图像进行锐化
    Args：
        prob (float): 图像锐化概率。默认为0.1
        laplacian_mode (str): 拉普拉斯算子类型，可选参数为 ['4-1', '8-1', '4-2']，默认为'8-1'
        band_num (int): 操作的波段数，默认为3
        img_do (bool): 对哪几个时段进行操作，默认为[0, 1]
    """
    laplacian_dict = {
        '4-1': np.array([[0, -1, 0], [-1, 4, -1], [0, -1, 0]], np.float32),
        '8-1': np.array([[-1, -1, -1], [-1, 8, -1], [-1, -1, -1]], np.float32),
        '4-2': np.array([[1, -2, 1], [-2, 4, -2], [1, -2, 1]], np.float32)
    }
    def __init__(self, prob=0.1, laplacian_mode='8-1', band_num=3, img_do=[0, 1]):
        assert laplacian_mode in self.laplacian_dict,  \
               'laplacian_mode should be one of {}.'.format(self.laplacian_dict.keys())
        if prob < 0 or prob > 1:
            raise ValueError('prob should be between 0 and 1.')
        if not isinstance(img_do, list):
            raise ValueError('img_do should be list.')
        self.prob = prob
        self.band_num = band_num
        self.kernel = self.laplacian_dict[laplacian_mode]
        self.img_do = img_do

    def __call__(self, image, label=None):
        if random.random() < self.prob:
            for i in range(len(image)):
                if i in self.img_do:
                    image[i][:, :, :self.band_num] += (
                        0.2 * cv2.filter2D(image[i][:, :, :self.band_num], -1, kernel=self.kernel))
            return image, label
        else:
            return image, label


class RandomColor:
    """
    对图像随机进行对比度及亮度的小范围增减
    Args：
        prob (float): 改变概率。默认为0.5
        alpha_range (list/tuple): 图像对比度调节范围，默认为 [0.8, 1.2]
        beta_range (list/tuple): 图像亮度调节范围，默认为 [-10, 10]
        band_num (int): 操作的波段数，默认为3
        img_do (bool): 对哪几个时段进行操作，默认为[0, 1]
    """
    def __init__(self, prob=0.5, alpha_range=[0.8, 1.2], beta_range=[-10, 10], band_num=3, img_do=[0, 1]):
        if prob < 0 or prob > 1:
            raise ValueError('prob should be between 0 and 1.')
        if isinstance(alpha_range, list) or isinstance(alpha_range, tuple):
            if len(alpha_range) != 2:
                raise ValueError(
                    'when alpha_range is list or tuple, it should include 2 elements, but it is {}.'
                    .format(alpha_range))
        if isinstance(beta_range, list) or isinstance(beta_range, tuple):
            if len(beta_range) != 2:
                raise ValueError(
                    'when beta_range is list or tuple, it should include 2 elements, but it is {}.'
                    .format(beta_range))
        if not isinstance(img_do, list):
            raise ValueError('img_do should be list.')
        self.prob = prob
        self.alpha_range = list(alpha_range)
        self.beta_range = list(beta_range)
        self.band_num = band_num
        self.img_do = img_do

    def __call__(self, image, label=None):
        if random.random() < self.prob:
            alpha = random.uniform(self.alpha_range[0], self.alpha_range[1])
            beta = random.uniform(self.beta_range[0], self.beta_range[1])
            for i in range(len(image)):
                if i in self.img_do:
                    image[i][:, :, :self.band_num] = alpha * image[i][:, :, :self.band_num] + beta
            return image, label
        else:
            return image, label


class RandomStrip:
    """
    对图像随机加上条带噪声
    Args：
        prob (float): 加上条带噪声的概率。默认为0.5
        strip_rate (float): 条带占比，默认0.05
        direction (str): 条带方向，可选参数 ['Horizontal', 'Vertical'],，默认'Horizontal'
        band_num (int): 操作的波段数，默认为3
        img_do (bool): 对哪几个时段进行操作，默认为[0, 1]
    """
    strip_list = ['Horizontal', 'Vertical']
    def __init__(self, prob=0.5, strip_rate=0.05, direction='Horizontal', band_num=3, img_do=[0, 1]):
        assert direction in self.strip_list, 'direction should be one of {}.'.format(self.strip_list)
        if prob < 0 or prob > 1:
            raise ValueError('prob should be between 0 and 1.')
        if strip_rate < 0 or strip_rate > 1:
            raise ValueError('strip_rate should be between 0 and 1.')
        if not isinstance(img_do, list):
            raise ValueError('img_do should be list.')
        self.prob = prob
        self.strip_rate = strip_rate
        self.direction = direction
        self.band_num = band_num
        self.img_do = img_do

    def __call__(self, image, label=None):
        h, w = image[0].shape[:2]
        if random.random() < self.prob:
            strip_num = self.strip_rate * (h if self.direction == 'Horizontal' else w)
            images = []
            for i in range(len(image)):
                if i in self.img_do:
                    images.append(func.random_strip(
                        image[i], strip_num, self.direction, self.band_num))
            return images, label
        else:
            return image, label


class RandomFog:
    """
    对图像随机加上雾效果
    Args：
        prob (float): 加上雾效果的概率。默认为0.5
        fog_range (list/tuple): 雾的大小范围，范围在0-1之间，默认为 [0.03, 0.28]
        band_num (int): 操作的波段数，默认为3
        img_do (bool): 对哪几个时段进行操作，默认为[0, 1]
    """
    def __init__(self, prob=0.5, fog_range=[0.03, 0.28], band_num=3, img_do=[0, 1]):
        if prob < 0 or prob > 1:
            raise ValueError('prob should be between 0 and 1.')
        if isinstance(fog_range, list) or isinstance(fog_range, tuple):
            if len(fog_range) != 2:
                raise ValueError(
                    'when fog_range is list or tuple, it should include 2 elements, but it is {}.'
                    .format(fog_range))
        if not isinstance(img_do, list):
            raise ValueError('img_do should be list.')
        self.prob = prob
        self.fog_range = fog_range
        self.band_num = band_num
        self.img_do = img_do

    def __call__(self, image, label=None):
        if random.random() < self.prob:
            images = []
            for i in range(len(image)):
                if i in self.img_do:
                    images.append(func.add_fog(image[i], self.fog_range, self.band_num))
            return images, label
        else:
            return image, label


class RandomSplicing:
    """
    对图像进行随机划分成两块，并对其中一块改变色彩，营造拼接未匀色的效果
    Args：
        prob (float): 执行此操作的概率。默认为0.1
        direction (str): 分割方向，可选参数 ['Horizontal', 'Vertical'],，默认'Horizontal'
        band_num (int): 操作的波段数，默认为3
    """
    splic_list = ['Horizontal', 'Vertical']
    def __init__(self, prob=0.1, direction='Horizontal', band_num=3):
        assert direction in self.splic_list, 'direction should be one of {}.'.format(self.splic_list)
        if prob < 0 or prob > 1:
            raise ValueError('prob should be between 0 and 1.')
        self.prob = prob
        self.direction = direction
        self.band_num = band_num
        
    def __call__(self, image, label=None):
        if random.random() < self.prob:
            images = []
            for i in range(len(image)):
                images.append(func.random_splicing(image[i], self.direction, self.band_num))
            return images, label
        else:
            return image, label


class RandomRemoveBand:
    """
    对图像随机置零某个波段
    Args：
        prob (float): 执行此操作的概率。默认为0.1
        kill_bands (list): 必须置零的波段列表，默认为None
        keep_bands (list): 不能置零的波段列表，默认为None
    """
    def __init__(self, prob=0.1, kill_bands=None, keep_bands=None):
        if prob < 0 or prob > 1:
            raise ValueError('prob should be between 0 and 1.')
        if not(isinstance(kill_bands, list)) and kill_bands != None:
            raise ValueError('kill_bands must be list or None.')
        if not(isinstance(keep_bands, list)) and keep_bands != None:
            raise ValueError('keep_bands must be list or None.')
        self.prob = prob
        self.kill_bands = [] if kill_bands == None else list(kill_bands)
        self.keep_bands = [] if keep_bands == None else list(keep_bands)

    def __call__(self, image, label=None):
        if random.random() < self.prob:
            rand_list = []
            rm_list = []
            c = image[0].shape[-1]
            for i in range(c):
                if i in self.kill_bands:
                    rm_list.append(i)
                elif i in self.keep_bands:
                    continue
                else:
                    rand_list.append(i)
            rnd = random.choice(rand_list)
            rm_list.append(rnd)
            for j in rm_list:
                for i in range(len(image)):
                    image[i][:, :, j] = 0
        return image, label


class NDVI:
    """
    对图像计算NDVI (归一化植被指数)并添加在新的通道中
    Args：
        r_band (int): 红波段序号，默认为landsat TM的第三波段
        nir_band (int): 近红外波段序号，默认为landsat TM的第四波段
    """
    def __init__(self, r_band=2, nir_band=3):
        self.r_band = r_band
        self.nir_band = nir_band

    def __call__(self, image, label=None):
        images = []
        for i in range(len(image)):
            images.append(func.band_comput(image[i], self.nir_band, self.r_band))
        return images, label


class NDWI:
    """
    对图像计算NDWI (归一化水体指数)并添加在新的通道中
    Args：
        g_band (int): 绿波段序号，默认为landsat TM的第二波段
        nir_band (int): 近红外波段序号，默认为landsat TM的第四波段
    """
    def __init__(self, g_band=1, nir_band=3):
        self.g_band = g_band
        self.nir_band = nir_band

    def __call__(self, image, label=None):
        images = []
        for i in range(len(image)):
            images.append(func.band_comput(image[i], self.g_band, self.nir_band))
        return images, label


class NDBI:
    """
    对图像计算NDBI (归一化建筑指数)并添加在新的通道中
    Args：
        nir_band (int): 近红外波段序号，默认为landsat TM的第四波段
        mir_band (int): 中红外波段序号，默认为landsat TM的第五波段
    """
    def __init__(self, nir_band=3, mir_band=4):
        self.nir_band = nir_band
        self.mir_band = mir_band

    def __call__(self, image, label=None):
        images = []
        for i in range(len(image)):
            images.append(func.band_comput(image[i], self.mir_band, self.nir_band))
        return images, label


# ----- change detection -----
class ExchangeTime:
    """
    将两个时段的图像进行交换
    Args:
        prob (int): 执行此操作的概率。默认为0.5
    """
    def __init__(self, prob=0.5):
        if prob < 0 or prob > 1:
            raise ValueError('prob should be between 0 and 1.')
        self.prob = prob

    def __call__(self, image, label=None):
        if len(image) == 2:
            return [image[1], image[0]], label
        else:
            return image, label


# ----- histogram -----
class HistogramMatching:
    """
    将第二时段的直方图规定到第一时段
    Args:
        bit_num (int): 图像的位数，默认为8
        band_num (int): 操作的波段数，默认为3
    """
    def __init__(self, bit_num=8, band_num=3):
        if bit_num not in [8, 16, 24]:
            raise ValueError('{} is not effective bit_num, bit_num should be one of 8, 16, 24.'
                             .format(bit_num))
        self.bit_num = bit_num
        self.band_num = band_num

    def __call__(self, image, label=None):
        images = []
        for i in range(len(image)):
            if i == 0:
                images.append(image[i])
            else:
                images.append(func.histogram_matching(
                    image[i], image[0], self.band_num, self.bit_num))
        return images, label