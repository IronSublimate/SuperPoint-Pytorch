# SuperPoint-Pytorch (A Pure Pytorch Implementation)
SuperPoint: Self-Supervised Interest Point Detection and Description  


# Thanks  
This work is based on:  
- Tensorflow implementation by [Rémi Pautrat and Paul-Edouard Sarlin](https://github.com/rpautrat/SuperPoint)  
- Official [SuperPointPretrainedNetwork](https://github.com/magicleap/SuperPointPretrainedNetwork). 
- [Kornia](https://kornia.github.io/)  

# Existing Problems
1. Different performances in training and evaluation modes, which is 
a famous problem have been discussed in 
[Performance highly degraded when eval() is activated in the test phase](https://discuss.pytorch.org/t/performance-highly-degraded-when-eval-is-activated-in-the-test-phase/3323)

# Our Performances
- MagicPoint, detection repeatability on Hpatches: 0.664
- SuperPoint, homography estimation correctness on Hpatches: 0.715
# Some Training Tricks For SuperPoint
##Before Training  
1. Remove parameter eps=1e-3 for all the BatchNorma2d functions
       in model/modules/cnn/\*.py   
2. Set better parameters, especially for lambda_d, lambda_loss in *.yaml. 
       You can use the default parameters in superpoint_train.yaml 
##Training Steps
1. Train detector loss. Replace line  
`        loss = det_loss + det_loss_warp + weighted_des_loss
`  
with  
`        loss = det_loss + det_loss_warp
`  
in loss.py
2. Commet the following lines in loss.py

```
dot_product_desc = torch.reshape(F.normalize(torch.reshape(dot_product_desc, [batch_size, Hc, Wc, Hc * Wc]),
                                              p=2,
                                              dim=3), [batch_size, Hc, Wc, Hc, Wc])
dot_product_desc = torch.reshape(F.normalize(torch.reshape(dot_product_desc, [batch_size, Hc * Wc, Hc, Wc]),
                                              p=2,
                                              dim=1), [batch_size, Hc, Wc, Hc, Wc])
``` 

3. Set base_lr=0.01 (in superpoint_train.yaml)  
4. Start training and get a pretrained model _./export/sp_2_0.46.pth_
5. Set pretrained_model=./export/sp_2_0.46.pth and base_lr=0.0001
6. Train both detector and descriptor loss, i.e., set  
`loss = det_loss + det_loss_warp + weighted_des_loss`   
, and start training.

##Other Practices  
1. Remove BatchNorm2d or other batch normalization op. 


# New Update (09/04/2021)
* You can now reproduce [rpautrat/Superpoint](https://github.com/rpautrat/SuperPoint)'s performances with pytorch.   
* Main steps:
    - 1 Construct network by [superpoint_bn.py](model/superpoint_bn.py) (Refer to [train.py](./train.py) for more details)
    - 2 Set parameter eps=1e-3 for all the BatchNormalization functions in model/modules/cnn/*.py
    - 3 Load pretrained weight [superpoint_bn.pth](./superpoint_bn.pth) and run forward propagation
 

# Usage
* 1 Prepare your data. Make directories *data* and *export*. The data directory should look like,
    ```
    data
    |-- coco
    |  |-- train2017
    |  |     |-- a.jpg
    |  |     |-- ...
    |  --- test2017
    |        |-- b.jpg
    |        |-- ...
    |-- hpatches
    |   |-- i_ajuntament
    |   |   |--1.ppm
    |   |   |--...
    |   |   |--H_1_2
    |   |-- ...
    ```
    You can create *soft links* if you already have *coco, hpatches* data sets, the commands are,
    ```
    cd data
    ln -s dir_to_coco ./coco
    ```
* 2 The training steps are much similar to [rpautrat/Superpoint](https://github.com/rpautrat/SuperPoint). 
    **However we strongly suggest you read the scripts first so that you can give correct settings for your envs.**   
    - 2.1 Train MagicPoint (about 1~3 hours):  
          `python train.py ./config/magic_point_train.yaml`   
          (Note that you have to delete the directory _./data/synthetic_shapes_ 
          whenever you want to regenerate it)
    - 2.2 Export coco labels (need very long time):   
          `python homo_export_labels.py #using your data dirs`
    - 2.3 Train MagicPoint on coco labels data set (exported by step 2.2)       
          `python train.py ./config/magic_point_coco_train.py #with correct data dirs` 
    - 2.4 Train SuperPoint following the steps in **Training Steps**     
          `python train.py ./config/superpoint_train.py #with correct data dirs`  
    - others. Validate detection repeatability or description
              (Better in training mode if you also have eval problem stated in **Existing Problems**)  
                   
        ```
        python export_detections_repeatability.py   
        python compute_repeatability.py  
        ## or
        python export_descriptors.py  
        python compute_desc_eval.py  
        ```   
    **AGAIN: you have to edit _.yaml_ files to run corresponding tasks,
     especially for the _path_ or _dir_ items** 
    ```
    model
        name: superpoint # magicpoint
     ...
    data:
        name: coco #synthetic
        image_train_path: ['./data/mp_coco_v2/images/train2017',] #several data sets can be list here
        label_train_path: ['./data/mp_coco_v2/labels/train2017/',]
        image_test_path: './data/mp_coco_v2/images/test2017/'
        label_test_path: './data/mp_coco_v2/labels/test2017/'
    ```

