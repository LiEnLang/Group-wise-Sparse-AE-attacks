import torch
import numpy as np
from scipy import ndimage

from .median import median_filter as median_filter_tf
from .median import median_random_filter as median_random_filter_tf
from .median import median_random_pos_size_filter as median_random_pos_size_filter_tf
from .median import median_random_size_filter as median_random_size_filter_tf


def reduce_precision_py(x, npp):
    """
    Reduce the precision of image, the numpy version.
    :param x: a float tensor, which has been scaled to [0, 1].
    :param npp: number of possible values per pixel. E.g. it's 256 for 8-bit gray-scale image, and 2 for binarized image.
    :return: a tensor representing image(s) with lower precision.
    """
    # Note: 0 is a possible value too.
    npp_int = npp - 1
    x_int = np.rint(x * npp_int)
    x_float = x_int / npp_int
    return x_float

def reduce_precision_tf(x, npp):
    """
    Reduce the precision of image, the tensorflow version.
    """
    npp_int = npp - 1
    x_int = torch.rint(torch.multiply(x, npp_int))
    x_float = torch.div(x_int, npp_int)
    return x_float


from attack.base import show_img
from skimage.restoration import denoise_wavelet

def denoising_py(noise_image):
    rec_image =  denoise_wavelet(noise_image, sigma=0.14, mode='hard', multichannel=False)
    # show_img(torch.tensor(noise_image).permute(0,3,1,2))
    # show_img(torch.tensor(rec_image).permute(0,3,1,2))

    return rec_image




def bit_depth_py(x, bits):
    precisions = 2**bits
    return reduce_precision_py(x, precisions)

def bit_depth_tf(x, bits):
    precisions = 2**bits
    return reduce_precision_tf(x, precisions)

def bit_depth_random_py(x, bits=4, stddev=0.125):
    if stddev == 0.:
        rand_array = np.zeros(x.shape)
    else:
        rand_array = np.random.normal(loc=0., scale=stddev, size=x.shape)
    x_random = np.add(x, rand_array)
    return bit_depth_py(x_random, bits)


def binary_filter_py(x, threshold):
    x_bin = np.maximum(np.sign(x-threshold), 0)
    return x_bin

def binary_random_filter_tf(x, threshold, stddev=0.125):
    rand_ts = torch.random_normal(x.get_shape(), mean=0, stddev=stddev)
    x_bin = torch.nn.relu(torch.sign(torch.add(x,rand_ts)-threshold))
    return x_bin

def binary_random_filter_py(x, threshold, stddev=0.125):
    if stddev == 0.:
        rand_array = np.zeros(x.shape)
    else:
        rand_array = np.random.normal(loc=0., scale=stddev, size=x.shape)
    x_bin = np.maximum(np.sign(np.add(x, rand_array)-threshold), 0)
    return x_bin


def median_filter_py(x, width, height=-1):
    """
    Median smoothing by Scipy.
    :param x: a tensor of image(s)
    :param width: the width of the sliding window (number of pixels)
    :param height: the height of the window. The same as width by default.
    :return: a modified tensor with the same shape as x.
    """
    if height == -1:
        height = width
    return ndimage.filters.median_filter(x, size=(1,width,height,1), mode='reflect')

def median_random_filter_py(x, width, height=-1):
    # assert False
    init_op = torch.initialize_all_variables()
    with torch.Session() as sess:
        sess.run(init_op)
        x = torch.constant(x)
        res = median_random_filter_tf(x, width, height)
        return res.eval()

def median_random_pos_size_filter_py(x, width, height=-1):
    # assert False
    init_op = torch.initialize_all_variables()
    with torch.Session() as sess:
        sess.run(init_op)
        x = torch.constant(x)
        res = median_random_pos_size_filter_tf(x, width, height)
        return res.eval()

def median_random_size_filter_py(x, width, height=-1):
    # assert False
    init_op = torch.global_variables_initializer()
    with torch.Session() as sess:
        sess.run(init_op)
        x = torch.constant(x)
        res = median_random_size_filter_tf(x, width, height)
        return res.eval()


# Squeezers implemented in OpenCV
# OpenCV expects uint8 as image data type.
def opencv_wrapper(imgs, opencv_func, argv):
    ret_imgs = []
    imgs_copy = imgs

    if imgs.shape[3] == 1:
        imgs_copy = np.squeeze(imgs)

    for img in imgs_copy:
        img_uint8 = np.clip(np.rint(img * 255), 0, 255).astype(np.uint8)
        ret_img = opencv_func(*[img_uint8]+argv)
        if type(ret_img) == tuple:
            ret_img = ret_img[1]
        ret_img = ret_img.astype(np.float32) / 255.
        ret_imgs.append(ret_img)
    ret_imgs = np.stack(ret_imgs)

    if imgs.shape[3] == 1:
        ret_imgs = np.expand_dims(ret_imgs, axis=3)

    return ret_imgs


# Binary filters.
def adaptive_binarize_py(x, block_size=5, C=33.8):
    "Works like an edge detector."
    # ADAPTIVE_THRESH_GAUSSIAN_C, ADAPTIVE_THRESH_MEAN_C
    # THRESH_BINARY, THRESH_BINARY_INV
    import cv2
    ret_imgs = opencv_wrapper(x, cv2.adaptiveThreshold, [255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, block_size, C])
    return ret_imgs

