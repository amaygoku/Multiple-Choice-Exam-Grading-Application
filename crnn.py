import tensorflow as tf
import numpy as np
import cv2
from tensorflow.keras.models import Model
from tensorflow.keras.layers import *
from tensorflow.keras import backend as K




def preprocess_image(img_path):
    img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
    
    # resize đúng size train
    img = cv2.resize(img, (IMG_WIDTH, IMG_HEIGHT))
    
    # normalize
    img = img / 255.0
    
    # expand dims → (1, H, W, 1)
    img = np.expand_dims(img, axis=0)
    img = np.expand_dims(img, axis=-1)
    
    return img

def decode_prediction(pred):
    input_len = np.ones(pred.shape[0]) * pred.shape[1]
    
    results = K.ctc_decode(pred, input_length=input_len, greedy=True)[0][0]
    
    output_text = []
    
    for res in results:
        res = tf.keras.backend.get_value(res)
        text = ""
        for i in res:
            if i != -1:
                text += char_list[i]
        output_text.append(text)
        
    return output_text

# ====== CONFIG ======
IMG_HEIGHT = 118
IMG_WIDTH = 2167

# char_list phải giống lúc train
char_list = list(" #'()+,-./0123456789:ABCDEFGHIJKLMNOPQRSTUVWXYabcdeghiklmnopqrstuvwxyzÂÊÔàáâãèéêìíòóôõùúýăĐđĩũƠơưạảấầẩậắằẵặẻẽếềểễệỉịọỏốồổỗộớờởỡợụủỨứừửữựỳỵỷỹ")  # sửa đúng của bạn

# ====== BUILD MODEL (giống y hệt lúc train) ======
inputs = Input(shape=(IMG_HEIGHT, IMG_WIDTH, 1))

x = Conv2D(64, (3,3), padding='same')(inputs)
x = MaxPool2D(pool_size=3, strides=3)(x)
x = Activation('relu')(x)

x = Conv2D(128, (3,3), padding='same')(x)
x = MaxPool2D(pool_size=3, strides=3)(x)
x = Activation('relu')(x)

x = Conv2D(256, (3,3), padding='same')(x)
x = BatchNormalization()(x)
x = Activation('relu')(x)
x_3 = x

x = Conv2D(256, (3,3), padding='same')(x)
x = BatchNormalization()(x)
x = Add()([x,x_3])
x = Activation('relu')(x)

x = Conv2D(512, (3,3), padding='same')(x)
x = BatchNormalization()(x)
x = Activation('relu')(x)
x_5 = x

x = Conv2D(512, (3,3), padding='same')(x)
x = BatchNormalization()(x)
x = Add()([x,x_5])
x = Activation('relu')(x)

x = Conv2D(1024, (3,3), padding='same')(x)
x = BatchNormalization()(x)
x = MaxPool2D(pool_size=(3,1))(x)
x = Activation('relu')(x)

x = MaxPool2D(pool_size=(3,1))(x)

# squeeze height
x = Lambda(lambda x: K.squeeze(x, 1))(x)

# LSTM
x = Bidirectional(LSTM(512, return_sequences=True))(x)
x = Bidirectional(LSTM(512, return_sequences=True))(x)

outputs = Dense(len(char_list)+1, activation='softmax')(x)

model = Model(inputs, outputs)

# ====== LOAD WEIGHTS ======
model.load_weights("checkpoint_weights.weights.h5")

print("Loaded model!")

img_path = "huy1.png"  # đổi thành ảnh của bạn

img = preprocess_image(img_path)


pred = model.predict(img)

text = decode_prediction(pred)

print("Prediction:", text[0])