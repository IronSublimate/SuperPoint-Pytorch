#-*-coding:utf8-*-
import torch
import numpy as np
import cv2
import os
import yaml
import argparse
from tqdm import tqdm
from dataset.synthetic_shapes import SyntheticShapes
from dataset.coco import COCODataset
from torch.utils.data import DataLoader
from model.magic_point import MagicPoint
from model.superpoint_bn import SuperPointBNNet
from solver.loss import loss_func
from solver.nms import box_nms


def train_eval(model, dataloader, config):
    optimizer = torch.optim.Adam(model.parameters(), lr=config['solver']['base_lr'])
    #lr_sch = StepLR(optimizer, step_size=10000,gamma=0.5)

    # start training
    for epoch in range(config['solver']['epoch']):
        model.train()
        mean_loss, best_loss = [], 9999
        for i, data in tqdm(enumerate(dataloader['train']), desc='Epoch:{}'.format(epoch)):

            prob, desc, prob_warp, desc_warp = None, None, None, None
            raw_outputs = model(data['raw'])
            if config['model']['name']=='superpoint':
                warp_outputs = model(data['warp'])
                prob, desc, prob_warp, desc_warp = raw_outputs['det_info'], \
                                                   raw_outputs['desc_info'], \
                                                   warp_outputs['det_info'],\
                                                   warp_outputs['desc_info']
            else:
                prob = raw_outputs

            ##loss
            loss = loss_func(config['solver'], data, prob, desc,
                             prob_warp, desc_warp, device)

            mean_loss.append(loss.item())
            # reset
            model.zero_grad()
            loss.backward()
            optimizer.step()
            #lr_sch.step()

            # for every 1000 images, print progress and visualize the matches
            if i % 500 == 0:
                print('Epoch [{}/{}], Step [{}/{}], LR [{}], Loss: {:.3f}'
                      .format(epoch, config['solver']['epoch'], i, len(dataloader['train']),
                              optimizer.state_dict()['param_groups'][0]['lr'], np.mean(mean_loss)))
                mean_loss = []
            # do evaluation
            if (i%10000==0 and i!=0) or (i+1)==len(dataloader['train']):
                eval_loss = do_eval(model, dataloader['test'], config, device)
                model.train()
                if eval_loss < best_loss:
                    save_path = os.path.join(config['solver']['save_dir'],
                                             config['solver']['model_name'] + '_{}_{}.pth').format(epoch, round(eval_loss, 4))
                    torch.save(model.state_dict(), save_path)
                    print('Epoch [{}/{}], Step [{}/{}], Checkpoint saved to {}'
                          .format(epoch, config['solver']['epoch'], i, len(dataloader['train']), save_path))
                    best_loss = eval_loss
                mean_loss = []

@torch.no_grad()
def do_eval(model, dataloader, config, device):
    model.eval()
    mean_loss = 0.
    for i, data in tqdm(enumerate(dataloader), desc='Evaluation'):
        prob, desc, prob_warp, desc_warp = None, None, None, None
        raw_outputs = model(data['raw'])

        if 'warp' in data:
            warp_outputs = model(data['warp'])

        if 'warp' in data and 'desc_dict' in raw_outputs:
            prob, desc, prob_warp, desc_warp = raw_outputs['det_info'], \
                                               raw_outputs['desc_info'], \
                                               warp_outputs['det_info'], \
                                               warp_outputs['desc_info']
        else:
            prob = raw_outputs

        # compute loss
        loss = loss_func(config['solver'], data, prob, desc,
                         prob_warp, desc_warp, device)
        mean_loss += loss.item()
    mean_loss /= len(dataloader)

    return mean_loss


def visualize(model, img, config, device='cpu'):
    """
    :param img: cv2 Gray, [H,W]
    :param model:
    :param dataloader:
    :param config:
    :return:
    """
    point_size = 1
    point_color = (0, 255, 0)  # BGR
    thickness = 4  # 可以为 0 、4、8

    model.to(device).eval()
    img = torch.tensor(img[np.newaxis,np.newaxis,:,:], device=device, dtype=torch.float32)
    img = img/255.
    res = model(img)  # output {'logits':[B,65,H/8,W/8],'prob':[B,H,W]}
    prob = res['prob']
    prob = box_nms(prob, size=4, min_prob=0.015, keep_top_k=0)

    masks = (prob>=config['detection_threshold']).int()
    masks = masks.cpu().numpy()
    ##
    images = torch.clip((img*255.), 0, 255).to(torch.uint8)
    images = images.cpu().numpy().transpose(0,2,3,1)
    for c, (im, m) in enumerate(zip(images, masks)):
        im = np.concatenate((im, im, im), axis=-1)
        pts = np.where(m==1)
        pts = np.stack(pts).T
        pts = pts.tolist()
        for p in pts:
            cv2.circle(im, tuple([p[1],p[0]]), point_size, point_color, thickness)
        #cv2.imshow('result.png',im)
        cv2.imwrite('result.png', im)


if __name__=='__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument("config")

    args = parser.parse_args()

    config_file = args.config
    assert(os.path.exists(config_file))
    ##
    with open(config_file,'r') as fin:
        config = yaml.safe_load(fin)

    if not os.path.exists(config['solver']['save_dir']):
        os.makedirs(config['solver']['save_dir'])

    device = 'cuda:0' if torch.cuda.is_available() else 'cpu'

    if config['data']['name']=='coco':
        datasets = {k:COCODataset(config['data'], is_train=True if k=='train' else False, device=device) for k in ['test','train']}
        data_loaders = {k:DataLoader(datasets[k],
                                     config['solver']['{}_batch_size'.format(k)],
                                     collate_fn=datasets[k].batch_collator,
                                     shuffle=True) for k in ['train','test']}
    elif config['data']['name']=='synthetic':
        datasets = {'train': SyntheticShapes(config['data'], task=['training', 'validation'], device=device),
                        'test': SyntheticShapes(config['data'], task=['test', ], device=device)}
        data_loaders = {'train': DataLoader(datasets['train'], batch_size=16, shuffle=True, collate_fn=datasets['train'].batch_collator),
                       'test': DataLoader(datasets['test'], batch_size=16, shuffle=False, collate_fn=datasets['test'].batch_collator)}

    if config['model']['name']=='superpoint':
        model = SuperPointBNNet(config['model'], device=device)
    else:
        model = MagicPoint(config['model'],device=device)

    if os.path.exists(config['model']['pretrained_model']):
        model.load_state_dict(torch.load(config['model']['pretrained_model']))
    model.to(device)

    train_eval(model, data_loaders, config)
    print('Done')

