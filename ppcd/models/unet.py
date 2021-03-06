import paddle
import paddle.nn as nn
import paddle.nn.functional as F
from ppcd.models.layers import ConvBNReLU


class UNet(nn.Layer):
    """
    The UNet implementation based on PaddlePaddle.
    The original article refers to
    Olaf Ronneberger, et, al. "U-Net: Convolutional Networks for Biomedical Image Segmentation"
    (https://arxiv.org/abs/1505.04597).
    Args:
        num_classes (int): The unique number of target classes.  Default: 2.
        in_channels (int, optional): Number of an image's channel.  Default: 3.
        align_corners (bool, optional): An argument of F.interpolate. It should be set to False when the output size of feature
            is even, e.g. 1024x512, otherwise it is True, e.g. 769x769.  Default: False.
        use_deconv (bool, optional): A bool value indicates whether using deconvolution in upsampling.
            If False, use resize_bilinear. Default: False.
    """
    def __init__(self,
                 in_channels=3,
                 num_classes=2,
                 num_image=2,
                 align_corners=False,
                 use_deconv=False,
                 first_concat=True):
        super().__init__()
        self.first_concat = first_concat
        self.encode = Encoder(in_channels, num_image, first_concat)
        self.decode = Decoder(num_image, align_corners, \
                              use_deconv=use_deconv, first_concat=first_concat)
        self.cls = self.conv = nn.Conv2D(
            in_channels=64,
            out_channels=num_classes,
            kernel_size=3,
            stride=1,
            padding=1)

    def forward(self, images):
        logit_list = []
        if self.first_concat:
            x = paddle.concat(images, axis=1)
            x, short_cuts = self.encode(x)
        else:
            xs = []
            scs = []
            for ima in images:
                x, short_cuts = self.encode(ima)
                xs.append(x)
                scs.append(short_cuts)
            x = paddle.concat(xs, axis=1)
            short_cuts = paddle.concat(scs, axis=1)
        x = self.decode(x, short_cuts)
        logit = self.cls(x)
        logit_list.append(logit)
        return logit_list


class Encoder(nn.Layer):
    def __init__(self, in_channels, num_image, first_concat=True):
        super().__init__()
        bate = 1 if first_concat == False else num_image
        self.double_conv = nn.Sequential(
            ConvBNReLU(bate*in_channels, 64, 3), ConvBNReLU(64, 64, 3))
        down_channels = [[64, 128], [128, 256], [256, 512], [512, 512]]
        self.down_sample_list = nn.LayerList([
            self.down_sampling(channel[0], channel[1])
            for channel in down_channels
        ])
    def down_sampling(self, in_channels, out_channels):
        modules = []
        modules.append(nn.MaxPool2D(kernel_size=2, stride=2))
        modules.append(ConvBNReLU(in_channels, out_channels, 3))
        modules.append(ConvBNReLU(out_channels, out_channels, 3))
        return nn.Sequential(*modules)

    def forward(self, x):
        short_cuts = []
        x = self.double_conv(x)
        for down_sample in self.down_sample_list:
            short_cuts.append(x)
            x = down_sample(x)
        return x, short_cuts


class Decoder(nn.Layer):
    def __init__(self, num_image, align_corners, use_deconv=False, first_concat=True):
        super().__init__()
        rate = 1 if first_concat == True else num_image
        up_channels = [[rate * 512, 256], [256, 128], [128, 64], [64, 64]]
        self.up_sample_list = nn.LayerList([
            UpSampling(channel[0], channel[1], align_corners, use_deconv)
            for channel in up_channels
        ])

    def forward(self, x, short_cuts):
        for i in range(len(short_cuts)):
            x = self.up_sample_list[i](x, short_cuts[-(i + 1)])
        return x


class UpSampling(nn.Layer):
    def __init__(self,
                 in_channels,
                 out_channels,
                 align_corners,
                 use_deconv=False):
        super().__init__()
        self.align_corners = align_corners
        self.use_deconv = use_deconv
        if self.use_deconv:
            self.deconv = nn.Conv2DTranspose(
                in_channels,
                out_channels // 2,
                kernel_size=2,
                stride=2,
                padding=0)
            in_channels = in_channels + out_channels // 2
        else:
            in_channels *= 2
        self.double_conv = nn.Sequential(
            ConvBNReLU(in_channels, out_channels, 3),
            ConvBNReLU(out_channels, out_channels, 3))
            
    def forward(self, x, short_cut):
        if self.use_deconv:
            x = self.deconv(x)
        else:
            x = F.interpolate(
                x,
                short_cut.shape[2:],
                mode='bilinear',
                align_corners=self.align_corners)
        x = paddle.concat([x, short_cut], axis=1)
        x = self.double_conv(x)
        return x