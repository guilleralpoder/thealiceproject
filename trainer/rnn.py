# Small LSTM Network to Generate Text based on Alice in Wonderland
# to run on Google Cloud ML Engine


import argparse
# import pickle # for handling the new data source
import h5py  # for saving the model

from datetime import datetime  # for filename conventions

import numpy
from keras.models import Sequential
from keras.layers import Dense
from keras.layers import Dropout
from keras.layers import LSTM
from keras.callbacks import ModelCheckpoint
from keras.utils import np_utils

from tensorflow.python.lib.io import file_io  # for better file I/O
import sys

# Create a function to allow for different training data and other options


def train_model(train_file='data/wonderland.txt',
                job_dir='./tmp/wonderland', **args):
    # set the logging path for ML Engine logging to Storage bucket
    logs_path = job_dir + '/logs/' + datetime.now().isoformat()
    print('Using logs_path located at {}'.format(logs_path))

    # Reading in the pickle file. Pickle works differently with Python 2 vs 3
    f = file_io.FileIO(train_file, mode='r')
    # if sys.version_info < (3,):
    #   data = pickle.load(f)
    # else:
    #   data = pickle.load(f, encoding='bytes')

    # load ascii text and covert to lowercase
    #fs = open(train_file)
    data = f.read()
    f.close()
    raw_text = data.lower()

    # create mapping of unique chars to integers
    chars = sorted(list(set(raw_text)))
    char_to_int = dict((c, i) for i, c in enumerate(chars))

    # summarize the loaded data
    n_chars = len(raw_text)
    n_vocab = len(chars)
    print("Total Characters: ", n_chars)
    print("Total Vocab: ", n_vocab)

    # prepare the dataset of input to output pairs encoded as integers
    seq_length = 20
    dataX = []
    dataY = []
    for i in range(0, n_chars - seq_length, 1):
        seq_in = raw_text[i:i + seq_length]
        seq_out = raw_text[i + seq_length]
        dataX.append([char_to_int[char] for char in seq_in])
        dataY.append(char_to_int[seq_out])
    n_patterns = len(dataX)
    print("Total Patterns: ", n_patterns)

    # reshape X to be [samples, time steps, features]
    X = numpy.reshape(dataX, (n_patterns, seq_length, 1))

    # normalize
    X = X / float(n_vocab)

    # one hot encode the output variable
    y = np_utils.to_categorical(dataY)

    # set the learning phase constant - fixes the bug when calling predict model using TF serving
    from keras import backend as K
    K.set_learning_phase(False)

    # define the LSTM model
    model = Sequential()
    model.add(LSTM(256, input_shape=(X.shape[1], X.shape[2])))
    model.add(Dropout(0.2))
    model.add(Dense(y.shape[1], activation='softmax'))

    model.summary()

    model.compile(loss='categorical_crossentropy', optimizer='adam')

    # define the checkpoint
    filepath = "weights-improvement-{epoch:02d}-{loss:.4f}.hdf5"
    checkpoint = ModelCheckpoint(
        filepath, monitor='loss', verbose=1, save_best_only=True, mode='min')
    callbacks_list = [checkpoint]

    # fit the model
    model.fit(X, y, epochs=1, batch_size=128, callbacks=callbacks_list)

    # save the Keras model in GCS
    model.save(job_dir+'/KerasModel/model.h5')

    # convert model to SavedModel and save to Google Cloud Storage
    '''
    import tensorflow as tf

    inputs = {"inputs": tf.saved_model.utils.build_tensor_info(model.input)}
    outputs = {"outputs": tf.saved_model.utils.build_tensor_info(model.output)}
    signature = tf.saved_model.signature_def_utils.build_signature_def(
        inputs=inputs,
        outputs=outputs,
        method_name=tf.saved_model.signature_constants.PREDICT_METHOD_NAME
    )

    # save as SavedModel
    builder = tf.saved_model.builder.SavedModelBuilder(job_dir+'/SavedModel')
    builder.add_meta_graph_and_variables(
        sess=K.get_session(),
        tags=[tf.saved_model.tag_constants.SERVING],
        signature_def_map={
            tf.saved_model.signature_constants.DEFAULT_SERVING_SIGNATURE_DEF_KEY:
            signature
        })
    builder.save()
    '''

if __name__ == '__main__':
    # Parse the input arguments for common Cloud ML Engine options
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--train-file',
        help='Cloud Storage bucket or local path to training data')
    parser.add_argument(
        '--job-dir',
        help='Cloud storage bucket to export the model and store temp files')
    args = parser.parse_args()
    arguments = args.__dict__
    train_model(**arguments)
