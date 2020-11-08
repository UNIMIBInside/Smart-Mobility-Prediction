from keras.models import Model
from keras.layers import (
    Input,
    Activation,
    Flatten,
    Concatenate,
    Dense,
    Reshape,
    Conv2D,
    BatchNormalization,
    Add,
    Conv2DTranspose,
    LSTM
)
import numpy as np

def conv_relu_bn(filters):
    def f(input_layer):
        l = Conv2D(filters, (3,3), padding='same', activation='relu')(input_layer)
        l = BatchNormalization()(l)
        return l                                                                                                                                                                                                                                      
    return f

def _residual_unit(filters):
    def f(input_layer):
        residual = conv_relu_bn(filters)(input_layer)
        # residual = filters(filters)(residual)
        return Add()([input_layer, residual])
    return f

def resUnits2D(filters, repetations=1):
    def f(input_layer):
        for i in range(repetations):
            input_layer = _residual_unit(filters)(input_layer)
        return input_layer
    return f

# def my_conv(input_layer, filters, activation):
#     l = Conv2D(filters, (3,3), padding='same', activation=activation)(input_layer)
#     l = BatchNormalization()(l)
#     return l

def my_downsampling(input_layer):
    l = Conv2D(input_layer.shape[-1], (2,2), (2,2), activation='relu')(input_layer)
    l = BatchNormalization()(l)
    return l

def my_conv_transpose(input_layer, skip_connection_layer):
    l = Conv2DTranspose(input_layer.shape[-1], (2,2), (2,2))(input_layer)
    l = Add()([l, skip_connection_layer])
    l = Activation('relu')(l)
    l = BatchNormalization()(l)
    return l

def my_model(len_c, len_p, len_t, nb_flow=2, map_height=32, map_width=32, external_dim=8, encoder_blocks=3, filters=[32,64,64,16]):

    main_inputs = []
    #ENCODER
    # input layer 32x32x14
    input = Input(shape=((map_height, map_width, nb_flow * (len_c+len_p*2+len_t*2))))
    main_inputs.append(input)
    x = input

    # merge external features
    if external_dim != None and external_dim > 0:
        # external input
        external_input = Input(shape=(external_dim,))
        main_inputs.append(external_input)
        embedding = Dense(units=10, activation='relu')(external_input)
        h1 = Dense(units=nb_flow*map_height * map_width, activation='relu')(embedding)
        external_output = Reshape((map_height, map_width, nb_flow))(h1)
        main_output = Concatenate(axis=3)([input, external_output])
        x = main_output

    # build encoder blocks
    skip_connection_layers = []
    for i in range(0, encoder_blocks):
        # conv + relu + bn + res
        x = conv_relu_bn(filters[i])(x)
        x = resUnits2D(filters[i])(x)
        # append layer to skip connection list
        skip_connection_layers.append(x)
        # max pool
        x = my_downsampling(x)

    # last convolution 4x4x16
    x = conv_relu_bn(filters[-1])(x)
    s = x.shape

    x = Reshape((x.shape[1]*x.shape[2], x.shape[3]))(x)
    x = LSTM(100, return_sequences=True)(x)
    x = LSTM(100, return_sequences=True)(x)
    x = LSTM(100, return_sequences=True)(x)
    x = LSTM(16, return_sequences=True)(x)
    x = Reshape((s[1:]))(x)

    # # dense layer for bottleneck
    # vol = x.shape
    # x = Flatten()(x)
    # x = Dense(x.shape[1]/2, activation='relu')(x)

    # # DECODER
    # # simmetric dense layer and reshape 4x4x16
    # x = Dense(np.prod(vol[1:]), activation='relu')(x)
    # x = Reshape((vol[1], vol[2], vol[3]))(x)

    # build decoder blocks
    for i in reversed(range(0, encoder_blocks)):
        # conv + relu + bn
        x = conv_relu_bn(filters[i])(x)
        x = resUnits2D(filters[i])(x)
        # conv_transpose + skip_conn + relu + bn
        x = my_conv_transpose(x, skip_connection_layers[i])

    # last convolution + tanh + bn 32x32x2
    output = Conv2D(nb_flow, (3,3), padding='same', activation='tanh')(x)

    return Model(main_inputs, output)
