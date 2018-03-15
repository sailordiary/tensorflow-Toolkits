#!/usr/bin/env python
# -*- coding:utf-8 -*-
# 2018.3.14;
# Copyright (C) 2017 Shuang Yang, Mingmin Yang /@


import numpy as np
from tensorflow.python.ops import array_ops
from tensorflow.python.ops import variable_scope
from tensorflow.python.ops import math_ops
from tensorflow.python.ops import nn
from tensorflow.python.framework import ops
from tensorflow.python.framework import dtypes

__all__ = ['_flattern', '_concat', '_sparse_tuple_from', '_decode_sparse_tuple',
           '_sparsemax', '_hardmax']

def _flattern(_input, axis=0, name="flattern"):
    """
    flattern a tensor at the given 'axis', which means only the given 'axis' will remain

    :return
        tensor, shape = [_input.shape[axis], -1]
    """
    # input: [batch_size, ....]
    with variable_scope.variable_scope(name) as scope:
        shape =_input.shape.as_list()
        if shape.__len__() < 2:
            raise ValueError('Inputs must have a least 2 dimensions.')
        dim = shape[axis]
        out = array_ops.reshape(_input, shape=[dim, -1])
        return out

def _concat(input_1, input_2, axis=-1, name="concat"):
    """
    concat two tensors at the given 'axis'
    """
    with variable_scope.variable_scope(name) as scope:
        shape1 = input_1.shape.as_list()
        shape2 = input_2.shape.as_list()
        assert shape1.__len__() == shape2.__len__()
        out = array_ops.concat([input_1, input_2], axis=axis)
    return out

def _sparse_tuple_from(src_seq_list, dtype=np.int32):
    """
    convert a list to sparse tuple

    usage:
        src_seq_list = [[1,2],[1],[1,2,3,4,5],[2,5,2,6]]
        sparse_tensor = sparse_tuple_from(src_seq_list)
        then :
            sparse_tensor[0](indices) = [[0,0],[0,1],[1,0],[2,0],[2,1],[2,2],[2,3],[2,4],[3,0],[3,1],[3,2],[3,3]]
            sparse_tensor[1](values) =  [1,2,1,1,2,3,4,5,2,5,2,6], squeezed src_seq_list's values
            sparse_tensor[2](shape) =  [4,5] , 4: number of sequence; 5: max_length of seq_labels
    """

    indices = []
    values = []
    for n, seq in enumerate(src_seq_list):
        indices.extend(zip([n] * len(seq), xrange(len(seq))))
        values.extend(seq)

    indices = np.asarray(indices, dtype=dtype)
    values = np.asarray(values, dtype=dtype)
    shape = np.asarray([len(src_seq_list), np.asarray(indices).max(0)[1] + 1], dtype=dtype)

    return indices, values, shape

# py_models_fea.decode_sparse_tensor(), modification version
def _decode_sparse_tuple(sparse_tensor):
    """
    decode a sparse tuple generated by function _sparse_tuple_from(),
    what this method does is the inverse process of _sparse_tuple_from()

    usage:
        sparse_tensor[0](indices) = [[0,0],[0,1],[1,0],[2,0],[2,1],[2,2],[2,3],[2,4],[3,0],[3,1],[3,2],[3,3]]
        sparse_tensor[1](values) =  [1,2,1,1,2,3,4,5,2,5,2,6], squeezed src_seq_list's values
        sparse_tensor[2](shape) =  [4,5] , 4: number of sequence; 5: max_length of seq_labels

        res = _decode_sparse_tuple(sparse_tensor)
        res: [[1,2],[1],[1,2,3,4,5],[2,5,2,6]]

    """
    # ele_count = [2, 1, 5, 4]
    ele_count = np.bincount(map(lambda a: a[0], sparse_tensor[0]))
    res = []
    total_c = 0
    for c in ele_count:
        res.append(list(sparse_tensor[1][total_c:total_c + c]))
        total_c += c
    return res

def _sparsemax(logits, name=None):
    """Computes sparsemax activations [1].

    For each batch `i` and class `j` we have
    sparsemax[i, j] = max(logits[i, j] - tau(logits[i, :]), 0)

    [1]: https://arxiv.org/abs/1602.02068

    :param logits, tensor

    Returns:
    A `Tensor`. Has the same type as `logits`.
    """

    with ops.name_scope(name, "sparsemax", [logits]) as name:
        logits = ops.convert_to_tensor(logits, name="logits")
        obs = logits.shape[0]
        dims = logits.shape[1]

        z = logits - math_ops.reduce_mean(logits, axis=1)[:, array_ops.newaxis]

        # sort z
        z_sorted, _ = nn.top_k(z, k=dims)

        # calculate k(z)
        z_cumsum = math_ops.cumsum(z_sorted, axis=1)
        k = math_ops.range(
            1, math_ops.cast(dims, logits.dtype) + 1, dtype=logits.dtype)
        z_check = 1 + k * z_sorted > z_cumsum
        # because the z_check vector is always [1,1,...1,0,0,...0] finding the
        # (index + 1) of the last `1` is the same as just summing the number of 1.
        k_z = math_ops.reduce_sum(math_ops.cast(z_check, dtypes.int32), axis=1)

        # calculate tau(z)
        indices = array_ops.stack([math_ops.range(0, obs), k_z - 1], axis=1)
        tau_sum = array_ops.gather_nd(z_cumsum, indices)
        tau_z = (tau_sum - 1) / math_ops.cast(k_z, logits.dtype)

        # calculate p
        return math_ops.maximum(
            math_ops.cast(0, logits.dtype), z - tau_z[:, array_ops.newaxis])

def _hardmax(logits, name=None):
    """Returns batched one-hot vectors.

    The depth index containing the `1` is that of the maximum logit value.

    :param logits: A batch tensor of logit values.

    Returns:
        A batched one-hot tensor.
    """
    with ops.name_scope(name, "Hardmax", [logits]):
        logits = ops.convert_to_tensor(logits, name="logits")
        if logits.get_shape()[-1].value is not None:
            depth = logits.get_shape()[-1].value
        else:
            depth = logits.shape[-1]
        return array_ops.one_hot(
        math_ops.argmax(logits, -1), depth, dtype=logits.dtype)