import torch
import torch.nn as nn

import functools
from collections import OrderedDict


class L2Regularization(nn.Module):
    r"""The L2 regularization of parameters :math:`w` can be described as:

    .. math::
        {\Omega} (w) = \dfrac{1}{2}  \Vert w\Vert_2^2 ,

    Args:
        model (torch.nn.Module):  The model to apply L2 penalty.

    Shape:
        - Output: scalar.
    """

    def __init__(self, model: nn.Module):
        super(L2Regularization, self).__init__()
        self.model = model

    def forward(self):
        output = 0.0
        for param in self.model.parameters():
            output += 0.5 * torch.norm(param) ** 2
        return output


class SPRegularization(nn.Module):
    r"""
    The SP (Starting Point) regularization from `Explicit inductive bias for transfer learning with convolutional networks
    (ICML 2018) <https://arxiv.org/abs/1802.01483>`_

    The SP regularization of parameters :math:`w` can be described as:

    .. math::
        {\Omega} (w) = \dfrac{1}{2}  \Vert w-w^0\Vert_2^2 ,

    where :math:`w^0` is the parameter vector of the model pretrained on the source problem, acting as the starting point (SP) in fine-tuning.


    Args:
        source_model (torch.nn.Module):  The source (starting point) model.
        target_model (torch.nn.Module):  The target (fine-tuning) model.

    Shape:
        - Output: scalar.
    """

    def __init__(self, source_model: nn.Module, target_model: nn.Module):
        super(SPRegularization, self).__init__()
        self.target_model = target_model
        self.source_weight = {}
        for name, param in source_model.named_parameters():
            self.source_weight[name] = param.detach()

    def forward(self):
        output = 0.0

        for name, param in self.target_model.named_parameters():
            output += 0.5 * torch.norm(param - self.source_weight[name]) ** 2
        return output


class FrobeniusRegularization(nn.Module):
    r"""
    The SP (Starting Point) regularization from `Explicit inductive bias for transfer learning with convolutional networks
    (ICML 2018) <https://arxiv.org/abs/1802.01483>`_

    The SP regularization of parameters :math:`w` can be described as:

    .. math::
        {\Omega} (w) = \dfrac{1}{2}  \Vert w-w^0\Vert_2^2 ,

    where :math:`w^0` is the parameter vector of the model pretrained on the source problem, acting as the starting point (SP) in fine-tuning.


    Args:
        source_model (torch.nn.Module):  The source (starting point) model.
        target_model (torch.nn.Module):  The target (fine-tuning) model.

    Shape:
        - Output: scalar.
    """

    def __init__(self, source_model: nn.Module, target_model: nn.Module):
        super(FrobeniusRegularization, self).__init__()
        self.target_model = target_model
        self.source_weight = {}
        self.D = 1
        self.scale_factor = 2
        for name, param in source_model.named_parameters():
            self.source_weight[name] = param.detach()

    def forward(self):
        output = 0.0
        for name, param in self.target_model.named_parameters():
            if name.startswith('gnns') or name.startswith('batch_norms'):
                gamma = int(name.split('.')[1])
            else:
                gamma = 1
            #     norm = torch.norm(param - self.source_weight[name]) Frobi
            norm = torch.abs(param - self.source_weight[name]).sum(-1).max()  # MARS  max absolute row sum
            output = output + torch.clamp_min(
                norm - self.D * torch.pow(torch.tensor([self.scale_factor], device=norm.device),
                                          gamma), 0)

        # for name, param in self.target_model.named_parameters():
        #     output += 0.5 * torch.norm(param - self.source_weight[name]) ** 2
        # for name, param in self.target_model.named_parameters():
        #     if name.startswith('gnns'):
        #         # print(int(name.split('.')[1]))
        #         print(torch.norm(param - self.source_weight[name]))
        #         print(torch.pow(torch.tensor([1.2]),int(name.split('.')[1])))
        return output


class BehavioralRegularization(nn.Module):
    r"""
    The behavioral regularization from `DELTA:DEep Learning Transfer using Feature Map with Attention
    for convolutional networks (ICLR 2019) <https://openreview.net/pdf?id=rkgbwsAcYm>`_

    It can be described as:

    .. math::
        {\Omega} (w) = \sum_{j=1}^{N}   \Vert FM_j(w, \boldsymbol x)-FM_j(w^0, \boldsymbol x)\Vert_2^2 ,

    where :math:`w^0` is the parameter vector of the model pretrained on the source problem, acting as the starting point (SP) in fine-tuning,
    :math:`FM_j(w, \boldsymbol x)` is feature maps generated from the :math:`j`-th layer of the model parameterized with :math:`w`, given the input :math:`\boldsymbol x`.


    Inputs:
        layer_outputs_source (OrderedDict):  The dictionary for source model, where the keys are layer names and the values are feature maps correspondingly.

        layer_outputs_target (OrderedDict):  The dictionary for target model, where the keys are layer names and the values are feature maps correspondingly.

    Shape:
        - Output: scalar.

    """

    def __init__(self):
        super(BehavioralRegularization, self).__init__()

    def forward(self, layer_outputs_source, layer_outputs_target):
        output = 0.0
        for fm_src, fm_tgt in zip(layer_outputs_source.values(), layer_outputs_target.values()):
            output += 0.5 * (torch.norm(fm_tgt - fm_src.detach()) ** 2)
        return output