def otsu_binarize_py(x):
    # func = lambda img: cv2.threshold(img, 0, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)[1]
    # return opencv_binarize(x, func)
    import cv2
    ret_imgs = opencv_wrapper(x, cv2.threshold, [0, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU])
    return ret_imgs


# Non-local Means
def non_local_means_color_py(imgs, search_window, block_size, photo_render):
    import cv2
    ret_imgs = opencv_wrapper(imgs, cv2.fastNlMeansDenoisingColored, [None,photo_render,photo_render,block_size,search_window])
    return ret_imgs

def non_local_means_color_tf(imgs, search_window, block_size, photo_render):
    my_func = lambda x: non_local_means_color_py(x, search_window, block_size, photo_render)
    y = torch.py_func(my_func, [imgs], torch.float32, stateful=False)
    return y

def non_local_means_bw_py(imgs, search_window, block_size, photo_render):
    import cv2
    ret_imgs = opencv_wrapper(imgs, cv2.fastNlMeansDenoising, [None,photo_render,block_size,search_window])
    return ret_imgs

def non_local_means_bw_tf(imgs, search_window, block_size, photo_render):
    my_func = lambda x: non_local_means_bw_py(x, search_window, block_size, photo_render)
    y = torch.py_func(my_func, [imgs], torch.float32, stateful=False)
    return y


def bilateral_filter_py(imgs, d, sigmaSpace, sigmaColor):
    """
    :param d: Diameter of each pixel neighborhood that is used during filtering. 
        If it is non-positive, it is computed from sigmaSpace.
    :param sigmaSpace: Filter sigma in the coordinate space. 
        A larger value of the parameter means that farther pixels will influence each other as long as their colors are close enough (see sigmaColor ). 
        When d>0, it specifies the neighborhood size regardless of sigmaSpace. 
        Otherwise, d is proportional to sigmaSpace.
    :param sigmaColor: Filter sigma in the color space. 
        A larger value of the parameter means that farther colors within the pixel neighborhood (see sigmaSpace) will be mixed together, resulting in larger areas of semi-equal color.
    """
    import cv2
    return opencv_wrapper(imgs, cv2.bilateralFilter, [d, sigmaColor, sigmaSpace])

def bilateral_filter_tf(imgs, d, sigmaSpace, sigmaColor):
    my_func = lambda x: bilateral_filter_py(x, d, sigmaSpace, sigmaColor)
    y = torch.py_func(my_func, [imgs], torch.float32, stateful=False)
    return y


# Adaptive Bilateral Filter
# https://docs.opencv.org/2.4/modules/imgproc/doc/filtering.html#adaptivebilateralfilter
# Removed in OpenCV > 3.0.
def adaptive_bilateral_filter_py(imgs, ksize, sigmaSpace, maxSigmaColor=20.0):
    import cv2
    return opencv_wrapper(imgs, cv2.adaptiveBilateralFilter, [(ksize,ksize), sigmaSpace, maxSigmaColor])

def adaptive_bilateral_filter_tf(imgs, ksize, sigmaSpace, maxSigmaColor=20.0):
    my_func = lambda x: adaptive_bilateral_filter_py(x, ksize, sigmaSpace, maxSigmaColor)
    y = torch.py_func(my_func, [imgs], torch.float32, stateful=False)
    return y


none_tf = none_py = lambda x:x


import sys, os
project_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_path)



mnist_autoencoder_fpath = os.path.join(project_path, "downloads/MagNet/defensive_models/MNIST_I")
cifar10_autoencoder_fpath = os.path.join(project_path, "downloads/MagNet/defensive_models/CIFAR")






# Construct a name search function.
def isfloat(value):
    try:
        float(value)
        return True
    except:
        return False

def parse_params(params_str):
    params = []

    for param in params_str.split('_'):
        param = param.strip()
        if param.isdigit():
            param = int(param)
        elif isfloat(param):
            param = float(param)
        else:
            continue
        params.append(param)

    return params

def get_squeezer_by_name(name, func_type):
    squeezer_list = ['none',
                     'bit_depth_random',
                     'bit_depth',
                     'binary_filter',
                     'binary_random_filter',
                     'adaptive_binarize',
                     'otsu_binarize',
                     'median_filter',
                     'median_random_filter',
                     'median_random_size_filter',
                     'non_local_means_bw',
                     'non_local_means_color',
                     'adaptive_bilateral_filter',
                     'bilateral_filter',
                     'magnet_mnist',
                     'magnet_cifar10',
                    ]

    for squeezer_name in squeezer_list:
        if name.startswith(squeezer_name):
            func_name = "%s_py" % squeezer_name if func_type=='python' else "%s_tf" % squeezer_name
            params_str = name[len(squeezer_name):]

            # Return a list
            args = parse_params(params_str)
            # print ("params_str: %s, args: %s" % (params_str, args))

            return lambda x: globals()[func_name](*([x]+args))

    raise Exception('Unknown squeezer name: %s' % name)

def get_sequential_squeezers_by_name(squeezers_name):
    # example_squeezers_name = "binary_filter_0.5,median_smoothing_2_2"
    squeeze_func = None
    for squeezer_name in squeezers_name.split(','):
        squeezer = get_squeezer_by_name(squeezer_name, 'python')

        if squeeze_func == None:
            squeeze_func = lambda x: squeezer(x)
        else:
            old_func = squeeze_func
            squeeze_func = lambda x: squeezer(old_func(x))
    return squeeze_func