class AttentionBehavioralRegularization(nn.Module):
    r"""
    The behavioral regularization with attention from `DELTA:DEep Learning Transfer using Feature Map with Attention
    for convolutional networks (ICLR 2019) <https://openreview.net/pdf?id=rkgbwsAcYm>`_

    It can be described as:

    .. math::
        {\Omega} (w) = \sum_{j=1}^{N}  W_j(w) \Vert FM_j(w, \boldsymbol x)-FM_j(w^0, \boldsymbol x)\Vert_2^2 ,

    where
    :math:`w^0` is the parameter vector of the model pretrained on the source problem, acting as the starting point (SP) in fine-tuning.
    :math:`FM_j(w, \boldsymbol x)` is feature maps generated from the :math:`j`-th layer of the model parameterized with :math:`w`, given the input :math:`\boldsymbol x`.
    :math:`W_j(w)` is the channel attention of the :math:`j`-th layer of the model parameterized with :math:`w`.

    Args:
        channel_attention (list): The channel attentions of feature maps generated by each selected layer. For the layer with C channels, the channel attention is a tensor of shape [C].

    Inputs:
        layer_outputs_source (OrderedDict):  The dictionary for source model, where the keys are layer names and the values are feature maps correspondingly.

        layer_outputs_target (OrderedDict):  The dictionary for target model, where the keys are layer names and the values are feature maps correspondingly.

    Shape:
        - Output: scalar.

    """

    def __init__(self, channel_attention):
        super(AttentionBehavioralRegularization, self).__init__()
        self.channel_attention = channel_attention
        # self.channel_attention = torch.random

    def forward(self, layer_outputs_source, layer_outputs_target):
        output = 0.0
        for i, (fm_src, fm_tgt) in enumerate(zip(layer_outputs_source.values(), layer_outputs_target.values())):
            # b, c, h, w = fm_src.shape
            b, c = fm_src.shape
            # fm_src = fm_src.reshape(b, c, h * w)
            # fm_tgt = fm_tgt.reshape(b, c, h * w)
            # todo 欧式距离-> warstrass distance
            distance = torch.norm(fm_tgt - fm_src.detach(), p=2, dim=0)  #

            # self.channel_attention[i] = torch.ones_like(self.channel_attention[i])/self.channel_attention[i].shape[0]
            distance = torch.mul(self.channel_attention[i], distance ** 2)
            # distance = c * torch.mul(self.channel_attention[i], distance ** 2) / (h * w)
            output += 0.5 * torch.sum(distance)

        return output


def get_attribute(obj, attr, *args):
    def _getattr(obj, attr):
        return getattr(obj, attr, *args)

    return functools.reduce(_getattr, [obj] + attr.split('.'))


class IntermediateLayerGetter(object):
    r"""
    Wraps a model to get intermediate output values of selected layers.

    Args:
       model (torch.nn.Module): The model to collect intermediate layer feature maps.
       return_layers (list): The names of selected modules to return the output.
       keep_output (bool): If True, `model_output` contains the final model's output, else return None. Default: True

    Returns:
       - An OrderedDict of intermediate outputs. The keys are selected layer names in `return_layers` and the values are the feature map outputs. The order is the same as `return_layers`.
       - The model's final output. If `keep_output` is False, return None.

    """

    def __init__(self, model, return_layers, keep_output=True):
        self._model = model
        self.return_layers = return_layers
        self.keep_output = keep_output

    def __call__(self, *args, **kwargs):
        ret = OrderedDict()
        handles = []
        for name in self.return_layers:
            layer = get_attribute(self._model, name)

            def hook(module, input, output, name=name):
                ret[name] = output

            try:
                h = layer.register_forward_hook(hook)
            except AttributeError as e:
                raise AttributeError(f'Module {name} not found')
            handles.append(h)
        # todo
        if self.keep_output:
            output = self._model(*args, **kwargs)
        else:
            self._model(*args, **kwargs)
            output = None

        for h in handles:
            h.remove()

        return ret, output
